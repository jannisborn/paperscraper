"""Functionalities to scrape PDF files of publications."""

import calendar
import datetime
import io
import logging
import re
import sys
import threading
import time
import zipfile
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Dict, Union
import threading
from collections import deque

import boto3
import requests
from botocore.client import BaseClient
from botocore.config import Config
from lxml import etree

ELIFE_XML_INDEX = None  # global variable to cache the eLife XML index from GitHub

logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


class WileyRateLimiter:
    """
    Smart rate limiter for Wiley API that handles both:
    - 3 articles per second
    - 60 requests per 10 minutes

    Uses a token bucket approach for efficient rate limiting.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Token bucket for per-second limit (3 tokens, refill 3 per second)
        self._per_second_tokens = 3.0
        self._per_second_capacity = 3.0
        self._per_second_refill_rate = 3.0  # tokens per second
        self._last_refill = time.time()

        # Sliding window for 10-minute limit (60 requests per 600 seconds)
        self._request_times = deque()
        self._ten_minute_limit = 60
        self._ten_minute_window = 600  # seconds

    def acquire(self) -> float:
        """
        Acquire permission to make a request.
        Returns the time to wait before making the request (0 if immediate).
        """
        with self._lock:
            now = time.time()

            # Refill per-second tokens based on elapsed time
            elapsed = now - self._last_refill
            self._per_second_tokens = min(
                self._per_second_capacity,
                self._per_second_tokens + elapsed * self._per_second_refill_rate
            )
            self._last_refill = now

            # Clean old requests from 10-minute window
            cutoff = now - self._ten_minute_window
            while self._request_times and self._request_times[0] < cutoff:
                self._request_times.popleft()

            # Check 10-minute limit
            if len(self._request_times) >= self._ten_minute_limit:
                # Calculate how long to wait for oldest request to expire
                wait_time = self._request_times[0] + self._ten_minute_window - now
                return max(0, wait_time)

            # Check per-second limit
            if self._per_second_tokens < 1.0:
                # Calculate how long to wait for next token
                wait_time = (1.0 - self._per_second_tokens) / self._per_second_refill_rate
                return wait_time

            # Consume tokens and record request
            self._per_second_tokens -= 1.0
            self._request_times.append(now)

            return 0.0


# Global rate limiter instance
_wiley_rate_limiter = WileyRateLimiter()


def fallback_wiley_api(
    paper_metadata: Dict[str, Any],
    output_path: Path,
    api_keys: Dict[str, str],
    max_attempts: int = 2,
) -> bool:
    """
    Attempt to download the PDF via the Wiley TDM API with smart rate limiting.

    Implements proper rate limiting for:
    - up to 3 articles per second
    - up to 60 requests per 10 minutes

    Uses token bucket algorithm for efficient handling of rate limits.

    Args:
        paper_metadata (dict): Dictionary containing paper metadata. Must include the 'doi' key.
        output_path (Path): A pathlib.Path object representing the path where the PDF will be saved.
        api_keys (dict): Preloaded API keys.
        max_attempts (int): The maximum number of attempts to retry API call.

    Returns:
        bool: True if the PDF file was successfully downloaded, False otherwise.
    """

    WILEY_TDM_API_TOKEN = api_keys.get("WILEY_TDM_API_TOKEN")
    if not WILEY_TDM_API_TOKEN:
        logger.info("No Wiley API token found, skipping Wiley fallback.")
        return False

    encoded_doi = paper_metadata["doi"].replace("/", "%2F")
    api_url = f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{encoded_doi}"
    headers = {"Wiley-TDM-Client-Token": WILEY_TDM_API_TOKEN}

    attempt = 0
    success = False

    while attempt < max_attempts:
        try:
            # Smart rate limiting - wait if necessary
            wait_time = _wiley_rate_limiter.acquire()
            if wait_time > 0:
                logger.info(f"Wiley API rate limit: waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)

            api_response = requests.get(
                api_url, headers=headers, allow_redirects=True, timeout=60
            )
            api_response.raise_for_status()

            if api_response.content[:4] != b"%PDF":
                logger.warning(
                    f"Wiley API returned content that is not a valid PDF for {paper_metadata['doi']}."
                )
            else:
                with open(output_path.with_suffix(".pdf"), "wb+") as f:
                    f.write(api_response.content)
                logger.info(
                    f"Successfully downloaded PDF via Wiley API for {paper_metadata['doi']}."
                )
                success = True
                break

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit exceeded
                # If we hit rate limit despite our limiter, wait longer
                retry_after = int(e.response.headers.get('Retry-After', 30))
                logger.warning(f"Wiley API rate limit hit, waiting {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                logger.error(f"Wiley API HTTP error (attempt {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(5)  # Brief pause before retry
        except Exception as e:
            logger.error(f"Wiley API error (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(5)  # Brief pause before retry

        attempt += 1

    return success


def fallback_bioc_pmc(doi: str, output_path: Path, ncbi_email="your_email@example.com") -> bool:
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
        max_attempts (int): Maximum number of attempts for rate-limited API calls.
        retry_sleep (int): Base sleep duration between retry attempts.

    Returns:
        bool: True if the XML file was successfully downloaded, False otherwise.
    """
    ncbi_tool = "paperscraper"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    converter_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    params = {
        "tool": ncbi_tool,
        "email": ncbi_email,
        "ids": doi,
        "idtype": "doi",
        "format": "json",
    }
    try:
        conv_response = requests.get(converter_url, params=params, headers=headers, timeout=60)
        conv_response.raise_for_status()
        data = conv_response.json()
        records = data.get("records", [])
        if not records or "pmcid" not in records[0]:
            logger.warning(
                f"No PMCID available for DOI {doi}. Fallback via PMC therefore not possible."
            )
            time.sleep(retry_sleep * attempt)
        except Exception as conv_err:
            logger.error(f"Error during DOI to PMCID conversion: {conv_err}")
            return False

    # Construct PMC XML URL
    xml_url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmcid}/unicode"
    logger.info(f"Attempting to download XML from BioC-PMC URL: {xml_url}")
    for attempt in range(1, max_attempts + 1):
        try:
            xml_response = requests.get(xml_url, timeout=60)
            if xml_response.status_code == 429:
                raise NCBIRateLimitError(
                    f"NCBI rate-limited BioC-PMC XML download for {doi}"
                )
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
        except NCBIRateLimitError as xml_err:
            if attempt == max_attempts:
                logger.error(
                    f"Failed to download XML from BioC-PMC URL {xml_url}: {xml_err}"
                )
                return False
            logger.info(
                f"NCBI rate limit hit during BioC-PMC XML download "
                f"(attempt {attempt}/{max_attempts}); retrying"
            )
            time.sleep(retry_sleep * attempt)
        except Exception as xml_err:
            logger.error(
                f"Failed to download XML from BioC-PMC URL {xml_url}: {xml_err}"
            )
            return False


