import logging
import os
import re
import sys
from typing import Any, Dict, List, Literal, Optional

import httpx
import requests
from tqdm import tqdm
from unidecode import unidecode

from ..async_utils import optional_async, retry_with_exponential_backoff

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

DOI_PATTERN = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"
PAPER_URL: str = "https://api.semanticscholar.org/graph/v1/paper/"
AUTHOR_URL: str = "https://api.semanticscholar.org/graph/v1/author/search"


SS_API_KEY = os.getenv("SS_API_KEY")
HEADERS: Dict[str, str] = {}
if SS_API_KEY:
    HEADERS["x-api-key"] = SS_API_KEY


def get_doi_from_title(title: str) -> Optional[str]:
    """
    Searches the DOI of a paper based on the paper title

    Args:
        title: Paper title

    Returns:
        DOI according to semantic scholar API
    """
    response = requests.get(
        PAPER_URL + "search",
        params={"query": title, "fields": "externalIds", "limit": 1},
        headers=HEADERS,
    )
    data = response.json()

    if data.get("data"):
        paper = data["data"][0]
        doi = paper.get("externalIds", {}).get("DOI")
        if doi:
            return doi
    logger.warning(f"Did not find DOI for title={title}")


@optional_async
async def get_doi_from_ssid(ssid: str, max_retries: int = 10) -> Optional[str]:
    """
    Given a Semantic Scholar paper ID, returns the corresponding DOI if available.

    Parameters:
      ssid (str): The paper ID on Semantic Scholar.

    Returns:
      str or None: The DOI of the paper, or None if not found or in case of an error.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
        logger.warning(
            "Semantic Scholar API is easily overloaded when passing SS IDs, provide DOIs to improve throughput."
        )
        attempts = 0
        for attempt in tqdm(
            range(1, max_retries + 1), desc=f"Fetching DOI for {ssid}", unit="attempt"
        ):
            # Make the GET request to Semantic Scholar.
            response = await client.get(
                f"{PAPER_URL}{ssid}",
                params={"fields": "externalIds", "limit": 1},
                headers=HEADERS,
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
    async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
        # Send the GET request to Semantic Scholar
        response = await client.get(f"{PAPER_URL}DOI:{doi}", headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            return {"title": data.get("title"), "ssid": data.get("paperId")}
        logger.warning(
            f"Could not get authors & semantic scholar ID for DOI={doi}, {response.status_code}: {response.text}"
        )


@optional_async
async def author_name_to_ssaid(author_name: str) -> str:
    """
    Given an author name, returns the Semantic Scholar author ID.

    Parameters:
        author_name (str): The full name of the author.

    Returns:
        str or None: The Semantic Scholar author ID or None if no author is found.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
        response = await client.get(
            AUTHOR_URL,
            params={"query": author_name, "fields": "name", "limit": 1},
            headers={"x-api-key": os.getenv("SS_API_KEY")},
        )
        if response.status_code == 200:
            data = response.json()
            authors = data.get("data", [])
            if authors:
                # Return the Semantic Scholar author ID from the first result.
                return authors[0].get("authorId")

        logger.error(
            f"Error in retrieving name from SS Author ID: {response.status_code} - {response.text}"
        )


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

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
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
