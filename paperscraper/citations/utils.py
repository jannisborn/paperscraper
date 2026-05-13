import asyncio
import logging
import os
import random
import re
import sys
import time
from typing import Dict, List, Literal, Optional, Tuple

import httpx
import requests
from tqdm import tqdm
from unidecode import unidecode

from ..async_utils import optional_async, retry_with_exponential_backoff

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

REQUEST_TIMEOUT_SECONDS = float(os.getenv("SS_REQUEST_TIMEOUT", "20"))
CONCURRENCY_LIMIT = max(1, int(os.getenv("SS_CONCURRENCY_LIMIT", "1")))
# Minimum delay between outbound requests to Semantic Scholar.
RATE_LIMIT_DELAY = max(0.0, float(os.getenv("SS_RATE_LIMIT_DELAY", "1.1")))

DOI_PATTERN = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"
PAPER_URL: str = "https://api.semanticscholar.org/graph/v1/paper/"
AUTHOR_URL: str = "https://api.semanticscholar.org/graph/v1/author/search"


SS_API_KEY = os.getenv("SS_API_KEY")
HEADERS: Dict[str, str] = {}
if SS_API_KEY:
    HEADERS["x-api-key"] = SS_API_KEY
_SEMANTIC_SCHOLAR_KEY_DISABLED = False

HTTPX_LIMITS = httpx.Limits(
    max_connections=CONCURRENCY_LIMIT, max_keepalive_connections=CONCURRENCY_LIMIT
)
REQUEST_SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)
_REQUEST_SCHEDULER_LOCK = asyncio.Lock()
_NEXT_REQUEST_TIME = 0.0


def disable_semantic_scholar_api_key() -> None:
    """
    Disable the configured Semantic Scholar API key after the API rejects it.
    """
    global _SEMANTIC_SCHOLAR_KEY_DISABLED
    if "x-api-key" not in HEADERS:
        return

    HEADERS.clear()
    _SEMANTIC_SCHOLAR_KEY_DISABLED = True
    logger.error(
        "Semantic Scholar rejected SS_API_KEY with HTTP 403 Forbidden. "
        "Continuing without the API key for subsequent requests."
    )


def semantic_scholar_key_disabled() -> bool:
    """
    Return whether the configured Semantic Scholar API key was disabled.
    """
    return _SEMANTIC_SCHOLAR_KEY_DISABLED


def _should_retry_without_key(status_code: int) -> bool:
    if status_code != 403 or "x-api-key" not in HEADERS:
        return False
    disable_semantic_scholar_api_key()
    return True


async def semantic_scholar_get(
    client: httpx.AsyncClient, url: str, **kwargs
) -> httpx.Response:
    """
    Perform a Semantic Scholar GET request and retry without a rejected API key.
    """
    response = await client.get(url, headers=HEADERS, **kwargs)
    if _should_retry_without_key(response.status_code):
        response = await client.get(url, headers=HEADERS, **kwargs)
    return response


def semantic_scholar_requests_get(url: str, **kwargs) -> requests.Response:
    """
    Perform a synchronous Semantic Scholar GET request and retry without a rejected API key.
    """
    response = requests.get(url, headers=HEADERS, **kwargs)
    if _should_retry_without_key(response.status_code):
        response = requests.get(url, headers=HEADERS, **kwargs)
    return response


def _semantic_scholar_requests_get_with_backoff(
    url: str,
    *,
    max_retries: int = 10,
    base_delay: float = 1.0,
    factor: float = 1.3,
    max_delay: float = 60.0,
    jitter_ratio: float = 0.1,
    **kwargs,
) -> requests.Response:
    """
    Synchronous GET with backoff for transient Semantic Scholar errors.

    Retries 429 / 408 / 5xx and respects Retry-After when present.
    """
    delay = base_delay
    last_exc: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            # Keep a minimum pacing between outbound requests.
            if RATE_LIMIT_DELAY > 0:
                time.sleep(RATE_LIMIT_DELAY)
            resp = semantic_scholar_requests_get(
                url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs
            )
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            sleep_for = min(delay, max_delay)
        else:
            if resp.status_code in (200, 201, 204):
                return resp

            retryable = (
                resp.status_code == 429
                or resp.status_code == 408
                or 500 <= resp.status_code <= 599
            )
            if not retryable:
                resp.raise_for_status()
                return resp

            sleep_for = min(delay, max_delay)
            ra = resp.headers.get("Retry-After")
            if ra is not None:
                try:
                    sleep_for = min(float(ra), max_delay)
                except ValueError:
                    pass

        if attempt == max_retries:
            raise RuntimeError(
                f"_semantic_scholar_requests_get_with_backoff failed after {attempt} attempts "
                f"with last delay {sleep_for:.2f}s"
            ) from last_exc

        delay = min(delay * factor, max_delay)
        if jitter_ratio > 0:
            jitter = sleep_for * jitter_ratio
            sleep_for = max(0.0, sleep_for + random.uniform(-jitter, jitter))
        time.sleep(sleep_for)

    raise RuntimeError("_semantic_scholar_requests_get_with_backoff: unreachable")