def fallback_elsevier_api(
    paper_metadata: Dict[str, Any],
    output_path: Path,
    api_keys: Dict[str, str],
    preferred_type: str = "xml",
) -> bool:
    """
    Attempt to download the full text via the Elsevier TDM API.
    For more information, see:
    https://www.elsevier.com/about/policies-and-standards/text-and-data-mining
    (Requires an institutional subscription and an API key provided in the api_keys dictionary under the key "ELSEVIER_TDM_API_KEY".)

    Args:
        paper_metadata (Dict[str, Any]): Dictionary containing paper metadata. Must include the 'doi' key.
        output_path (Path): A pathlib.Path object representing the path where the file will be saved.
        api_keys (Dict[str, str]): A dictionary containing API keys. Must include the key "ELSEVIER_TDM_API_KEY".
        preferred_type (str): The preferred file type to download, either "xml" or "pdf". Defaults to "xml".

    Returns:
        bool: True if the file was successfully downloaded, False otherwise.
    """
    elsevier_api_key = api_keys.get("ELSEVIER_TDM_API_KEY")
    if not elsevier_api_key:
        logger.info("No Elsevier API key found, skipping Elsevier fallback.")
        return False

    if preferred_type not in ["xml", "pdf"]:
        logger.warning(
            f"Invalid preferred_type '{preferred_type}'. Defaulting to 'xml'."
        )
        preferred_type = "xml"

    doi = paper_metadata["doi"]
    api_url = f"https://api.elsevier.com/content/article/doi/{doi}"
    accept_header = (
        "application/xml" if preferred_type == "xml" else "application/pdf"
    )
    headers = {"Accept": accept_header, "X-ELS-APIKey": elsevier_api_key}

    logger.info(
        f"Attempting download via Elsevier API ({preferred_type.upper()}) for {doi}"
    )

    try:
        response = requests.get(api_url, headers=headers, timeout=60)

        if response.status_code in [401, 403]:
            error_text = response.text
            if "APIKEY_INVALID" in error_text:
                logger.error(
                    "Invalid API key. Couldn't download via Elsevier API."
                )
            else:
                logger.error(
                    f"{response.status_code} Unauthorized/Forbidden. Couldn't download via Elsevier API."
                )
            return False

        response.raise_for_status()

        content = response.content
        file_path = output_path.with_suffix(f".{preferred_type}")

        if preferred_type == "xml":
            try:
                etree.fromstring(content)
            except etree.XMLSyntaxError as e:
                logger.warning(
                    f"Elsevier API returned invalid XML for {doi}: {e}"
                )
                return False
        elif preferred_type == "pdf":
            if not content.startswith(b"%PDF"):
                logger.warning(
                    f"Elsevier API did not return a valid PDF for {doi}."
                )
                return False

        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(
            f"Successfully downloaded {preferred_type.upper()} via Elsevier API for {doi} to {file_path}"
        )
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Could not download via Elsevier API for {doi}: {e}")
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
    if article_num in index:
        candidate_files = index[article_num]
        latest_version, latest_download_url = max(candidate_files, key=lambda x: x[0])
    else:
        candidate_files = _direct_elife_xml_candidates(article_num)
        if not candidate_files:
            logger.warning(f"No eLife XML found for DOI {doi}.")
            return False
        latest_version, latest_download_url = candidate_files[0]

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


