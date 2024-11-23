from typing import List

import httpx

doi_pattern = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"


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