async def wait_for_request_slot() -> None:
    """
    Enforces global pacing between Semantic Scholar requests.
    Uses a shared scheduler to avoid bursts across modules.
    """
    global _NEXT_REQUEST_TIME

    async with _REQUEST_SCHEDULER_LOCK:
        now = time.monotonic()
        scheduled = max(_NEXT_REQUEST_TIME, now)
        _NEXT_REQUEST_TIME = scheduled + RATE_LIMIT_DELAY

    delay = scheduled - now
    if delay > 0:
        await asyncio.sleep(delay)


def get_doi_from_title(title: str) -> Optional[str]:
    """
    Searches the DOI of a paper based on the paper title

    Args:
        title: Paper title

    Returns:
        DOI according to semantic scholar API
    """
    response = semantic_scholar_requests_get(
        PAPER_URL + "search",
        params={"query": title, "fields": "externalIds", "limit": 1},
    )
    data = response.json()

    if data.get("data"):
        paper = data["data"][0]
        doi = paper.get("externalIds", {}).get("DOI")
        if doi:
            return doi
    logger.warning(f"Did not find DOI for title={title}")


def get_author_name_from_ssaid(ss_author_id: str) -> Optional[str]:
    """
    Given a Semantic Scholar author ID, return the author's name.
    """
    response = _semantic_scholar_requests_get_with_backoff(
        f"https://api.semanticscholar.org/graph/v1/author/{ss_author_id}",
        params={"fields": "name"},
    )
    data = response.json()
    return data.get("name")


@optional_async
async def get_doi_from_ssid(ssid: str, max_retries: int = 10) -> Optional[str]:
    """
    Given a Semantic Scholar paper ID, returns the corresponding DOI if available.

    Parameters:
      ssid (str): The paper ID on Semantic Scholar.

    Returns:
      str or None: The DOI of the paper, or None if not found or in case of an error.
    """
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS), limits=HTTPX_LIMITS
    ) as client:
        logger.warning(
            "Semantic Scholar API is easily overloaded when passing SS IDs, provide DOIs to improve throughput."
        )
        attempts = 0
        for attempt in tqdm(
            range(1, max_retries + 1), desc=f"Fetching DOI for {ssid}", unit="attempt"
        ):
            # Make the GET request to Semantic Scholar.
            response = await semantic_scholar_get(
                client,
                f"{PAPER_URL}{ssid}",
                params={"fields": "externalIds", "limit": 1},
            )

            # If successful, try to extract and return the DOI.
            if response.status_code == 200:
                data = response.json()
                doi = data.get("externalIds", {}).get("DOI")
                return doi
            attempts += 1
        logger.warning(
            f"Did not find DOI for paper ID {ssid}. Code={response.status_code}, text={response.text}"
        )


@optional_async
async def get_title_and_id_from_doi(doi: str) -> Dict[str, str] | None:
    """
    Given a DOI, retrieves the paper's title and semantic scholar paper ID.

    Parameters:
        doi (str): The DOI of the paper (e.g., "10.18653/v1/N18-3011").

    Returns:
        dict or None: A dictionary with keys 'title' and 'ssid'.
    """
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS), limits=HTTPX_LIMITS
    ) as client:
        # Send the GET request to Semantic Scholar
        response = await semantic_scholar_get(client, f"{PAPER_URL}DOI:{doi}")
        if response.status_code == 200:
            data = response.json()
            return {"title": data.get("title"), "ssid": data.get("paperId")}
        logger.warning(
            f"Could not get authors & semantic scholar ID for DOI={doi}, {response.status_code}: {response.text}"
        )


@optional_async
@retry_with_exponential_backoff(max_retries=10, base_delay=1.0)
async def author_name_to_ssaid(author_name: str) -> Tuple[str, str]:
    """
    Given an author name, returns the Semantic Scholar author ID.
    Respects rate limiting to avoid exceeding API limits.

    Parameters:
        author_name (str): The full name of the author.

    Returns:
        Tuple[str, str] or None: The SS author ID alongside the SS name (may differ
            slightly from input name) or None if no author is found.
    """
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS), limits=HTTPX_LIMITS
    ) as client:
        await wait_for_request_slot()

        response = await semantic_scholar_get(
            client,
            AUTHOR_URL,
            params={"query": author_name, "fields": "name", "limit": 1},
        )
        response.raise_for_status()
        data = response.json()
        authors = data.get("data", [])
        if authors:
            # Return the Semantic Scholar author ID from the first result.
            return authors[0]["authorId"], authors[0]["name"]

        logger.error(
            f"Error in retrieving name from SS Author ID: {response.status_code} - {response.text}"
        )
        return ("-1", "N.A.")