def _direct_elife_xml_candidates(article_num: str) -> list:
    """
    Find versioned eLife XML files directly when the GitHub tree API is unavailable.
    """
    base_url = (
        "https://raw.githubusercontent.com/elifesciences/elife-article-xml/master"
    )
    candidates = []
    for version in range(1, 8):
        download_url = f"{base_url}/articles/elife-{article_num}-v{version}.xml"
        try:
            response = requests.head(download_url, allow_redirects=True, timeout=20)
            if response.status_code == 200:
                candidates.append((version, download_url))
        except requests.RequestException as e:
            logger.debug(f"Could not check eLife XML candidate {download_url}: {e}")
    return sorted(candidates, key=lambda x: x[0], reverse=True)


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
        for attempt in range(1, 4):
            try:
                r = requests.get(base_tree_url, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == 3:
                    logger.error(f"Could not fetch eLife XML index from GitHub: {e}")
                    return ELIFE_XML_INDEX
                logger.info("Retrying eLife XML index fetch from GitHub...")
                time.sleep(2 * attempt)
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


def list_meca_keys(s3_client: BaseClient, bucket: str, prefix: str) -> list:
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


def _try_download_pdf_from_meca(
    s3_client: BaseClient, bucket: str, key: str, out_pdf: Path, stop: threading.Event
) -> bool:
    """
    Download a MECA object and extract the first PDF found into out_pdf.

    Args:
        s3_client: S3 client to get the data from.
        bucket: bucket to get data from.
        key: prefix to get data from.
        out_pdf: Where the PDF should be saved to.

    Returns:
        True on success, False otherwise.
    """
    if stop.is_set():
        return False
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key, RequestPayer="requester")
        data = obj["Body"].read()
    except Exception as e:
        logger.debug(f"Failed to GET {key}: {e}")
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.lower().endswith(".pdf"):
                    out_pdf.parent.mkdir(parents=True, exist_ok=True)
                    z.extract(name, path=out_pdf.parent)
                    (out_pdf.parent / name).rename(out_pdf)
                    return True
    except Exception as e:
        logger.debug(f"Failed to read MECA zip {key}: {e}")
        return False
    return False


