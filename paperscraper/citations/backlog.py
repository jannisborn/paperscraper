import asyncio
import re
from typing import Dict, List, Tuple

import httpx

from ..utils import optional_async
from .utils import check_overlap, doi_pattern, get_citations, get_paper_data


@optional_async
async def self_references(input: str, verbose: bool = False) -> Dict[str, Tuple[int]]:
    doi = re.findall(doi_pattern, input, re.IGNORECASE)
    print("DOI", doi)

    if "." in input and "/" in input:
        # This is a doi
        return await self_references_paper(doi=input, verbose=verbose)
    else:
        # This is a name
        raise NotImplementedError(
            "Analyzing self-references of whole authors will follow."
        )


@optional_async
async def self_references_paper(doi: str, verbose: bool = False) -> Dict[str, int]:
    async with httpx.AsyncClient() as client:
        paper = await get_paper_data(client, doi, "title,authors")
        authors = {a["name"]: [0, 0] for a in paper["authors"]}

        citing_papers = await get_citations(client, doi)

        for citing_paper in citing_papers:
            for author in authors.keys():
                authors[author][0] += 1

                citing_authors = {a["name"] for a in citing_paper["authors"]}
                if any(check_overlap(author, ca) for ca in citing_authors):
                    authors[author][1] += 1

        if verbose:
            print(f"Self references in \"{paper['title']}\"")
            print(f" N = {len(citing_papers)}")
            for author, (total, self_cites) in authors.items():
                print(
                    f" {author}: {self_cites/total:.2%} self-citations ({self_cites} / {total})"
                )

        return authors


def check_overlap(n1: str, n2: str) -> bool:
    """
    Check whether...

    Args:
        n1: _description_
        n2: _description_

    Returns:
        bool: _description_
    """
    # remove initials and check for name intersection
    s1 = {w for w in n1.lower().replace(".", "").split() if len(w) > 1}
    s2 = {w for w in n2.lower().replace(".", "").split() if len(w) > 1}
    return len(s1 | s2) == len(s1)


async def get_paper_data(client: httpx.AsyncClient, paper_id: str, fields: str) -> dict:
    """
    Fetch paper data from the Semantic Scholar API.
    """
    response = await client.get(
        f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}",
        params={"fields": fields},
    )
    response.raise_for_status()
    return response.json()


async def self_citations_in_paper(
    doi: str, verbose: bool = False
) -> Dict[str, Tuple[int]]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "title,authors,references.authors"},
        )
        response.raise_for_status()
        paper = response.json()

    if not paper["references"]:
        raise ValueError("Could not find citations from Semantic Scholar")

    authors = {a["name"]: [0, 0] for a in paper["authors"]}

    for ref in paper["references"]:
        ref_authors = {a["name"] for a in ref["authors"]}
        for author in authors:
            authors[author][1] += 1
            if any(check_overlap(author, ra) for ra in ref_authors):
                authors[author][0] += 1

    if verbose:
        print(f"Self references in \"{paper['title']}\"")
        print(f" N = {len(paper['references'])}")
        for author, (self_cites, total) in authors.items():
            print(f" {author}: {self_cites/total:.2%} self-references")

    print(authors)
    return authors


async def get_citations(
    client: httpx.AsyncClient, paper_id: str, offset: int = 0, limit: int = 1000
) -> List[dict]:
    """
    Fetch all citing papers for a given paper ID.
    """
    citations = []
    while True:
        response = await client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations",
            params={"fields": "authors", "limit": limit, "offset": offset},
        )
        response.raise_for_status()
        page = response.json()["data"]
        citations.extend([edge["citingPaper"] for edge in page])

        if len(page) < limit:
            break
        offset += limit
    return citations


async def self_citations_of_paper(
    paper_id: str, verbose: bool = False
) -> Dict[str, int]:
    async with httpx.AsyncClient() as client:
        paper = await get_paper_data(client, paper_id, "title,authors")
        authors = {a["name"]: [0, 0] for a in paper["authors"]}

        citing_papers = await get_citations(client, paper_id)

        for citing_paper in citing_papers:
            for author in authors.keys():
                authors[author][0] += 1

                citing_authors = {a["name"] for a in citing_paper["authors"]}
                if any(check_overlap(author, ca) for ca in citing_authors):
                    authors[author][1] += 1

        if verbose:
            print(f"Self references in \"{paper['title']}\"")
            print(f" N = {len(citing_papers)}")
            for author, (total, self_cites) in authors.items():
                print(
                    f" {author}: {self_cites/total:.2%} self-citations ({self_cites} / {total})"
                )

        return authors


async def get_author_papers(client: httpx.AsyncClient, author_name: str) -> List[dict]:
    """
    Fetch all papers authored by the given researcher.
    """
    papers = []
    offset = 0
    while True:
        response = await client.get(
            "https://api.semanticscholar.org/graph/v1/author/search",
            params={
                "query": author_name,
                "fields": "papers",
                "offset": offset,
            },
        )
        response.raise_for_status()
        data = response.json()
        if not data["data"]:
            break
        papers.extend(data["data"])
        # if len(data["data"]) < limit:
        #     break
        # offset += limit

    print(len(papers))
    return papers


async def aggregate_self_citations(
    author_name: str, verbose: bool = False
) -> Dict[str, int]:
    """
    Aggregate self-citation statistics for all papers of a given researcher.
    """
    async with httpx.AsyncClient() as client:
        # Fetch all papers authored by the researcher
        author_papers = await get_author_papers(client, author_name)

        total_citations = 0
        total_self_citations = 0

        for paper in author_papers:
            paper_id = paper.get("paperId")
            print(paper_id)
            if not paper_id:
                continue

            try:
                # Get self-citation statistics for this paper
                paper_stats = await self_citations_of_paper(paper_id)
                print(paper_id, paper_stats)
                for author, (total, self_cites) in paper_stats.items():
                    if check_overlap(author, author_name):
                        total_citations += total
                        total_self_citations += self_cites
            except Exception as e:
                if verbose:
                    print(
                        f"Error processing paper {paper.get('title', 'Unknown')} ({paper_id}): {e}"
                    )

        if verbose:
            print(f"Aggregate statistics for '{author_name}':")
            print(f" Total Citations: {total_citations}")
            print(f" Total Self-Citations: {total_self_citations}")

        return {
            "total_citations": total_citations,
            "self_citations": total_self_citations,
        }


asyncio.run(aggregate_self_citations("Bastian Rieck", verbose=True))


# asyncio.run(self_citations_of_paper("10.3389/frai.2021.681108", verbose=True))
# asyncio.run(self_citations_in_paper("10.1038/s42256-023-00639-z", verbose=True))
