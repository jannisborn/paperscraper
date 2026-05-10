import logging
import sys
from time import sleep

from scholarly import scholarly
from semanticscholar import SemanticScholarException

from .utils import PAPER_URL, semantic_scholar_requests_get

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def get_citations_by_doi(doi: str) -> int:
    """
    Get the number of citations of a paper according to semantic scholar.

    Args:
        doi: the DOI of the paper.

    Returns:
        The number of citations
    """

    try:
        response = semantic_scholar_requests_get(
            f"{PAPER_URL}DOI:{doi}",
            params={"fields": "citationCount"},
            timeout=20,
        )
        if response.status_code == 404:
            logger.warning(f"Could not find paper {doi}, assuming 0 citation.")
            return 0
        response.raise_for_status()
        return response.json()["citationCount"]
    except SemanticScholarException.ObjectNotFoundException:
        logger.warning(f"Could not find paper {doi}, assuming 0 citation.")
        return 0
    except ConnectionRefusedError as e:
        logger.warning(f"Waiting for 10 sec since {doi} gave: {e}")
        sleep(10)
        response = semantic_scholar_requests_get(
            f"{PAPER_URL}DOI:{doi}",
            params={"fields": "citationCount"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["citationCount"]


def get_citations_from_title(title: str) -> int:
    """
    Args:
        title (str): Title of paper to be searched on Scholar.

    Raises:
        TypeError: If sth else than str is passed.

    Returns:
        int: Number of citations of paper.
    """

    if not isinstance(title, str):
        raise TypeError(f"Pass str not {type(title)}")

    # Search for exact match
    title = '"' + title.strip() + '"'

    matches = scholarly.search_pubs(title)
    counts = list(map(lambda p: int(p["num_citations"]), matches))
    if len(counts) == 0:
        logger.warning(f"Found no match for {title}.")
        return 0
    if len(counts) > 1:
        logger.warning(f"Found {len(counts)} matches for {title}, returning first one.")
    return counts[0]