def find_meca_for_doi(
    s3_client: BaseClient,
    bucket: str,
    key: str,
    doi_token: str,
    stop_event: threading.Event,
    tail_bytes: int = 131072,
) -> bool:
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

    if stop_event.is_set():
        return False

    try:
        # Try tail-only first (central directory is at end)
        tail = s3_client.get_object(
            Bucket=bucket,
            Key=key,
            Range=f"bytes=-{tail_bytes}",
            RequestPayer="requester",
        )["Body"].read()
    except Exception:
        return False

    if stop_event.is_set():
        return False

    data = tail
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            # avoid reading file contents; inspect namelist/central directory
            for name in z.namelist():
                if name.endswith("manifest.xml"):
                    manifest = z.read(name)  # small file in practice
                    token = doi_token.split(".")[-1].encode("utf-8")
                    return token in manifest.lower()
    except zipfile.BadZipFile:
        # Fallback: fetch small head slice & retry zip
        try:
            head = s3_client.get_object(
                Bucket=bucket, Key=key, Range="bytes=0-65535", RequestPayer="requester"
            )["Body"].read()
            with zipfile.ZipFile(io.BytesIO(head + tail)) as z:
                manifest = z.read("manifest.xml")
                token = doi_token.split(".")[-1].encode("utf-8")
                return token in manifest.lower()
        except Exception:
            return False
    return False


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
        config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 3}),
    )
    bucket = "biorxiv-src-monthly"

    # Derive prefix from DOI date
    prefix = f"Current_Content/{month_folder(doi)}/"

    # List MECA archives in that month
    meca_keys = list_meca_keys(s3, bucket, prefix)
    if not meca_keys:
        return False

    token = doi.split("/")[-1].lower()

    # Prefer keys that already contain the token
    candidate_keys = [k for k in meca_keys if token in k.lower()]
    # If none contain the token (older DOIs, etc.), fall back to a small prefix scan
    if not candidate_keys:
        candidate_keys = meca_keys[: min(500, len(meca_keys))]
    out_pdf = Path(output_path).with_suffix(".pdf")

    # Try candidates concurrently but keep at most `workers` in flight.
    stop = threading.Event()

    def job(k):
        ok = _try_download_pdf_from_meca(s3, bucket, k, out_pdf, stop)
        if ok:
            stop.set()
        return ok

    executor = ThreadPoolExecutor(max_workers=workers)
    found = False
    try:
        it = iter(candidate_keys)
        # prime the queue with at most `workers` tasks
        futures = set()
        for _ in range(min(workers, len(candidate_keys))):
            k = next(it, None)
            if k is not None:
                futures.add(executor.submit(job, k))

        while futures and not found:
            done, futures = wait(futures, return_when=FIRST_COMPLETED)
            # check completed ones
            for fut in done:
                try:
                    if fut.result():
                        found = True
                        stop.set()
                        # cancel not-yet-started tasks
                        for f in list(futures):
                            f.cancel()
                        break
                except Exception:
                    pass
            # top up queue if still searching
            while not found and len(futures) < workers:
                k = next(it, None)
                if k is None:
                    break
                futures.add(executor.submit(job, k))
    finally:
        # don't wait for running tasks; best-effort cancel
        executor.shutdown(wait=False, cancel_futures=True)

    if not found:
        logger.error(f"Could not find {doi} on biorxiv")
        return False
    return True


