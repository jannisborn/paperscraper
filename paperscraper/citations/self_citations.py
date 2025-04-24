import asyncio
import logging
import re
import sys
from typing import Any, Dict, List, Union

import httpx
import numpy as np
from pydantic import BaseModel

from ..async_utils import optional_async, retry_with_exponential_backoff
from .utils import DOI_PATTERN, find_matching

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


class CitationResult(BaseModel):
    ssid: str  # semantic scholar paper id
    num_citations: int
    self_citations: Dict[str, float] = {}
    citation_score: float


async def _fetch_citation_data(
    client: httpx.AsyncClient, suffix: str
) -> Dict[str, Any]:
    """
    Fetch raw paper data from Semantic Scholar by DOI or SSID suffix.

    Args:
        client: An active httpx.AsyncClient.
        suffix: Prefixed identifier (e.g., "DOI:10.1000/xyz123" or SSID).

    Returns:
        The JSON-decoded response as a dictionary.
    """
    response = await client.get(
        f"https://api.semanticscholar.org/graph/v1/paper/{suffix}",
        params={"fields": "title,authors,citations.authors"},
    )
    response.raise_for_status()
    return response.json()


async def _process_single(client: httpx.AsyncClient, identifier: str) -> CitationResult:
    """
    Compute self-citation stats for a single paper.

    Args:
        client: An active httpx.AsyncClient.
        identifier: A DOI or Semantic Scholar ID.

    Returns:
        A CitationResult containing counts and percentages of self-citations.
    """
    # Determine prefix for Semantic Scholar API
    if len(identifier) > 15 and identifier.isalnum() and identifier.islower():
        prefix = ""
    elif len(re.findall(DOI_PATTERN, identifier, re.IGNORECASE)) == 1:
        prefix = "DOI:"
    else:
        prefix = ""

    suffix = f"{prefix}{identifier}"
    paper = await _fetch_citation_data(client, suffix)

    # Initialize counters
    author_counts: Dict[str, int] = {a["name"]: 0 for a in paper.get("authors", [])}
    citations = paper.get("citations", [])
    total_cites = len(citations)

    # Tally self-citations
    for cite in citations:
        matched = find_matching(paper.get("authors", []), cite.get("authors", []))
        for name in matched:
            author_counts[name] += 1

    # Compute percentages
    ratios: Dict[str, float] = {
        name: round((count / total_cites * 100), 2) if total_cites > 0 else 0.0
        for name, count in author_counts.items()
    }

    avg_score = round(float(np.mean(list(ratios.values()))) if ratios else 0.0, 3)

    return CitationResult(
        ssid=identifier,
        num_citations=total_cites,
        self_citations=ratios,
        citation_score=avg_score,
    )


@optional_async
@retry_with_exponential_backoff(max_retries=4, base_delay=1.0)
async def self_citations_paper(
    inputs: Union[str, List[str]], verbose: bool = False
) -> Union[CitationResult, List[CitationResult]]:
    """
    Analyze self-citations for one or more papers by DOI or Semantic Scholar ID.

    Args:
        inputs: A single DOI/SSID string or a list of them.
        verbose: If True, logs detailed information for each paper.

    Returns:
        A single CitationResult if a string was passed, else a list of CitationResults.
    """
    single_input = isinstance(inputs, str)
    identifiers = [inputs] if single_input else list(inputs)

    async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
        tasks = [_process_single(client, ident) for ident in identifiers]
        results = await asyncio.gather(*tasks)

    if verbose:
        for res in results:
            logger.info(
                f'Self-citations in "{res.ssid}": N={res.num_citations}, Score={res.citation_score}%'
            )
            for author, pct in res.self_citations.items():
                logger.info(f"  {author}: {pct}%")

    return results[0] if single_input else results
