import logging
import sys
from time import sleep

from semanticscholar import SemanticScholar, SemanticScholarException

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
sch = SemanticScholar()


def get_citations_by_doi(doi: str) -> int:
    """
    Get the number of citations of a paper according to semantic scholar.

    Args:
        doi: the DOI of the paper.

    Returns:
        The number of citations
    """

    try:
        paper = sch.get_paper(doi)
        citations = len(paper["citations"])
    except SemanticScholarException.ObjectNotFoundException:
        logger.warning(f"Could not find paper {doi}, assuming 0 citation.")
        citations = 0
    except ConnectionRefusedError as e:
        logger.warning(f"Waiting for 10 sec since {doi} gave: {e}")
        sleep(10)
        citations = len(sch.get_paper(doi)["citations"])
    finally:
        return citations