def fallback_unpaywall(doi: str, output_path: Union[str,Path], mail: str, final_url: str) -> bool:
    """
    Attempt to download the PDF via Unpaywall.
    Unpaywall is a service that finds open access versions of paywalled articles.
    Args:
        doi (str): The DOI of the paper to retrieve.
        output_path (Path): A pathlib.Path object representing the path where the PDF will be saved.
        mail (str): Email address to use for Unpaywall API requests.
        final_url (str): The redirected URL of the DOI
    Returns:
        bool: True if the PDF file was successfully downloaded, False otherwise.
    """
    if type(output_path) is str:
        output_path = Path(output_path)
    unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email={mail}"
    try:
        response = requests.get(unpaywall_url, timeout=60)
        response.raise_for_status()
        data = response.json()
        if not data.get("is_oa", False):
            logger.info(f"No open access version found for {doi} on Unpaywall.")
            return False
        pdf_url = data.get("best_oa_location", {}).get("url_for_pdf", None)
        if final_url== pdf_url:
            logger.info(f"Unpaywall returned the same URL as the redirected URL for {doi}")
            return False

        if pdf_url:
            pdf_response = requests.get(pdf_url, timeout=60)
            pdf_response.raise_for_status()
            if pdf_response.content[:4] == b"%PDF":
                with open(output_path.with_suffix(".pdf"), "wb+") as f:
                    f.write(pdf_response.content)
                logger.info(f"Successfully downloaded PDF via Unpaywall for {doi}.")
                return True
            else:
                logger.warning(f"Unpaywall URL for {doi} did not return a valid PDF.")
                return False
        else:
            logger.info(f"No open access PDF found on Unpaywall for {doi}.")
            return False
    except Exception as e:
        logger.warning(f"Error during Unpaywall fallback for {doi}: {e}")
        return False

def fallback_springer_api(
    paper_metadata: Dict[str, Any],
    output_path: Path,
    api_keys: Dict[str, str],
) -> bool:
    """
    Attempt to download the PDF via the Springer Nature API.
    This function uses the SPRINGER_API_KEY environment variable to authenticate.
    See https://dev.springernature.com/ for details on how to get an API key.
    Args:
        paper_metadata (dict): Dictionary containing paper metadata. Must include the 'doi' key.
        output_path (Path): A pathlib.Path object representing the path where the PDF will be saved.
        api_keys (dict): Preloaded API keys.
    Returns:
        bool: True if the PDF file was successfully downloaded, False otherwise.
    """
    springer_api_key = api_keys.get("SPRINGER_API_KEY")
    if not springer_api_key:
        logger.info("No Springer API key found, skipping Springer fallback.")
        return False

    doi = paper_metadata["doi"]
    # Try open access endpoint first
    api_url = f"https://api.springernature.com/openaccess/v2/json?q=doi:{doi}&api_key={springer_api_key}"
    try:
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get("records"):
            pdf_url = data["records"][0].get("url")
            if pdf_url:
                # The URL is often a list, take the first one which is usually the PDF
                if isinstance(pdf_url, list):
                    pdf_url = pdf_url[0]["url"]

                pdf_response = requests.get(pdf_url, timeout=60)
                pdf_response.raise_for_status()
                if pdf_response.content[:4] == b"%PDF":
                    with open(output_path.with_suffix(".pdf"), "wb+") as f:
                        f.write(pdf_response.content)
                    logger.info(f"Successfully downloaded PDF via Springer Open Access API for {doi}.")
                    return True

    except Exception as e:
        logger.info(f"Springer Open Access API failed for {doi}: {e}. Trying metadata API.")

    # Fallback to metadata API (TDM)
    api_url = f"https://api.springernature.com/metadata/v2/json?q=doi:{doi}&api_key={springer_api_key}"
    try:
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get("records"):
            pdf_url = data["records"][0].get("url")
            if pdf_url:
                if isinstance(pdf_url, list):
                    pdf_url = pdf_url[0]["url"]

                pdf_response = requests.get(pdf_url, timeout=60)
                pdf_response.raise_for_status()
                if pdf_response.content[:4] == b"%PDF":
                    with open(output_path.with_suffix(".pdf"), "wb+") as f:
                        f.write(pdf_response.content)
                    logger.info(f"Successfully downloaded PDF via Springer Metadata API for {doi}.")
                    return True
    except Exception as e:
        logger.error(f"Could not download via Springer API for {doi}: {e}")

    return False


