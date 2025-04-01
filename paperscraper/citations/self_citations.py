import logging
import re
import sys
from typing import Dict

import httpx
import numpy as np
from pydantic import BaseModel

from ..utils import optional_async
from .utils import DOI_PATTERN, find_matching

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


class CitationResult(BaseModel):
    ssid: str  # semantic scholar paper id
    num_citations: int
    self_citations: Dict[str, float] = {}
    citation_score: float


@optional_async
async def self_citations_paper(input: str, verbose: bool = False) -> CitationResult:
    """
    Analyze self-citations for a single DOI or semantic scholar ID.

    Args:
        input: Either a DOI or a semantic scholar ID.
        verbose: Whether to log detailed information. Defaults to False.

    Returns:
        A ReferenceResult object.

    Raises:
        ValueError: If no citations are found for the given DOI.
    """
    if len(input) > 15 and " " not in input and (input.isalnum() and input.islower()):
        mode = ""
    elif len(re.findall(DOI_PATTERN, input, re.IGNORECASE)) == 1:
        mode = "DOI:"

    suffix = f"{mode}{input}"
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{suffix}",
            params={"fields": "title,authors,citations.authors"},
        )
        response.raise_for_status()
        paper = response.json()

    authors: Dict[str, int] = {a["name"]: 0 for a in paper["authors"]}
    ratios = authors.copy()
    if not paper.get("citations"):
        logger.warning(f"Could not find citations from Semantic Scholar for ID:{input}")
        return authors

    for citation in paper["citations"]:
        # For every reference, find matching names and increase
        for author in find_matching(paper["authors"], citation["authors"]):
            authors[author] += 1

    total = len(paper["citations"])

    if verbose:
        logger.info(f'Self-citations in "{paper["title"]}"')
        logger.info(f" N = {len(paper['citations'])}")
        for author, self_cites in authors.items():
            logger.info(f" {author}: {100 * (self_cites / total):.2f}% self-citations")

    for author, self_cites in authors.items():
        ratios[author] = round(100 * self_cites / total, 2)

    result = CitationResult(
        ssid=input,
        num_citations=total,
        self_citations=ratios,
        citation_score=round(np.mean(list(ratios.values())), 3),
    )

    return result
