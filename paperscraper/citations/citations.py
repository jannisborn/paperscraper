import logging
import sys
from typing import Literal, Optional

from semanticscholar import SemanticScholarException

from .searchapi import get_citation_count_from_searchapi_author  # noqa: F401
from .searchapi import (
    _get_citations_from_title_scholarly,
    _get_citations_from_title_searchapi,
    _get_citations_from_title_semantic_scholar,
    _get_searchapi_citation_entry,
    _get_searchapi_citing_paper_titles,
    _resolve_citation_backend,
)
from .utils import PAPER_URL, _semantic_scholar_requests_get_with_backoff

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

    return _get_searchapi_citation_entry(title_or_doi.strip(), format, api_key)


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
    *,
    api_key: Optional[str] = None,
) -> list[str]:
    """Return titles of papers citing a paper on Google Scholar.

    The title is matched exactly before SearchAPI requests the papers citing
    it. By default all pages are retrieved. Set ``max_results`` to limit the
    result count. Each SearchAPI request/page returns up to 20 entries.
    """
    if not isinstance(title, str):
        raise TypeError(f"Pass str not {type(title)}")
    if max_results is not None and (
        not isinstance(max_results, int) or isinstance(max_results, bool)
    ):
        raise TypeError(f"Pass int or None not {type(max_results)}")
    if max_results is not None and max_results < 0:
        raise ValueError("max_results must be non-negative")
    return _get_searchapi_citing_paper_titles(
        title.strip(), api_key, max_results=max_results
    )


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