def fallback_plos_api(doi: str, output_path: Path) -> bool:
    """
    Attempt to download the PDF from PLOS journals.
    PLOS articles are open access and their PDFs can often be downloaded directly.
    Args:
        doi (str): The DOI of the paper to retrieve.
        output_path (Path): A pathlib.Path object representing the path where the PDF will be saved.
    Returns:
        bool: True if the PDF file was successfully downloaded, False otherwise.
    """
    if "plos" not in doi.lower():
        return False
    try:
        # Construct the URL based on common PLOS URL patterns
        # e.g., https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0000001&type=printable
        journal_match = re.search(r'journal\.(\w+)', doi)
        if not journal_match:
            logger.warning(f"Could not determine PLOS journal from DOI: {doi}")
            return False
        journal_short_name = journal_match.group(1)
        # 'pone' is a special case, it maps to 'plosone' in the URL
        if journal_short_name == 'pone':
            journal_name = 'plosone'
        else:
            journal_name = f'plos{journal_short_name}'

        pdf_url = f"https://journals.plos.org/{journal_name}/article/file?id={doi}&type=printable"

        pdf_response = requests.get(pdf_url, timeout=60)
        pdf_response.raise_for_status()
        if pdf_response.content[:4] == b"%PDF":
            with open(output_path.with_suffix(".pdf"), "wb+") as f:
                f.write(pdf_response.content)
            logger.info(f"Successfully downloaded PDF from PLOS for {doi}.")
            return True
        else:
            logger.warning(f"PLOS URL for {doi} did not return a valid PDF.")
            return False
    except Exception as e:
        logger.error(f"Error during PLOS fallback for {doi}: {e}")
        return False



def fallback_europepmc(doi: str, output_path: Path) -> bool:
    """
    Attempt to download the XML via Europe PMC.

    This function first converts a given DOI to a PMCID using the Europe PMC REST API.
    If a PMCID is found, it attempts to download the full-text XML from Europe PMC.

    Europe PMC is a repository of biomedical and life sciences literature that provides
    free access to abstracts and full-text articles.

    Args:
        doi (str): The DOI of the paper to retrieve.
        output_path (Path): A pathlib.Path object representing the path where the XML file will be saved.

    Returns:
        bool: True if the XML file was successfully downloaded, False otherwise.
    """
    # First, search for the article using DOI to get PMCID
    search_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    search_params = {
        "query": f'DOI:"{doi}"',
        "format": "json",
        "resultType": "core"
    }

    try:
        search_response = requests.get(search_url, params=search_params, timeout=60)
        search_response.raise_for_status()
        search_data = search_response.json()

        results = search_data.get("resultList", {}).get("result", [])
        if not results:
            logger.warning(f"No results found for DOI {doi} in Europe PMC.")
            return False

        # Search through all results to find one with a PMCID
        pmcid = None
        for result in results:
            candidate_pmcid = result.get("pmcid")
            if candidate_pmcid:
                pmcid = candidate_pmcid
                logger.info(f"Found PMCID {pmcid} for DOI {doi} in Europe PMC (result {results.index(result) + 1} of {len(results)}).")
                break

        if not pmcid:
            logger.warning(f"No PMCID available for DOI {doi} in Europe PMC (searched {len(results)} results).")
            return False

    except Exception as search_err:
        logger.error(f"Error searching Europe PMC for DOI {doi}: {search_err}")
        return False

    # Download full-text XML using PMCID
    xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"

    try:
        xml_response = requests.get(xml_url, timeout=60)
        xml_response.raise_for_status()

        # Check if we got valid XML content
        xml_content = xml_response.content
        if xml_content.startswith(b"<?xml") or xml_content.startswith(b"<"):
            xml_path = output_path.with_suffix(".xml")
            with open(xml_path, "wb") as f:
                f.write(xml_content)
            logger.info(f"Successfully downloaded XML from Europe PMC for DOI {doi} to {xml_path}.")
            return True
        else:
            logger.warning(f"Europe PMC did not return valid XML for DOI {doi}.")
            return False

    except Exception as xml_err:
        logger.error(f"Failed to download XML from Europe PMC for DOI {doi}: {xml_err}")
        return False

from urllib.parse import quote

