import logging
import re
import sys
from typing import Iterable, Literal, Optional

from bs4 import BeautifulSoup
from scholarly import scholarly
from semanticscholar import SemanticScholarException

from .utils import (
    PAPER_URL,
    SEARCH_API_CACHE,
    SEARCH_API_KEY,
    SS_API_KEY,
    _semantic_scholar_requests_get_with_backoff,
    save_search_api_cache,
    search_api_requests_get,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# Identical SearchApi queries can return different Google Scholar result sets.
_SEARCH_API_ATTEMPTS = 3


def get_citations_by_doi(doi: str) -> int:
    """
    Get the number of citations of a paper according to semantic scholar.

    Args:
        doi: the DOI of the paper.

    Returns:
        The number of citations
    """

    try:
        response = _semantic_scholar_requests_get_with_backoff(
            f"{PAPER_URL}DOI:{doi}",
            params={"fields": "citationCount"},
            max_retries=14,
            raise_for_status=False,
        )
        if response.status_code == 404:
            logger.warning(f"Could not find paper {doi}, assuming 0 citation.")
            return 0
        response.raise_for_status()
        return response.json()["citationCount"]
    except SemanticScholarException.ObjectNotFoundException:
        logger.warning(f"Could not find paper {doi}, assuming 0 citation.")
        return 0


def get_citations_from_title(
    title: str,
    backend: Literal["auto", "scholarly", "semantic_scholar", "searchapi"] = "auto",
    *,
    api_key: Optional[str] = None,
) -> int:
    """
    Retrieve a paper's citation count by title.

    Args:
        title: Paper title.
        backend: Citation backend. ``auto`` prefers configured APIs.
        api_key: Explicit API key. Not valid with ``auto``.

    Raises:
        TypeError: If sth else than str is passed.
        ValueError: If the backend or API key configuration is invalid.
        RuntimeError: If SearchApi returns incomplete citation data.

    Returns:
        Number of citations of paper.
    """

    if not isinstance(title, str):
        raise TypeError(f"Pass str not {type(title)}")

    title = title.strip()
    resolved_backend = _resolve_citation_backend(backend, api_key)
    if resolved_backend == "scholarly":
        if api_key is not None:
            raise ValueError("api_key is not supported by backend='scholarly'")
        return _get_citations_from_title_scholarly(title)
    if resolved_backend == "semantic_scholar":
        return _get_citations_from_title_semantic_scholar(title, api_key)
    if resolved_backend == "searchapi":
        return _get_citations_from_title_searchapi(title, api_key)
    raise ValueError(f"Unknown backend: {backend}")


def _get_citations_from_title_scholarly(title: str) -> int:
    """
    Retrieve a Google Scholar citation count through scholarly.

    Args:
        title: Paper title.

    Returns:
        Citation count.
    """
    matches = scholarly.search_pubs(f'"{title}"')
    counts = [int(paper["num_citations"]) for paper in matches]
    if len(counts) == 0:
        logger.warning(f"Found no match for {title}.")
        return 0
    if len(counts) > 1:
        logger.warning(f"Found {len(counts)} matches for {title}, returning first one.")
    return counts[0]


def _get_citations_from_title_semantic_scholar(
    title: str, api_key: Optional[str]
) -> int:
    """
    Retrieve a Semantic Scholar citation count.

    Args:
        title: Paper title.
        api_key: Explicit API key.

    Returns:
        Citation count.
    """
    response = _semantic_scholar_requests_get_with_backoff(
        f"{PAPER_URL}search",
        params={"query": title, "fields": "citationCount", "limit": 1},
        api_key=api_key,
    )
    matches = response.json().get("data", [])
    if not matches:
        logger.warning(f"Found no match for {title}.")
        return 0
    return int(matches[0].get("citationCount") or 0)


def _get_citations_from_title_searchapi(title: str, api_key: Optional[str]) -> int:
    """
    Retrieve a Google Scholar citation count through SearchApi.

    Args:
        title: Paper title.
        api_key: Explicit API key.

    Returns:
        Citation count.
    """
    normalized_title = " ".join(title.casefold().split())
    citation_cache = SEARCH_API_CACHE["citations"]
    if title in citation_cache:
        return citation_cache[title]

    search_ids = []
    author_names = set()
    for _ in range(_SEARCH_API_ATTEMPTS):
        response = search_api_requests_get(
            api_key=api_key,
            params={
                "engine": "google_scholar",
                "q": f'"{title}"',
                "hl": "en",
                "num": 20,
            },
        )
        data = response.json()
        metadata = data.get("search_metadata", {})
        search_ids.append(metadata.get("id", "unknown"))
        author_names.update(
            author["name"]
            for paper in data.get("organic_results", [])
            if " ".join(paper.get("title", "").casefold().split()).startswith(
                normalized_title
            )
            for author in paper.get("authors", [])
            if author.get("name")
        )
        exact_matches = [
            paper
            for paper in data.get("organic_results", [])
            if " ".join(paper.get("title", "").casefold().split()) == normalized_title
        ]
        if not exact_matches:
            continue

        preferred_matches = [
            paper for paper in exact_matches if paper.get("type") != "CITATION"
        ] or exact_matches
        counts = {
            int(cited_by["total"])
            for paper in preferred_matches
            if (cited_by := paper.get("inline_links", {}).get("cited_by", {})).get(
                "total"
            )
            is not None
        }
        if len(counts) == 1:
            count = counts.pop()
            return _cache_search_api_citation(title, count)
        if len(counts) > 1:
            raise RuntimeError(f"SearchApi returned conflicting counts for {title!r}.")

        data_cids = {
            paper["data_cid"] for paper in preferred_matches if paper.get("data_cid")
        }
        html_url = metadata.get("html_url")
        if html_url and data_cids:
            count = _get_citation_count_from_searchapi_html(
                html_url, data_cids, api_key
            )
            if count is not None:
                return _cache_search_api_citation(title, count)

    count = get_citation_count_from_searchapi_author(
        title, api_key, author_names=author_names
    )
    if count is not None:
        return _cache_search_api_citation(title, count)

    raise RuntimeError(
        f"SearchApi returned no complete exact match for {title!r} "
        f"(search IDs: {', '.join(search_ids)})."
    )


def _cache_search_api_citation(title: str, count: int) -> int:
    """Cache a citation count and persist the SearchApi cache."""
    SEARCH_API_CACHE["citations"][title] = count
    save_search_api_cache()
    return count


def _get_citation_count_from_searchapi_html(
    html_url: str, data_cids: set[str], api_key: Optional[str]
) -> Optional[int]:
    """
    Retrieve citation counts omitted from a SearchApi JSON response.

    Args:
        html_url: Archived SearchApi HTML URL.
        data_cids: Exact-match result identifiers.
        api_key: Explicit API key.

    Returns:
        Citation count if available.
    """
    response = search_api_requests_get(api_key=api_key, url=html_url)
    soup = BeautifulSoup(response.text, "html.parser")
    counts = set()
    for result in soup.select(".gs_r[data-cid]"):
        if result.get("data-cid") not in data_cids:
            continue
        cited_by = result.select_one('a[href*="cites="]')
        if cited_by is None:
            continue
        match = re.fullmatch(r"Cited by ([\d,]+)", cited_by.get_text(" ", strip=True))
        if match:
            counts.add(int(match.group(1).replace(",", "")))

    if len(counts) > 1:
        raise RuntimeError("SearchApi HTML returned conflicting citation counts.")
    return counts.pop() if counts else None


def get_citation_count_from_searchapi_author(
    title: str,
    api_key: Optional[str] = None,
    *,
    author_names: Optional[Iterable[str]] = None,
) -> Optional[int]:
    """
    Retrieve a canonical count through a matching Scholar author profile.

    Args:
        title: Paper title.
        api_key: Explicit API key.
        author_names: Candidate author names, if already known.

    Returns:
        Citation count if a matching author article is available.
    """
    normalized_title = " ".join(title.casefold().split())
    candidate_authors = set(author_names or ())

    # Discover authors when the initial paper search did not provide them.
    for _ in range(_SEARCH_API_ATTEMPTS):
        if candidate_authors:
            break
        response = search_api_requests_get(
            api_key=api_key,
            params={
                "engine": "google_scholar",
                "q": f"allintitle: {title}",
                "hl": "en",
                "num": 20,
            },
        )
        candidate_authors.update(
            author["name"]
            for paper in response.json().get("organic_results", [])
            if " ".join(paper.get("title", "").casefold().split()).startswith(
                normalized_title
            )
            for author in paper.get("authors", [])
            if author.get("name")
        )

    # Resolve the most specific candidate names to Scholar profiles.
    for author_name in sorted(candidate_authors, key=len, reverse=True)[:3]:
        response = search_api_requests_get(
            api_key=api_key,
            params={
                "engine": "google_scholar",
                "q": f"author:{author_name}",
                "hl": "en",
                "num": 20,
            },
        )
        for profile in response.json().get("profiles", [])[:3]:
            author_id = profile.get("author_id")
            if not author_id:
                continue

            # Only accept a citation_id from an exact article-title match.
            response = search_api_requests_get(
                api_key=api_key,
                params={
                    "engine": "google_scholar_author",
                    "author_id": author_id,
                },
            )
            article = next(
                (
                    article
                    for article in response.json().get("articles", [])
                    if " ".join(article.get("title", "").casefold().split())
                    == normalized_title
                ),
                None,
            )
            if article is None or not article.get("citation_id"):
                continue

            # Fetch the paper-level count and verify the title once more.
            response = search_api_requests_get(
                api_key=api_key,
                params={
                    "engine": "google_scholar_author",
                    "view_op": "view_citation",
                    "citation_id": article["citation_id"],
                },
            )
            scholar_article = (
                response.json().get("citation", {}).get("scholar_articles", {})
            )
            if (
                " ".join(scholar_article.get("title", "").casefold().split())
                != normalized_title
            ):
                continue
            total = scholar_article.get("cited_by", {}).get("total")
            if total is not None:
                return int(total)
    return None


def _resolve_citation_backend(backend: str, api_key: Optional[str]) -> str:
    """
    Resolve the citation backend.

    Args:
        backend: Requested backend.
        api_key: Explicit API key.

    Returns:
        Resolved backend.
    """
    if backend != "auto":
        return backend
    if api_key is not None:
        raise ValueError("api_key cannot be used with backend='auto'")
    if SEARCH_API_KEY:
        return "searchapi"
    if SS_API_KEY:
        return "semantic_scholar"
    return "scholarly"
