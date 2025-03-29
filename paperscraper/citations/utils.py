import logging
import sys
from time import sleep
from typing import Any, Dict, List, Optional

import httpx
import requests
from tqdm import tqdm
from unidecode import unidecode

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

DOI_PATTERN = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"
PAPER_URL: str = "https://api.semanticscholar.org/graph/v1/paper/"
AUTHOR_URL: str = "https://api.semanticscholar.org/graph/v1/author/search"


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
    )
    data = response.json()

    if data.get("data"):
        paper = data["data"][0]
        doi = paper.get("externalIds", {}).get("DOI")
        if doi:
            return doi
    logger.warning(f"Did not find DOI for title={title}")


def get_doi_from_ssid(ssid: str, max_retries: int = 10) -> Optional[str]:
    """
    Given a Semantic Scholar paper ID, returns the corresponding DOI if available.

    Parameters:
      ssid (str): The paper ID on Semantic Scholar.

    Returns:
      str or None: The DOI of the paper, or None if not found or in case of an error.
    """
    logger.warning(
        "Semantic Scholar API is easily overloaded when passing SS IDs, provide DOIs to improve throughput."
    )
    attempts = 0
    for attempt in tqdm(
        range(1, max_retries + 1), desc=f"Fetching DOI for {ssid}", unit="attempt"
    ):
        # Make the GET request to Semantic Scholar.
        response = requests.get(
            f"{PAPER_URL}{ssid}", params={"fields": "externalIds", "limit": 1}
        )

        # If successful, try to extract and return the DOI.
        if response.status_code == 200:
            data = response.json()
            doi = data.get("externalIds", {}).get("DOI")
            return doi
        attempts += 1
        sleep(10)
    logger.warning(
        f"Did not find DOI for paper ID {ssid}. Code={response.status_code}, text={response.text}"
    )


def get_title_and_id_from_doi(doi: str) -> Dict[str, Any]:
    """
    Given a DOI, retrieves the paper's title and semantic scholar paper ID.

    Parameters:
        doi (str): The DOI of the paper (e.g., "10.18653/v1/N18-3011").

    Returns:
        dict or None: A dictionary with keys 'title' and 'ssid'.
    """

    # Send the GET request to Semantic Scholar
    response = requests.get(f"{PAPER_URL}DOI:{doi}")
    if response.status_code == 200:
        data = response.json()
        return {"title": data.get("title"), "ssid": data.get("paperId")}
    logger.warning(
        f"Could not get authors & semantic scholar ID for DOI={doi}, {response.status_code}: {response.text}"
    )


def author_name_to_ssid(author_name: str) -> str:
    """
    Given an author name, returns the Semantic Scholar author ID.

    Parameters:
        author_name (str): The full name of the author.

    Returns:
        str or None: The Semantic Scholar author ID or None if no author is found.
    """

    response = requests.get(
        AUTHOR_URL, params={"query": author_name, "fields": "name", "limit": 1}
    )
    if response.status_code == 200:
        data = response.json()
        authors = data.get("data", [])
        if authors:
            # Return the Semantic Scholar author ID from the first result.
            return authors[0].get("authorId")

    logger.error(
        f"Error in retrieving name from SS ID: {response.status_code} - {response.text}"
    )


async def get_papers_for_author(author_id: str) -> List[str]:
    """
    Given a Semantic Scholar author ID, returns a list of all Semantic Scholar paper IDs for that author.

    Args:
        author_id (str): The Semantic Scholar author ID (e.g., "1741101").

    Returns:
        A list of paper IDs (as strings) authored by the given author.
    """
    papers = []
    offset = 0
    limit = 100

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers",
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
    TODO: This can be made more robust

    Args:
        n1: first name
        n2: second name

    Returns:
        bool: Whether names are identical.
    """
    # remove initials and check for name intersection
    s1 = {w for w in clean_name(n1).split()}
    s2 = {w for w in clean_name(n2).split()}
    return len(s2) > 0 and len(s1 | s2) == len(s1)


def clean_name(s: str) -> str:
    """
    Clean up a str by removing special characters.

    Args:
        s: Input possibly containing special symbols

    Returns:
        Homogenized string.
    """
    return "".join(ch for ch in unidecode(s) if ch.isalpha() or ch.isspace()).lower()
