import logging
import re
import sys
from typing import Iterable, Literal, Optional

from scholarly import scholarly
from semanticscholar import SemanticScholarException

from ..searchapi.core import SEARCH_API_KEY, SearchAPICitations, SearchAPIClient
from ..utils import _resolve_backend
from .entity import Paper
from .utils import (
    DOI_PATTERN,
    PAPER_URL,
    SS_API_KEY,
    _semantic_scholar_requests_get_with_backoff,
    get_doi_from_title,
)

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


def get_citation_entry(
    title_or_doi: str,
    format: Literal["endnote", "bibtex"] = "bibtex",
    *,
    api_key: Optional[str] = None,
) -> str:
    """Return a BibTeX or EndNote entry for a paper found on Google Scholar.

    ``title_or_doi`` may be a paper title or DOI. DOI inputs require an
    additional Semantic Scholar request to resolve the DOI to a title before
    searching Google Scholar. The SearchAPI key is read from ``SEARCH_API_KEY``
    unless ``api_key`` is provided.
    """
    if not isinstance(title_or_doi, str):
        raise TypeError(f"Pass str not {type(title_or_doi)}")
    if format not in {"endnote", "bibtex"}:
        raise ValueError("format must be 'endnote' or 'bibtex'")

    title_or_doi = title_or_doi.strip()
    doi = re.search(DOI_PATTERN, title_or_doi, re.IGNORECASE)
    search_title = None
    if doi:
        response = _semantic_scholar_requests_get_with_backoff(
            f"{PAPER_URL}DOI:{doi.group(0)}",
            params={"fields": "title"},
            base_delay=5.0,
            factor=2.0,
        )
        search_title = response.json().get("title") or ""
    return SearchAPICitations(SearchAPIClient(api_key)).get_citation_entry(
        title_or_doi, format, search_title=search_title
    )


def get_bibtex_entry(title_or_doi: str, *, api_key: Optional[str] = None) -> str:
    """Return a BibTeX entry for a paper title or DOI.

    DOI inputs consume an additional Semantic Scholar request to resolve the
    DOI before the Google Scholar SearchAPI lookup.
    """
    return get_citation_entry(title_or_doi, format="bibtex", api_key=api_key)


def get_endnote_entry(title_or_doi: str, *, api_key: Optional[str] = None) -> str:
    """Return an EndNote entry for a paper title or DOI.

    DOI inputs consume an additional Semantic Scholar request to resolve the
    DOI before the Google Scholar SearchAPI lookup.
    """
    return get_citation_entry(title_or_doi, format="endnote", api_key=api_key)


def get_citing_papers_from_title(
    title: str,
    max_results: Optional[int] = None,
    full_info: bool = False,
    *,
    api_key: Optional[str] = None,
    ss_api_key: Optional[str] = None,
) -> list[Paper]:
    """Return papers citing a paper on Google Scholar.

    The title is matched exactly before SearchAPI requests the papers citing
    it. By default all pages are retrieved. Set ``max_results`` to limit the
    result count. SearchApi pages contain up to 20 entries. By default only
    titles are populated. ``full_info=True`` also populates authors and
    resolves available DOIs through Semantic Scholar, consuming one Semantic
    Scholar request per result. API keys default to ``SEARCH_API_KEY`` and
    ``SS_API_KEY`` respectively.
    Raises ``RuntimeError`` if retrieval ends below the advertised citation
    count, rather than returning an incomplete list as a complete result.
    """
    if not isinstance(title, str):
        raise TypeError(f"Pass str not {type(title)}")
    if max_results is not None and (
        not isinstance(max_results, int) or isinstance(max_results, bool)
    ):
        raise TypeError(f"Pass int or None not {type(max_results)}")
    if max_results is not None and max_results < 0:
        raise ValueError("max_results must be non-negative")
    if not isinstance(full_info, bool):
        raise TypeError(f"Pass bool not {type(full_info)}")

    results = SearchAPICitations(SearchAPIClient(api_key)).get_citing_papers(
        title.strip(), max_results=max_results
    )
    papers = []
    for result in results:
        paper_title = result["title"]
        authors = []
        doi = ""
        if full_info:
            authors = [
                author["name"]
                for author in result.get("authors", [])
                if author.get("name")
            ]
            doi = get_doi_from_title(paper_title, api_key=ss_api_key) or ""
        papers.append(Paper(paper_title, doi=doi, authors=authors))
    return papers


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
        return get_citations_from_title_searchapi(title, api_key)
    raise ValueError(f"Unknown backend: {backend}")


def get_citation_count_from_searchapi_author(
    title: str,
    api_key: Optional[str] = None,
    *,
    author_names: Optional[Iterable[str]] = None,
) -> Optional[int]:
    """Retrieve a canonical count through a matching Scholar author profile."""
    return SearchAPICitations(SearchAPIClient(api_key)).get_citation_count_from_author(
        title, author_names=author_names
    )


def get_citations_from_title_searchapi(title: str, api_key: Optional[str]) -> int:
    """Retrieve a Google Scholar citation count through SearchApi."""
    return SearchAPICitations(SearchAPIClient(api_key)).get_citations_from_title(title)


def _get_citations_from_title_scholarly(title: str) -> int:
    """Retrieve a Google Scholar citation count through scholarly."""
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
    """Retrieve a Semantic Scholar citation count."""
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


def _resolve_citation_backend(backend: str, api_key: Optional[str]) -> str:
    """Resolve the citation backend."""
    return _resolve_backend(
        backend,
        api_key,
        (("searchapi", SEARCH_API_KEY), ("semantic_scholar", SS_API_KEY)),
        "scholarly",
    )