def fallback_openalex(doi: str, output_path: Path) -> bool:
    """
    Use OpenAlex to locate an OA PDF for a DOI.
    https://api.openalex.org/works/doi:{doi}
    """
    try:
        url = f"https://api.openalex.org/works/doi:{quote(doi)}"
        r = requests.get(url, timeout=60)
        if r.status_code == 404:
            logger.info(f"OpenAlex: no record for {doi}")
            return False
        r.raise_for_status()
        data = r.json()

        best = data.get("best_oa_location") or {}
        pdf_url = best.get("pdf_url")
        if not pdf_url:
            # Fallbacks: try other locations OpenAlex exposes
            primary = data.get("primary_location") or {}
            pdf_url = primary.get("pdf_url") or (best.get("landing_page_url") if best.get("is_oa") else None)

        if not pdf_url:
            logger.info(f"OpenAlex: no OA PDF for {doi}")
            return False

        pdf = requests.get(pdf_url, timeout=60)
        pdf.raise_for_status()
        if not pdf.content.startswith(b"%PDF"):
            logger.warning(f"OpenAlex PDF URL did not return a PDF for {doi}")
            return False

        with open(output_path.with_suffix(".pdf"), "wb") as f:
            f.write(pdf.content)
        logger.info(f"Successfully downloaded PDF via OpenAlex for {doi}.")
        return True
    except Exception as e:
        logger.error(f"OpenAlex fallback failed for {doi}: {e}")
        return False


def fallback_crossref_links(doi: str, output_path: Path, contact_email: str = "your_email@example.com") -> bool:
    """
    Use Crossref /works to find publisher-provided text-mining PDF links.
    Prefers links with intended-application='text-mining' and content-type='application/pdf'.
    """
    try:
        url = f"https://api.crossref.org/works/{quote(doi)}"
        headers = {"User-Agent": f"paperscraper (mailto:{contact_email})"}
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        msg = r.json().get("message", {})
        links = msg.get("link", []) or []

        # Prioritize text-mining PDF links, then any PDF links
        def score(link: dict) -> tuple:
            return (
                0 if link.get("intended-application") == "text-mining" else 1,
                0 if link.get("content-type") == "application/pdf" else 1,
            )

        links = sorted(links, key=score)
        for link in links:
            if link.get("content-type") != "application/pdf":
                continue
            pdf_url = link.get("URL")
            if not pdf_url:
                continue
            try:
                pdf = requests.get(pdf_url, headers=headers, timeout=60)
                pdf.raise_for_status()
                if pdf.content.startswith(b"%PDF"):
                    with open(output_path.with_suffix(".pdf"), "wb") as f:
                        f.write(pdf.content)
                    logger.info(f"Successfully downloaded PDF via Crossref link for {doi}.")
                    return True
            except Exception as sub_e:
                logger.info(f"Crossref link failed for {doi}: {sub_e}")
        logger.info(f"Crossref: no usable PDF links for {doi}.")
        return False
    except Exception as e:
        logger.error(f"Crossref fallback failed for {doi}: {e}")
        return False


def fallback_arxiv(doi: str, output_path: Path) -> bool:
    """
    If an arXiv preprint is associated with the DOI, fetch the arXiv PDF.
    """
    try:
        # arXiv Atom API supports DOI query
        q = quote(f'doi:"{doi}"')
        url = f"http://export.arxiv.org/api/query?search_query={q}&max_results=1"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        root = etree.fromstring(r.content)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry_id = root.find(".//a:entry/a:id", namespaces=ns)
        if entry_id is None or not entry_id.text:
            logger.info(f"arXiv: no entry for DOI {doi}")
            return False
        abs_url = entry_id.text.strip()
        if "/abs/" not in abs_url:
            logger.info(f"arXiv: unexpected entry URL for {doi}: {abs_url}")
            return False
        pdf_url = abs_url.replace("/abs/", "/pdf/") + ".pdf"
        pdf = requests.get(pdf_url, timeout=60)
        pdf.raise_for_status()
        if not pdf.content.startswith(b"%PDF"):
            logger.warning(f"arXiv URL did not return a PDF for {doi}")
            return False
        with open(output_path.with_suffix(".pdf"), "wb") as f:
            f.write(pdf.content)
        logger.info(f"Successfully downloaded PDF via arXiv for {doi}.")
        return True
    except Exception as e:
        logger.error(f"arXiv fallback failed for {doi}: {e}")
        return False


