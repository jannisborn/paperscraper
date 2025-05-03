"""Functionalities to scrape PDF files of publications."""

import calendar
import datetime
import io
import logging
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, Union

import boto3
import requests
from lxml import etree
from tqdm import tqdm

ELIFE_XML_INDEX = None  # global variable to cache the eLife XML index from GitHub

logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


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
        bool: True if the PDF file was successfully downloaded, False otherwise.
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
        bool: True if the XML file was successfully downloaded, False otherwise.
    """
    elsevier_api_key = api_keys.get("ELSEVIER_TDM_API_KEY")
    doi = paper_metadata["doi"]
    api_url = f"https://api.elsevier.com/content/article/doi/{doi}?apiKey={elsevier_api_key}&httpAccept=text%2Fxml"
    logger.info(f"Attempting download via Elsevier API (XML) for {doi}: {api_url}")
    headers = {"Accept": "application/xml"}
    try:
        response = requests.get(api_url, headers=headers, timeout=60)

        # Check for 401 error and look for APIKEY_INVALID in the response
        if response.status_code == 401:
            error_text = response.text
            if "APIKEY_INVALID" in error_text:
                logger.error("Invalid API key. Couldn't download via Elsevier XML API")
            else:
                logger.error("401 Unauthorized. Couldn't download via Elsevier XML API")
            return False

        response.raise_for_status()

        # Attempt to parse it with lxml to confirm it's valid XML
        try:
            etree.fromstring(response.content)
        except etree.XMLSyntaxError as e:
            logger.warning(f"Elsevier API returned invalid XML for {doi}: {e}")
            return False

        xml_path = output_path.with_suffix(".xml")
        with open(xml_path, "wb") as f:
            f.write(response.content)
        logger.info(
            f"Successfully used Elsevier API to downloaded XML for {doi} to {xml_path}"
        )
        return True
    except Exception as e:
        logger.error(f"Could not download via Elsevier XML API: {e}")
        return False


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


def month_folder(doi: str) -> str:
    """
    Query bioRxiv API to get the posting date of a given DOI.
    Convert a date to the BioRxiv S3 folder name, rolling over if it's the month's last day.
    E.g., if date is the last day of April, treat as May_YYYY.

    Args:
        doi: The DOI for which to retrieve the date.

    Returns:
        Month and year in format `October_2019`
    """
    url = f"https://api.biorxiv.org/details/biorxiv/{doi}/na/json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    date_str = resp.json()["collection"][0]["date"]
    date = datetime.date.fromisoformat(date_str)

    # NOTE: bioRxiv papers posted on the last day of the month are archived the next day
    last_day = calendar.monthrange(date.year, date.month)[1]
    if date.day == last_day:
        date = date + datetime.timedelta(days=1)
    return date.strftime("%B_%Y")


def list_meca_keys(s3_client, bucket: str, prefix: str) -> list:
    """
    List all .meca object keys under a given prefix in a requester-pays bucket.

    Args:
        s3_client: S3 client to get the data from.
        bucket: bucket to get data from.
        prefix: prefix to get data from.

    Returns:
        List of keys, one per existing .meca in the bucket.
    """
    keys = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(
        Bucket=bucket, Prefix=prefix, RequestPayer="requester"
    ):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".meca"):
                keys.append(obj["Key"])
    return keys


def find_meca_for_doi(s3_client, bucket: str, key: str, doi_token: str) -> bool:
    """
    Efficiently inspect manifest.xml within a .meca zip by fetching only necessary bytes.
    Parse via ZipFile to read manifest.xml and match DOI token.

    Args:
        s3_client: S3 client to get the data from.
        bucket: bucket to get data from.
        key: prefix to get data from.
        doi_token: the DOI that should be matched

    Returns:
        Whether or not the DOI could be matched
    """
    try:
        head = s3_client.get_object(
            Bucket=bucket, Key=key, Range="bytes=0-4095", RequestPayer="requester"
        )["Body"].read()
        tail = s3_client.get_object(
            Bucket=bucket, Key=key, Range="bytes=-4096", RequestPayer="requester"
        )["Body"].read()
    except Exception:
        return False

    data = head + tail
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        manifest = z.read("manifest.xml")

    return doi_token.encode("utf-8") in manifest.lower()


def fallback_s3(
    doi: str, output_path: Union[str, Path], api_keys: dict, workers: int = 32
) -> bool:
    """
    Download a BioRxiv PDF via the requester-pays S3 bucket using range requests.

    Args:
        doi: The DOI for which to retrieve the PDF (e.g. '10.1101/798496').
        output_path: Path where the PDF will be saved (with .pdf suffix added).
        api_keys: Dict containing 'AWS_ACCESS_KEY_ID' and 'AWS_SECRET_ACCESS_KEY'.

    Returns:
        True if download succeeded, False otherwise.
    """

    s3 = boto3.client(
        "s3",
        aws_access_key_id=api_keys.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=api_keys.get("AWS_SECRET_ACCESS_KEY"),
        region_name="us-east-1",
    )
    bucket = "biorxiv-src-monthly"

    # Derive prefix from DOI date
    prefix = f"Current_Content/{month_folder(doi)}/"

    # List MECA archives in that month
    meca_keys = list_meca_keys(s3, bucket, prefix)
    if not meca_keys:
        return False

    token = doi.split("/")[-1].lower()
    target = None
    executor = ThreadPoolExecutor(max_workers=32)
    futures = {
        executor.submit(find_meca_for_doi, s3, bucket, key, token): key
        for key in meca_keys
    }
    target = None
    for future in tqdm(
        as_completed(futures),
        total=len(futures),
        desc=f"Scanning in biorxiv with {workers} workers for {doi}...",
    ):
        key = futures[future]
        try:
            if future.result():
                target = key
                # cancel pending futures to speed shutdown
                for fut in futures:
                    fut.cancel()
                break
        except Exception:
            continue
    # shutdown without waiting for remaining threads
    executor.shutdown(wait=False)
    if target is None:
        logger.error(f"Could not find {doi} on biorxiv")
        return False

    # Download full MECA and extract PDF
    data = s3.get_object(Bucket=bucket, Key=target, RequestPayer="requester")[
        "Body"
    ].read()
    output_path = Path(output_path)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.lower().endswith(".pdf"):
                z.extract(name, path=output_path.parent)
                # Move file to desired location
                (output_path.parent / name).rename(output_path.with_suffix(".pdf"))
                return True
    return False


FALLBACKS: Dict[str, Callable] = {
    "bioc_pmc": fallback_bioc_pmc,
    "elife": fallback_elife_xml,
    "elsevier": fallback_elsevier_api,
    "s3": fallback_s3,
    "wiley": fallback_wiley_api,
}
