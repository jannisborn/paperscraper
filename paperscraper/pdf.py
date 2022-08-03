"""Functionalities to scrape PDF files of publications."""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .utils import load_jsonl

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def save_pdf(paper_metadata: Dict[str, Any], filepath: str) -> None:
    """
    Save a PDF file of a paper.

    Args:
        paper_metadata (Dict[str, Any]): A dictionary with the paper metadata. Must
            contain the `doi` key.
        filepath (str): Path to the file to be saved.
    """
    if not isinstance(paper_metadata, Dict):
        raise TypeError(f"paper_metadata must be a dict, not {type(paper_metadata)}.")
    if "doi" not in paper_metadata.keys():
        raise KeyError("paper_metadata must contain the key 'doi'.")
    if not isinstance(filepath, str):
        raise TypeError(f"filepath must be a string, not {type(filepath)}.")
    if not filepath.endswith(".pdf"):
        raise ValueError("Please provide a filepath with .pdf extension.")
    if not Path(filepath).parent.exists():
        raise ValueError(f"The folder: {Path(filepath).parent} seems to not exist.")

    url = f"https://doi.org/{paper_metadata['doi']}"
    try:
        response = requests.get(url)
    except Exception:
        logger.warning(f"Could not download {url}.")
        return

    soup = BeautifulSoup(response.text, features="lxml")

    metas = soup.find("meta", {"name": "citation_pdf_url"})
    if metas is None:
        logger.warning(
            f"Could not find PDF for: {url} (either there's a paywall or the host "
            "blocks PDF scraping)."
        )
        return
    pdf_url = metas.attrs.get("content")

    try:
        response = requests.get(pdf_url)
    except Exception:
        logger.warning(f"Could not download {pdf_url}.")
        return
    with open(filepath, "wb+") as f:
        f.write(response.content)


def save_pdf_from_dump(dump_path: str, pdf_path: str, key_to_save: str = "doi") -> None:
    """
    Receives a path to a `.jsonl` dump with paper metadata and saves the PDF files of
    each paper.

    Args:
        dump_path: Path to a `.jsonl` file with paper metadata, one paper per line.
        pdf_path: Path to a folder where the files will be stored.
        key_to_save: Key in the paper metadata to use as filename.
            Has to be `doi` or `title`. Defaults to `doi`.
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

    pbar = tqdm(papers, total=len(papers), desc="Processing")
    for i, paper in enumerate(pbar):
        pbar.set_description(f"Processing paper {i+1}/{len(papers)}")

        if "doi" not in paper.keys() or paper["doi"] is None:
            logger.warning(f"Skipping {paper['title']} since no DOI available.")
            continue
        filename = paper[key_to_save].replace("/", "_")
        save_pdf(paper, os.path.join(pdf_path, f"{filename}.pdf"))
