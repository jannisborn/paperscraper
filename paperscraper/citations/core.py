import asyncio
import logging
import re
import sys
from typing import Dict, Iterable, Union

import httpx

from ..utils import optional_async
from .entity import Paper, Researcher
from .utils import check_overlap

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


@optional_async
async def self_references(
    inputs: Union[str, Iterable[str]],
    relative: bool = False,
    verbose: bool = False,
) -> Dict[str, Dict[str, Union[float, int]]]:
    """
    Analyze self-references for a DOI or a list of DOIs.

    Args:
        inputs: A single DOI or an iterable of DOIs.
        relative: If True, returns self-citations as percentages; otherwise, as raw counts.
                  Defaults to False.
        verbose: Whether to log detailed information. Defaults to False.

    Returns:
        A dictionary where the keys are DOIs and the values are dictionaries mapping
        authors to their self-citations.

    Raises:
        NotImplementedError: If the input does not match a DOI format.
    """
    if isinstance(inputs, str):
        inputs = [inputs]

    results: Dict[str, Dict[str, Union[float, int]]] = {}

    tasks = []

    for sample in inputs:
        dois = re.findall(doi_pattern, sample, re.IGNORECASE)
        if len(dois) == 1:
            # This is a DOI
            tasks.append(
                (
                    sample,
                    self_references_paper(dois[0], verbose=verbose, relative=relative),
                )
            )
        elif len(dois) == 0:
            # TODO: Check that it is a proper name or an ORCID ID
            raise NotImplementedError(
                "Analyzing self-references of whole authors is not yet implemented."
            )
    completed_tasks = await asyncio.gather(*[task[1] for task in tasks])
    for sample, task_result in zip(tasks, completed_tasks):
        results[sample[0]] = task_result

    return results


@optional_async
async def self_references_paper(
    doi: str,
    relative: bool = False,
    verbose: bool = False,
) -> Dict[str, Union[float, int]]:
    """
    Analyze self-references for a single DOI.

    Args:
        doi: The DOI to analyze.
        relative: If True, returns self-citations as percentages; otherwise, as raw counts.
                  Defaults to False.
        verbose: Whether to log detailed information. Defaults to False.

    Returns:
        A dictionary mapping authors to their self-citations.

    Raises:
        ValueError: If no references are found for the given DOI.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "title,authors,references.authors"},
        )
        response.raise_for_status()
        paper = response.json()

    if not paper["references"]:
        raise ValueError("Could not find citations from Semantic Scholar")

    authors: Dict[str, int] = {a["name"]: 0 for a in paper["authors"]}

    for ref in paper["references"]:
        ref_authors = {a["name"] for a in ref["authors"]}
        for author in authors:
            if any(check_overlap(author, ra) for ra in ref_authors):
                authors[author] += 1
    total = len(paper["references"])

    if verbose:
        logger.info(f'Self references in "{paper["title"]}"')
        logger.info(f" N = {len(paper['references'])}")
        for author, self_cites in authors.items():
            logger.info(f" {author}: {100 * (self_cites / total):.2f}% self-references")

    if relative:
        for author, self_cites in authors.items():
            authors[author] = round(100 * self_cites / total, 2)

    return authors
