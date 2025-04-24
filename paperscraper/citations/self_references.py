import asyncio
import logging
import re
import sys
from typing import Any, Dict, List, Literal, Union

import httpx
import numpy as np
from pydantic import BaseModel

from ..utils import optional_async
from .utils import DOI_PATTERN, find_matching

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
ModeType = Literal[tuple(MODES := ("doi", "infer", "ssid"))]


class ReferenceResult(BaseModel):
    ssid: str  # semantic scholar paper id
    num_references: int
    self_references: Dict[str, float] = {}
    reference_score: float


async def _fetch_reference_data(
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
        params={"fields": "title,authors,references.authors"},
    )
    response.raise_for_status()
    return response.json()


async def _process_single_reference(
    client: httpx.AsyncClient, identifier: str
) -> ReferenceResult:
    """
    Compute self-reference statistics for a single paper.

    Args:
        client: An active httpx.AsyncClient.
        identifier: A DOI or Semantic Scholar ID.

    Returns:
        A ReferenceResult containing counts and percentages of self-references.
    """
    # Determine prefix for API
    if len(identifier) > 15 and identifier.isalnum() and identifier.islower():
        prefix = ""
    elif len(re.findall(DOI_PATTERN, identifier, re.IGNORECASE)) == 1:
        prefix = "DOI:"
    else:
        prefix = ""

    suffix = f"{prefix}{identifier}"
    paper = await _fetch_reference_data(client, suffix)

    # Initialize counters
    author_counts: Dict[str, int] = {a["name"]: 0 for a in paper.get("authors", [])}
    references = paper.get("references", [])
    total_refs = len(references)

    # Tally self-references
    for ref in references:
        matched = find_matching(paper.get("authors", []), ref.get("authors", []))
        for name in matched:
            author_counts[name] += 1

    # Compute percentages per author
    ratios: Dict[str, float] = {
        name: round((count / total_refs * 100), 2) if total_refs > 0 else 0.0
        for name, count in author_counts.items()
    }

    # Compute average score
    avg_score = round(float(np.mean(list(ratios.values()))) if ratios else 0.0, 3)

    return ReferenceResult(
        ssid=identifier,
        num_references=total_refs,
        self_references=ratios,
        reference_score=avg_score,
    )


@optional_async
async def self_references_paper(
    inputs: Union[str, List[str]], verbose: bool = False
) -> Union[ReferenceResult, List[ReferenceResult]]:
    """
    Analyze self-references for one or more papers by DOI or Semantic Scholar ID.

    Args:
        inputs: A single DOI/SSID string or a list of them.
        verbose: If True, logs detailed information for each paper.

    Returns:
        A single ReferenceResult if a string was passed, else a list of ReferenceResults.

    Raises:
        ValueError: If no references are found for a given identifier.
    """
    single_input = isinstance(inputs, str)
    identifiers = [inputs] if single_input else list(inputs)

    async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
        tasks = [_process_single_reference(client, ident) for ident in identifiers]
        results = await asyncio.gather(*tasks)

    if verbose:
        for res in results:
            logger.info(
                f'Self-references in "{res.ssid}": N={res.num_references}, '
                f"Score={res.reference_score}%"
            )
            for author, pct in res.self_references.items():
                logger.info(f"  {author}: {pct}% self-reference")

    return results[0] if single_input else results


# @optional_async
# async def self_references_paper(input: str, verbose: bool = False) -> ReferenceResult:
#     """
#     Analyze self-references for a single DOI or semantic scholar ID

#     Args:
#         input: either a DOI or a semantic scholar ID.
#         verbose: Whether to log detailed information. Defaults to False.

#     Returns:
#         A ReferenceResult object.

#     Raises:
#         ValueError: If no references are found for the given DOI.
#     """
#     if len(input) > 15 and " " not in input and (input.isalnum() and input.islower()):
#         mode = ""
#     elif len(re.findall(DOI_PATTERN, input, re.IGNORECASE)) == 1:
#         mode = "DOI:"

#     suffix = f"{mode}{input}"
#     async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
#         response = await client.get(
#             f"https://api.semanticscholar.org/graph/v1/paper/{suffix}",
#             params={"fields": "title,authors,references.authors"},
#         )
#         response.raise_for_status()
#         paper = response.json()

#     authors: Dict[str, int] = {a["name"]: 0 for a in paper["authors"]}
#     ratios = authors.copy()
#     if not paper["references"]:
#         logger.warning(f"Could not find citations from Semantic Scholar for ID:{input}")
#         return authors

#     for ref in paper["references"]:
#         # For every reference, find matching names and increase
#         for author in find_matching(paper["authors"], ref["authors"]):
#             authors[author] += 1
#     total = len(paper["references"])

#     if verbose:
#         logger.info(f'Self references in "{paper["title"]}"')
#         logger.info(f" N = {len(paper['references'])}")
#         for author, self_cites in authors.items():
#             logger.info(f" {author}: {100 * (self_cites / total):.2f}% self-references")

#     for author, self_cites in authors.items():
#         ratios[author] = round(100 * self_cites / total, 2)

#     result = ReferenceResult(
#         ssid=input,
#         num_references=total,
#         self_references=ratios,
#         reference_score=round(np.mean(list(ratios.values())), 3),
#     )

#     return result