def month_folder_medrxiv(doi: str) -> str:
    """
    Get medRxiv posting month folder, rolling over last-day postings to next month.
    """
    url = f"https://api.medrxiv.org/details/medrxiv/{doi}/na/json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    date_str = resp.json()["collection"][0]["date"]
    date = datetime.date.fromisoformat(date_str)
    last_day = calendar.monthrange(date.year, date.month)[1]
    if date.day == last_day:
        date = date + datetime.timedelta(days=1)
    return date.strftime("%B_%Y")


def fallback_medrxiv_s3(
    doi: str, output_path: Union[str, Path], api_keys: dict, workers: int = 32
) -> bool:
    """
    Download a medRxiv PDF via the requester-pays S3 bucket using range requests.
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=api_keys.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=api_keys.get("AWS_SECRET_ACCESS_KEY"),
        region_name="us-east-1",
    )
    bucket = "medrxiv-src-monthly"
    try:
        prefix = f"Current_Content/{month_folder_medrxiv(doi)}/"
    except Exception as e:
        logger.error(f"Could not resolve medRxiv month folder for {doi}: {e}")
        return False

    meca_keys = list_meca_keys(s3, bucket, prefix)
    if not meca_keys:
        logger.info(f"No MECA archives in {bucket}/{prefix} for {doi}")
        return False

    token = doi.split("/")[-1].lower()
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {executor.submit(find_meca_for_doi, s3, bucket, key, token): key for key in meca_keys}
    pbar = tqdm(total=len(futures), desc=f"Scanning in medrxiv with {workers} workers for {doi}…")
    target = None
    for fut in as_completed(futures):
        key = futures[fut]
        try:
            if fut.result():
                target = key
                pbar.set_description(f"Success! Found target {doi} in {key}")
                for other in futures:
                    other.cancel()
                break
        except Exception:
            pass
        finally:
            pbar.update(1)
    executor.shutdown(wait=False)
    if target is None:
        logger.error(f"Could not find {doi} on medrxiv")
        return False

    data = s3.get_object(Bucket=bucket, Key=target, RequestPayer="requester")["Body"].read()
    output_path = Path(output_path)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.lower().endswith(".pdf"):
                z.extract(name, path=output_path.parent)
                (output_path.parent / name).rename(output_path.with_suffix(".pdf"))
                return True
    return False


def fallback_doaj(doi: str, output_path: Path) -> bool:
    """
    Use DOAJ API to find fulltext links for OA articles.
    """
    try:
        url = f"https://doaj.org/api/v2/search/articles/doi:{quote(doi)}"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        results = r.json().get("results", []) or []
        for res in results:
            links = (res.get("bibjson", {}) or {}).get("link", []) or []
            for ln in links:
                if ln.get("type") != "fulltext":
                    continue
                pdf_url = ln.get("url")
                if not pdf_url:
                    continue
                try:
                    pdf = requests.get(pdf_url, timeout=60)
                    pdf.raise_for_status()
                    if not pdf.content.startswith(b"%PDF"):
                        continue
                    with open(output_path.with_suffix(".pdf"), "wb") as f:
                        f.write(pdf.content)
                    logger.info(f"Successfully downloaded PDF via DOAJ for {doi}.")
                    return True
                except Exception:
                    continue
        logger.info(f"DOAJ: no usable fulltext PDF for {doi}.")
        return False
    except Exception as e:
        logger.error(f"DOAJ fallback failed for {doi}: {e}")
        return False



FALLBACKS: Dict[str, Callable] = {
    "bioc_pmc": fallback_bioc_pmc,
    "elife": fallback_elife_xml,
    "elsevier": fallback_elsevier_api,
    "europepmc": fallback_europepmc,
    "s3": fallback_s3,
    "wiley": fallback_wiley_api,
    "unpaywall": fallback_unpaywall,
    "springer": fallback_springer_api,
    "plos": fallback_plos_api,
    "openalex": fallback_openalex,
    "crossref": fallback_crossref_links,
    "arxiv": fallback_arxiv,
    "medrxiv_s3": fallback_medrxiv_s3,
    "doaj": fallback_doaj,
}