def determine_paper_input_type(input: str) -> Literal["ssid", "doi", "title"]:
    """
    Determines the intended input type by the user if not explicitly given (`infer`).

    Args:
        input: Either a DOI or a semantic scholar paper ID or an author name.

    Returns:
        The input type
    """
    if len(input) > 15 and " " not in input and (input.isalnum() and input.islower()):
        mode = "ssid"
    elif len(re.findall(DOI_PATTERN, input, re.IGNORECASE)) == 1:
        mode = "doi"
    else:
        logger.info(
            f"Assuming `{input}` is a paper title, since it seems neither a DOI nor a paper ID"
        )
        mode = "title"
    return mode


@optional_async
@retry_with_exponential_backoff(max_retries=10, base_delay=1.0)
async def get_papers_for_author(ss_author_id: str) -> List[str]:
    """
    Given a Semantic Scholar author ID, returns a list of all Semantic Scholar paper IDs for that author.

    Args:
        ss_author_id (str): The Semantic Scholar author ID (e.g., "1741101").

    Returns:
        A list of paper IDs (as strings) authored by the given author.
    """
    papers = []
    offset = 0
    limit = 100

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS), limits=HTTPX_LIMITS
    ) as client:
        while True:
            response = await semantic_scholar_get(
                client,
                f"https://api.semanticscholar.org/graph/v1/author/{ss_author_id}/papers",
                params={"fields": "paperId", "offset": offset, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()
            page = data.get("data", [])

            # Extract paper IDs from the current page.
            for paper in page:
                if "paperId" in paper:
                    papers.append(paper["paperId"])

            # If fewer papers were returned than the limit, we've reached the end.
            if len(page) < limit:
                break

            offset += limit

    return papers


def find_matching(
    first: List[Dict[str, str]], second: List[Dict[str, str]]
) -> List[str]:
    """
    Ingests two sets of authors and returns a list of those that match (either based on name
        or on author ID).

    Args:
        first: First set of authors given as list of dict with two keys (`authorID` and `name`).
        second: Second set of authors given as list of dict with two same keys.

    Returns:
        List of names of authors in first list where a match was found.
    """
    # Check which author IDs overlap
    second_names = set(map(lambda x: x["authorId"], second))
    overlap_ids = {f["name"] for f in first if f["authorId"] in second_names}

    overlap_names = {
        f["name"]
        for f in first
        if f["authorId"] not in overlap_ids
        and any([check_overlap(f["name"], s["name"]) for s in second])
    }
    return list(overlap_ids | overlap_names)


def check_overlap(n1: str, n2: str) -> bool:
    """
    Check whether two author names are identical.

    Heuristics:
        - Case insensitive
        - If name sets are identical, a match is assumed (e.g. "John Walter" vs "Walter John").
        - Assume the last token is the surname and require:
            * same surname
            * both have at least one given name
            * first given names are compatible (same, or initial vs full)

    Args:
        n1: first name (e.g., "John A. Smith")
        n2: second name (e.g., "J. Smith")

    Returns:
        bool: Whether names are identical.
    """
    t1 = [w for w in clean_name(n1).split() if w]
    t2 = [w for w in clean_name(n2).split() if w]

    if not t1 or not t2:
        return False  # One name is empty after cleaning

    if set(t1) == set(t2):
        return True  # Name sets are identical

    # Assume last token is surname
    surname1, given1 = t1[-1], t1[:-1]
    surname2, given2 = t2[-1], t2[:-1]

    if surname1 != surname2:
        return False  # Surnames do not match

    if not given1 or not given2:
        return False  # One name has no given names

    # Compare only the *first* given name; middle names are optional
    return (
        given1[0] == given2[0]
        or (len(given1[0]) == 1 and given2[0].startswith(given1[0]))
        or (len(given2[0]) == 1 and given1[0].startswith(given2[0]))
    )


def clean_name(s: str) -> str:
    """
    Clean up a str by removing special characters.

    Args:
        s: Input possibly containing special symbols

    Returns:
        Homogenized string.
    """
    return "".join(ch for ch in unidecode(s) if ch.isalpha() or ch.isspace()).lower()
