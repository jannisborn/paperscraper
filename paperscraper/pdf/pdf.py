"""Functionalities to scrape PDF files of publications."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

import requests
import tldextract
from bs4 import BeautifulSoup
from tqdm import tqdm

from ..utils import load_jsonl
from .fallbacks import FALLBACKS
from .utils import load_api_keys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

ABSTRACT_ATTRIBUTE = {
    "biorxiv": ["DC.Description"],
    "arxiv": ["citation_abstract"],
    "chemrxiv": ["citation_abstract"],
}
DEFAULT_ATTRIBUTES = ["citation_abstract", "description"]


def save_pdf(
    paper_metadata: Dict[str, Any],
    filepath: Union[str, Path],
    save_metadata: bool = False,
    api_keys: Optional[Union[str, Dict[str, str]]] = None,
) -> None:
    """
    Save a PDF file of a paper.

    Args:
        paper_metadata: A dictionary with the paper metadata. Must contain the `doi` key.
        filepath: Path to the PDF file to be saved (with or without suffix).
        save_metadata: A boolean indicating whether to save paper metadata as a separate json.
        api_keys: Either a dictionary containing API keys (if already loaded) or a string (path to API keys file).
                  If None, will try to load from `.env` file and if unsuccessful, skip API-based fallbacks.
    """
    if not isinstance(paper_metadata, Dict):
        raise TypeError(f"paper_metadata must be a dict, not {type(paper_metadata)}.")
    if "doi" not in paper_metadata.keys():
        raise KeyError("paper_metadata must contain the key 'doi'.")
    if not isinstance(filepath, str):
        raise TypeError(f"filepath must be a string, not {type(filepath)}.")

    output_path = Path(filepath)

    if not Path(output_path).parent.exists():
        raise ValueError(f"The folder: {output_path} seems to not exist.")

    # load API keys from file if not already loaded via in save_pdf_from_dump (dict)
    if not isinstance(api_keys, dict):
        api_keys = load_api_keys(api_keys)

    doi = paper_metadata["doi"]
    url = f"https://doi.org/{doi}"
    success = False
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        success = True
    except Exception as e:
        error = str(e)
        logger.warning(f"Could not download from: {url} - {e}. ")

    if not success and "biorxiv" in error:
        if (
            api_keys.get("AWS_ACCESS_KEY_ID") is None
            or api_keys.get("AWS_SECRET_ACCESS_KEY") is None
        ):
            logger.info(
                "BiorXiv PDFs can be downloaded from a S3 bucket with a requester-pay option. "
                "Consider setting `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` to use this option. "
                "Pricing is a few cent per GB, thus each request costs < 0.1 cents. "
                "For details see: https://www.biorxiv.org/tdm"
            )
        else:
            success = FALLBACKS["s3"](doi, output_path, api_keys)
            if success:
                return

    if not success:
        # always first try fallback to BioC-PMC (open access papers on PubMed Central)
        success = FALLBACKS["bioc_pmc"](doi, output_path)

        # if BioC-PMC fails, try other fallbacks
        if not success:
            # check for specific publishers
            if "elife" in error.lower():  # elife has an open XML repository on GitHub
                FALLBACKS["elife"](doi, output_path)
            elif (
                ("wiley" in error.lower())
                and api_keys
                and ("WILEY_TDM_API_TOKEN" in api_keys)
            ):
                FALLBACKS["wiley"](paper_metadata, output_path, api_keys)
        return

    soup = BeautifulSoup(response.text, features="lxml")
    meta_pdf = soup.find("meta", {"name": "citation_pdf_url"})
    if meta_pdf and meta_pdf.get("content"):
        pdf_url = meta_pdf.get("content")
        try:
            response = requests.get(pdf_url, timeout=60)
            response.raise_for_status()

            if response.content[:4] != b"%PDF":
                logger.warning(
                    f"The file from {url} does not appear to be a valid PDF."
                )
                success = FALLBACKS["bioc_pmc"](doi, output_path)
                if not success:
                    # Check for specific publishers
                    if "elife" in doi.lower():
                        logger.info("Attempting fallback to eLife XML repository")
                        FALLBACKS["elife"](doi, output_path)
                    elif api_keys and "WILEY_TDM_API_TOKEN" in api_keys:
                        FALLBACKS["wiley"](paper_metadata, output_path, api_keys)
                    elif api_keys and "ELSEVIER_TDM_API_KEY" in api_keys:
                        FALLBACKS["elsevier"](paper_metadata, output_path, api_keys)
            else:
                with open(output_path.with_suffix(".pdf"), "wb+") as f:
                    f.write(response.content)
        except Exception as e:
            logger.warning(f"Could not download {pdf_url}: {e}")
    else:  # if no citation_pdf_url meta tag found, try other fallbacks
        if "elife" in doi.lower():
            logger.info(
                "DOI contains eLife, attempting fallback to eLife XML repository on GitHub."
            )
            if not FALLBACKS["elife"](doi, output_path):
                logger.warning(
                    f"eLife XML fallback failed for {paper_metadata['doi']}."
                )
        elif (
            api_keys and "ELSEVIER_TDM_API_KEY" in api_keys
        ):  # elsevier journals can be accessed via the Elsevier TDM API (requires API key)
            FALLBACKS["elsevier"](paper_metadata, output_path, api_keys)
        else:
            logger.warning(
                f"Retrieval failed. No citation_pdf_url meta tag found for {url} and no applicable fallback mechanism available."
            )

    if not save_metadata:
        return

    metadata = {}
    # Extract title
    title_tag = soup.find("meta", {"name": "citation_title"})
    metadata["title"] = title_tag.get("content") if title_tag else "Title not found"

    # Extract authors
    authors = []
    for author_tag in soup.find_all("meta", {"name": "citation_author"}):
        if author_tag.get("content"):
            authors.append(author_tag["content"])
    metadata["authors"] = authors if authors else ["Author information not found"]

    # Extract abstract
    domain = tldextract.extract(url).domain
    abstract_keys = ABSTRACT_ATTRIBUTE.get(domain, DEFAULT_ATTRIBUTES)

    for key in abstract_keys:
        abstract_tag = soup.find("meta", {"name": key})
        if abstract_tag:
            raw_abstract = BeautifulSoup(
                abstract_tag.get("content", "None"), "html.parser"
            ).get_text(separator="\n")
            if raw_abstract.strip().startswith("Abstract"):
                raw_abstract = raw_abstract.strip()[8:]
            metadata["abstract"] = raw_abstract.strip()
            break

    if "abstract" not in metadata.keys():
        metadata["abstract"] = "Abstract not found"
        logger.warning(f"Could not find abstract for {url}")
    elif metadata["abstract"].endswith("..."):
        logger.warning(f"Abstract truncated from {url}")

    # Save metadata to JSON
    try:
        with open(output_path.with_suffix(".json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Failed to save metadata to {str(output_path)}: {e}")


def save_pdf_from_dump(
    dump_path: str,
    pdf_path: str,
    key_to_save: str = "doi",
    save_metadata: bool = False,
    api_keys: Optional[str] = None,
) -> None:
    """
    Receives a path to a `.jsonl` dump with paper metadata and saves the PDF files of
    each paper.

    Args:
        dump_path: Path to a `.jsonl` file with paper metadata, one paper per line.
        pdf_path: Path to a folder where the files will be stored.
        key_to_save: Key in the paper metadata to use as filename.
            Has to be `doi` or `title`. Defaults to `doi`.
        save_metadata: A boolean indicating whether to save paper metadata as a separate json.
        api_keys: Path to a file with API keys. If None, API-based fallbacks will be skipped.
    """

    if not isinstance(dump_path, str):
        raise TypeError(f"dump_path must be a string, not {type(dump_path)}.")
    if not dump_path.endswith(".jsonl"):
        raise ValueError("Please provide a dump_path with .jsonl extension.")

    if not isinstance(pdf_path, str):
        raise TypeError(f"pdf_path must be a string, not {type(pdf_path)}.")

    if not isinstance(key_to_save, str):
        raise TypeError(f"key_to_save must be a string, not {type(key_to_save)}.")
    if key_to_save not in ["doi", "title", "date"]:
        raise ValueError("key_to_save must be one of 'doi' or 'title'.")

    papers = load_jsonl(dump_path)

    if not isinstance(api_keys, dict):
        api_keys = load_api_keys(api_keys)

    pbar = tqdm(papers, total=len(papers), desc="Processing")
    for i, paper in enumerate(pbar):
        pbar.set_description(f"Processing paper {i + 1}/{len(papers)}")

        if "doi" not in paper.keys() or paper["doi"] is None:
            logger.warning(f"Skipping {paper['title']} since no DOI available.")
            continue
        filename = paper[key_to_save].replace("/", "_")
        pdf_file = Path(os.path.join(pdf_path, f"{filename}.pdf"))
        xml_file = pdf_file.with_suffix(".xml")
        if pdf_file.exists():
            logger.info(f"File {pdf_file} already exists. Skipping download.")
            continue
        if xml_file.exists():
            logger.info(f"File {xml_file} already exists. Skipping download.")
            continue
        output_path = str(pdf_file)
        save_pdf(paper, output_path, save_metadata=save_metadata, api_keys=api_keys)
