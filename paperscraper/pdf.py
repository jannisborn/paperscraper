"""Functionalities to scrape PDF files of publications."""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

import requests
import tldextract
from bs4 import BeautifulSoup
from lxml import etree
from tqdm import tqdm

from .utils import load_jsonl

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
    filepath: str,
    save_metadata: bool = False,
    api_keys: Optional[Union[str, Dict[str, str]]] = None,
) -> None:
    """
    Save a PDF file of a paper.

    Args:
        paper_metadata: A dictionary with the paper metadata. Must
            contain the `doi` key.
        filepath: Path to the PDF file to be saved (with or without suffix).
        save_metadata: A boolean indicating whether to save paper metadata as a separate json.
        api_keys: Either a dictionary containing API keys (if already loaded) or a string (path to API keys file).
                  If None, API-based fallbacks will be skipped.
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
    if isinstance(api_keys, str):
        api_keys = load_api_keys(api_keys)

    url = f"https://doi.org/{paper_metadata['doi']}"
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
    except Exception as e:
        logger.warning(
            f"Could not download from: {url} - {e}. Attempting download via BioC-PMC fallback"
        )
        # always first try fallback to BioC-PMC (open access papers on PubMed Central)
        success = fallback_bioc_pmc(paper_metadata["doi"], output_path)

        # if BioC-PMC fails, try other fallbacks
        if not success:
            # check for specific publishers
            if "elife" in str(e).lower():  # elife has an open XML repository on GitHub
                if fallback_elife_xml(paper_metadata["doi"], output_path):
                    logger.info(
                        f"Successfully downloaded XML of paper via eLife fallback."
                    )
            elif (
                ("wiley" in str(e).lower())
                and api_keys
                and ("WILEY_TDM_API_TOKEN" in api_keys)
            ):
                fallback_wiley_api(paper_metadata, output_path, api_keys)
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
            else:
                with open(output_path.with_suffix(".pdf"), "wb+") as f:
                    f.write(response.content)
        except Exception as e:
            logger.warning(f"Could not download {pdf_url}: {e}")
    else:  # if no citation_pdf_url meta tag found, try other fallbacks
        if "elife" in paper_metadata["doi"].lower():
            logger.info(
                f"DOI contains eLife, attempting fallback to eLife XML repository on GitHub."
            )
            if not fallback_elife_xml(paper_metadata["doi"], output_path):
                logger.warning(
                    f"eLife XML fallback failed for {paper_metadata['doi']}."
                )
        elif (
            api_keys and "ELSEVIER_TDM_API_KEY" in api_keys
        ):  # elsevier journals can be accessed via the Elsevier TDM API (requires API key)
            fallback_elsevier_api(paper_metadata, output_path, api_keys)
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

    api_keys_dict = load_api_keys(api_keys) if api_keys else None

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
        save_pdf(
            paper, output_path, save_metadata=save_metadata, api_keys=api_keys_dict
        )


def load_api_keys(filepath: str) -> Dict[str, str]:
    """
    Reads API keys from a file and returns them as a dictionary.
    The file should have each API key on a separate line in the format:
        KEY_NAME=API_KEY_VALUE

    Example:
        WILEY_TDM_API_TOKEN=your_wiley_token_here
        ELSEVIER_TDM_API_KEY=your_elsevier_key_here

    Args:
        filepath (str): Path to the file containing API keys.

    Returns:
        Dict[str, str]: A dictionary where keys are API key names and values are their respective API keys.
    """
    api_keys = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    api_keys[key] = value
    except Exception as e:
        logger.error(f"Error reading API keys file: {e}")
    return api_keys


def fallback_wiley_api(
    paper_metadata: Dict[str, Any],
    output_path: Path,
    api_keys: Dict[str, str],
    max_attempts: int = 2,
) -> bool:
    """
    Attempt to download the PDF via the Wiley TDM API (popular publisher which blocks standard scraping attempts; API access free for academic users).

    This function uses the WILEY_TDM_API_TOKEN environment variable to authenticate
    with the Wiley TDM API and attempts to download the PDF for the given paper.
    See https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining for a description on how to get your WILEY_TDM_API_TOKEN.

    Args:
        paper_metadata (dict): Dictionary containing paper metadata. Must include the 'doi' key.
        output_path (Path): A pathlib.Path object representing the path where the PDF will be saved.
        api_keys (dict): Preloaded API keys.
        max_attempts (int): The maximum number of attempts to retry API call.

    Returns:
        Whether or not download was successful
    """

    WILEY_TDM_API_TOKEN = api_keys.get("WILEY_TDM_API_TOKEN")
    encoded_doi = paper_metadata["doi"].replace("/", "%2F")
    api_url = f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{encoded_doi}"
    headers = {"Wiley-TDM-Client-Token": WILEY_TDM_API_TOKEN}

    attempt = 0
    success = False

    while attempt < max_attempts:
        try:
            api_response = requests.get(
                api_url, headers=headers, allow_redirects=True, timeout=60
            )
            api_response.raise_for_status()
            if api_response.content[:4] != b"%PDF":
                logger.warning(
                    f"API returned content that is not a valid PDF for {paper_metadata['doi']}."
                )
            else:
                with open(output_path.with_suffix(".pdf"), "wb+") as f:
                    f.write(api_response.content)
                logger.info(
                    f"Successfully downloaded PDF via Wiley API for {paper_metadata['doi']}."
                )
                success = True
                break
        except Exception as e2:
            if attempt < max_attempts - 1:
                logger.info("Waiting 20 seconds before retrying...")
                time.sleep(20)
            logger.error(
                f"Could not download via Wiley API (attempt {attempt + 1}/{max_attempts}): {e2}"
            )

        attempt += 1

    # **Mandatory delay of 10 seconds to comply with Wiley API rate limits**
    logger.info(
        "Waiting 10 seconds before next request to comply with Wiley API rate limits..."
    )
    time.sleep(10)
    return success


def fallback_bioc_pmc(doi: str, output_path: Path) -> bool:
    """
    Attempt to download the XML via the BioC-PMC fallback.

    This function first converts a given DOI to a PMCID using the NCBI ID Converter API.
    If a PMCID is found, it constructs the corresponding PMC XML URL and attempts to
    download the full-text XML.

    PubMed Central® (PMC) is a free full-text archive of biomedical and life sciences
    journal literature at the U.S. National Institutes of Health's National Library of Medicine (NIH/NLM).

    Args:
        doi (str): The DOI of the paper to retrieve.
        output_path (Path): A pathlib.Path object representing the path where the XML file will be saved.

    Returns:
        bool: True if the XML file was successfully downloaded, False otherwise.
    """
    ncbi_tool = "paperscraper"
    ncbi_email = "your_email@example.com"

    converter_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    params = {
        "tool": ncbi_tool,
        "email": ncbi_email,
        "ids": doi,
        "idtype": "doi",
        "format": "json",
    }
    try:
        conv_response = requests.get(converter_url, params=params, timeout=60)
        conv_response.raise_for_status()
        data = conv_response.json()
        records = data.get("records", [])
        if not records or "pmcid" not in records[0]:
            logger.warning(
                f"No PMCID available for DOI {doi}. Fallback via PMC therefore not possible."
            )
            return False
        pmcid = records[0]["pmcid"]
        logger.info(f"Converted DOI {doi} to PMCID {pmcid}.")
    except Exception as conv_err:
        logger.error(f"Error during DOI to PMCID conversion: {conv_err}")
        return False

    # Construct PMC XML URL
    xml_url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmcid}/unicode"
    logger.info(f"Attempting to download XML from BioC-PMC URL: {xml_url}")
    try:
        xml_response = requests.get(xml_url, timeout=60)
        xml_response.raise_for_status()
        xml_path = output_path.with_suffix(".xml")
        # check for xml error:
        if xml_response.content.startswith(
            b"[Error] : No result can be found. <BR><HR><B> - https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/"
        ):
            logger.warning(f"No XML found for DOI {doi} at BioC-PMC URL {xml_url}.")
            return False
        with open(xml_path, "wb+") as f:
            f.write(xml_response.content)
        logger.info(f"Successfully downloaded XML for DOI {doi} to {xml_path}.")
        return True
    except Exception as xml_err:
        logger.error(f"Failed to download XML from BioC-PMC URL {xml_url}: {xml_err}")
        return False


def fallback_elsevier_api(
    paper_metadata: Dict[str, Any], output_path: Path, api_keys: Dict[str, str]
) -> bool:
    """
    Attempt to download the full text via the Elsevier TDM API.
    For more information, see:
    https://www.elsevier.com/about/policies-and-standards/text-and-data-mining
    (Requires an institutional subscription and an API key provided in the api_keys dictionary under the key "ELSEVIER_TDM_API_KEY".)

    Args:
        paper_metadata (Dict[str, Any]): Dictionary containing paper metadata. Must include the 'doi' key.
        output_path (Path): A pathlib.Path object representing the path where the XML file will be saved.
        api_keys (Dict[str, str]): A dictionary containing API keys. Must include the key "ELSEVIER_TDM_API_KEY".

    Returns:
        Whether the download was successful.
    """
    elsevier_api_key = api_keys.get("ELSEVIER_TDM_API_KEY")
    doi = paper_metadata["doi"]
    api_url = f"https://api.elsevier.com/content/article/doi/{doi}?apiKey={elsevier_api_key}&httpAccept=text%2Fxml"
    logger.info(f"Attempting download via Elsevier API (XML) for {doi}: {api_url}")
    headers = {"Accept": "application/xml"}
    success = False
    try:
        response = requests.get(api_url, headers=headers, timeout=60)
        response.raise_for_status()

        # Attempt to parse it with lxml to confirm it's valid XML
        try:
            etree.fromstring(response.content)
        except etree.XMLSyntaxError as e:
            logger.warning(f"Elsevier API returned invalid XML for {doi}: {e}")
            return

        xml_path = output_path.with_suffix(".xml")
        with open(xml_path, "wb") as f:
            f.write(response.content)
        logger.info(
            f"Successfully used Elsevier API to downloaded XML for {doi} to {xml_path}"
        )
        success = True

    except Exception as e:
        logger.error(f"Could not download via Elsevier XML API: {e}")
    return success


def fallback_elife_xml(doi: str, output_path: Path) -> bool:
    """
    Attempt to download the XML via the eLife XML repository on GitHub.

    eLife provides open access to their XML files on GitHub, which can be used as a fallback.
    When multiple versions exist (revised papers), it takes the latest version (e.g., v3 instead of v1).

    Args:
        doi (str): The DOI of the eLife paper to download.
        output_path (Path): A pathlib.Path object representing the path where the XML file will be saved.

    Returns:
        bool: True if the XML file was successfully downloaded, False otherwise.
    """
    parts = doi.split("eLife.")
    if len(parts) < 2:
        logger.error(f"Unable to parse eLife DOI: {doi}")
        return False
    article_num = parts[1].strip()

    index = get_elife_xml_index()
    if article_num not in index:
        logger.warning(f"No eLife XML found for DOI {doi}.")
        return False
    candidate_files = index[article_num]
    latest_version, latest_download_url = max(candidate_files, key=lambda x: x[0])
    try:
        r = requests.get(latest_download_url, timeout=60)
        r.raise_for_status()
        latest_xml = r.content
    except Exception as e:
        logger.error(f"Error downloading file from {latest_download_url}: {e}")
        return False

    xml_path = output_path.with_suffix(".xml")
    with open(xml_path, "wb") as f:
        f.write(latest_xml)
    logger.info(
        f"Successfully downloaded XML via eLife API ({latest_version}) for DOI {doi} to {xml_path}."
    )
    return True


ELIFE_XML_INDEX = None  # global variable to cache the eLife XML index from GitHub


def get_elife_xml_index() -> dict:
    """
    Fetch the eLife XML index from GitHub and return it as a dictionary.

    This function retrieves and caches the list of available eLife articles in XML format
    from the eLife GitHub repository. It ensures that the latest version of each article
    is accessible for downloading. The index is cached in memory to avoid repeated
    network requests when processing multiple eLife papers.

    Returns:
        dict: A dictionary where keys are article numbers (as strings) and values are
              lists of tuples (version, download_url). Each list is sorted by version number.
    """
    global ELIFE_XML_INDEX
    if ELIFE_XML_INDEX is None:
        logger.info("Fetching eLife XML index from GitHub using git tree API")
        ELIFE_XML_INDEX = {}
        # Use the git tree API to get the full repository tree.
        base_tree_url = "https://api.github.com/repos/elifesciences/elife-article-xml/git/trees/master?recursive=1"
        r = requests.get(base_tree_url, timeout=60)
        r.raise_for_status()
        tree_data = r.json()
        items = tree_data.get("tree", [])
        # Look for files in the 'articles' directory matching the pattern.
        pattern = r"articles/elife-(\d+)-v(\d+)\.xml"
        for item in items:
            path = item.get("path", "")
            match = re.match(pattern, path)
            if match:
                article_num_padded = match.group(1)
                version = int(match.group(2))
                # Construct the raw download URL.
                download_url = f"https://raw.githubusercontent.com/elifesciences/elife-article-xml/master/{path}"
                ELIFE_XML_INDEX.setdefault(article_num_padded, []).append(
                    (version, download_url)
                )
        # Sort each article's file list by version.
        for key in ELIFE_XML_INDEX:
            ELIFE_XML_INDEX[key].sort(key=lambda x: x[0])
    return ELIFE_XML_INDEX
