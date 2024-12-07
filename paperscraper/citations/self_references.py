import asyncio
import logging
import re
import sys
from typing import Dict, Iterable, Literal, Union

import httpx
from semanticscholar import SemanticScholar

from ..utils import optional_async
from .utils import check_overlap, doi_pattern

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
ModeType = Literal[tuple(MODES := ("doi", "name", "orcid", "ssid"))]


@optional_async
async def self_references(
    inputs: Union[str, Iterable[str]],
    mode: ModeType = "doi",
    relative: bool = True,
    verbose: bool = False,
) -> Dict[str, Dict[str, Union[float, int]]]:
    """
    Analyze self-references for a DOI or a list of DOIs.

    Args:
        inputs: A single or a list of strings to analyze self-references for.
            Dependent on the `mode` this can be either of:
            - doi:      Digital object identifier of a paper to measure self references.
            - name:     Name of a researcher to measure self references across all papers.
            - orcid:    ORCID ID of a researcher to measure self references across all papers.
            - ssid:    Semantic Scholar ID of a researcher to measure self references across all papers.
        mode:
            Either `doi`, `author`, `orcid` or `ssid`.
            - doi:      Digital object identifier of a paper to measure self references.
            - name:     Name of a researcher to measure self references across all papers.
            - orcid:    ORCID ID of a researcher to measure self references across all papers.
            - ssid:    Semantic Scholar ID of a researcher to measure self references across all papers.
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

    if mode == "doi":
        for should_be_doi in inputs:
            dois = re.findall(doi_pattern, should_be_doi, re.IGNORECASE)
            if len(dois) == 1:
                # This is a DOI
                tasks.append(
                    (
                        should_be_doi,
                        self_references_paper(
                            dois[0], verbose=verbose, relative=relative
                        ),
                    )
                )
            else:
                raise ValueError(
                    f"For {should_be_doi} {len(dois)} DOIs were extracted. Please check your input."
                )
        completed_tasks = await asyncio.gather(*[task[1] for task in tasks])
        for sample, task_result in zip(tasks, completed_tasks):
            results[sample[0]] = task_result
    elif mode == "name":
        pass

    elif mode == "orcid":
        pass

    elif mode == "ssid":
        sch = SemanticScholar()
        for should_be_ssid in inputs:
            # TODO: Error handling
            author = sch.get_author(should_be_ssid)
            # TODO: Support other IDs than DOI
            dois = [
                paper._data["externalIds"]["DOI"]
                for paper in author.papers
                if "DOI" in paper._data["externalIds"].keys()
            ]
            for doi in dois:
                # TODO: Skip over erratum / corrigendum
                tasks.append(
                    (
                        should_be_ssid,
                        self_references_paper(doi, verbose=verbose, relative=relative),
                    )
                )
        completed_tasks = await asyncio.gather(*[task[1] for task in tasks])
        results[author.name] = []
        for sample, task_result in zip(tasks, completed_tasks):
            results[author.name].append(task_result[author.name])
            # TODO: Consider returning this as JSON/DF

    else:
        raise ValueError(f"Unknown mode {mode}, pick from {MODES}")

    # TODO: Post-hoc aggregation for SS-ID

    return results


@optional_async
async def self_references_paper(
    doi: str,
    relative: bool = True,
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

    authors: Dict[str, int] = {a["name"]: 0 for a in paper["authors"]}
    if not paper["references"]:
        logger.warning(f"Could not find citations from Semantic Scholar for {doi}")
        return authors

    for ref in paper["references"]:
        ref_authors = {a["name"] for a in ref["authors"]}
        for author in authors:
            # TODO: Make sure to expand names given as J. Doe to John Doe
            if any(check_overlap(author, ra) for ra in ref_authors):
                authors[author] += 1
    total = len(paper["references"])

    if verbose:
        logger.info(f"Self references in \"{paper['title']}\"")
        logger.info(f" N = {len(paper['references'])}")
        for author, self_cites in authors.items():
            logger.info(f" {author}: {100*(self_cites/total):.2f}% self-references")

    if relative:
        for author, self_cites in authors.items():
            authors[author] = round(100 * self_cites / total, 2)

    return authors
