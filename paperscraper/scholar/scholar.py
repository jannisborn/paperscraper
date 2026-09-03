import logging
import re
import sys
from typing import Dict, List, Literal, Optional, Tuple

import pandas as pd
import requests
from scholarly import scholarly

from ..citations.utils import SEARCH_API_KEY, _resolve_backend, search_api_requests_get
from ..utils import dump_papers

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


scholar_field_mapper = {
    "venue": "journal",
    "author": "authors",
    "cites": "citations",
    "pub_year": "year",
}
process_fields = {"year": lambda x: int(x) if x.isdigit() else -1, "citations": int}


def get_scholar_papers(
    title: str,
    fields: List = ["title", "authors", "year", "abstract", "journal", "citations"],
    backend: Literal["auto", "scholarly", "searchapi"] = "auto",
    *,
    api_key: Optional[str] = None,
    search_api_kwargs: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Performs Google Scholar API request of a given title and returns list of papers with
    fields as desired.

    Args:
        title: Google Scholar search query.
        fields: List of strings with fields to keep in output.
        backend: Scholar backend. ``auto`` uses SearchApi when configured.
        api_key: Explicit SearchApi key.
        search_api_kwargs: SearchApi-specific keyword arguments.

    Returns:
        pd.DataFrame. One paper per row.

    """
    if not isinstance(title, str):
        raise TypeError(f"Pass str not {type(title)}")

    if re.search(r"\b(?:AND|OR)\b", title):
        logger.info(
            "NOTE: Scholar API cannot be used with Boolean logic in keywords."
            " Query should be a single string to be entered in the Scholar search field."
        )

    resolved_backend = _resolve_backend(
        backend, api_key, (("searchapi", SEARCH_API_KEY),), "scholarly"
    )
    if resolved_backend == "searchapi":
        return get_scholar_papers_searchapi(
            title,
            fields,
            api_key,
            search_api_kwargs=search_api_kwargs,
        )
    if resolved_backend != "scholarly":
        raise ValueError(f"Unknown backend: {backend}")
    if api_key is not None:
        raise ValueError("api_key is not supported by backend='scholarly'")

    matches = scholarly.search_pubs(title)

    processed = []
    for paper in matches:
        # Extracts title, author, year, journal, abstract
        entry = {
            scholar_field_mapper.get(key, key): process_fields.get(
                scholar_field_mapper.get(key, key), lambda x: x
            )(value)
            for key, value in paper["bib"].items()
            if scholar_field_mapper.get(key, key) in fields
        }

        entry["citations"] = paper["num_citations"]
        processed.append(entry)

    return pd.DataFrame(processed)


def get_scholar_papers_searchapi(
    title: str,
    fields: List = ["title", "authors", "year", "abstract", "journal", "citations"],
    api_key: Optional[str] = None,
    search_api_kwargs: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Retrieve Google Scholar paper metadata through SearchApi.

    Args:
        title: Google Scholar search query.
        fields: List of strings with fields to keep in output.
        api_key: Explicit SearchApi key.
        search_api_kwargs: Supports ``top_k``, ``num_enrich`` and
            ``max_author_requests``.

    Returns:
        pd.DataFrame. One paper per row.
    """
    resolved_kwargs = _resolve_search_api_kwargs(search_api_kwargs)
    response = search_api_requests_get(
        api_key=api_key,
        params={
            "engine": "google_scholar",
            "q": title,
            "hl": "en",
            "num": resolved_kwargs["top_k"],
        },
    )

    processed = []
    for index, paper in enumerate(response.json().get("organic_results", [])):
        # Search result snippets are not abstracts; only the citation view exposes one.
        citation = (
            get_searchapi_scholar_citation(
                paper,
                api_key,
                search_api_kwargs=resolved_kwargs,
            )
            if index < resolved_kwargs["num_enrich"]
            else {}
        )
        entry = _parse_searchapi_scholar_result(paper, citation)
        processed.append({key: value for key, value in entry.items() if key in fields})

    return pd.DataFrame(processed, columns=fields)


def _resolve_search_api_kwargs(search_api_kwargs: Optional[dict]) -> Dict[str, int]:
    """Resolve SearchApi Scholar keyword arguments with defaults."""
    kwargs = {"top_k": 20, "num_enrich": 3, "max_author_requests": 9}
    kwargs.update(search_api_kwargs or {})
    return kwargs


def _parse_searchapi_scholar_result(paper: dict, citation: dict) -> dict:
    """Parse SearchApi Scholar result fields into paperscraper metadata."""
    publication = _normalize_searchapi_text(paper.get("publication", ""))
    citation_date = citation.get("publication_date") or ""
    year = citation_date[:4] if re.match(r"(?:19|20)\d{2}", citation_date) else None
    year = year or citation.get("year") or _parse_searchapi_year(publication)

    cited_by = paper.get("inline_links", {}).get("cited_by", {})
    citations = citation.get("cited_by", {}).get("total")
    citations = citations if citations is not None else cited_by.get("total")

    return {
        "title": citation.get("title") or paper.get("title", ""),
        "authors": _parse_searchapi_authors(paper, citation),
        "year": int(year) if year else -1,
        "date": citation_date,
        "abstract": citation.get("description", ""),
        "snippet": paper.get("snippet", ""),
        "journal": citation.get("journal") or _parse_searchapi_journal(publication),
        "citations": int(citations) if citations is not None else -1,
    }


def get_searchapi_scholar_citation(
    paper: dict,
    api_key: Optional[str] = None,
    search_api_kwargs: Optional[dict] = None,
) -> dict:
    """
    Retrieve citation details for a SearchApi Scholar result when available.

    Args:
        paper: SearchApi ``google_scholar`` organic result.
        api_key: Explicit SearchApi key.
        search_api_kwargs: Supports ``max_author_requests``.

    Returns:
        SearchApi ``google_scholar_author`` citation dict. Common entries are
        ``title``, ``link``, ``resources``, ``description``, ``authors``,
        ``publication_date``, ``journal``, ``volume``, ``issue``, ``pages``,
        ``publisher``, ``cited_by``, ``cites_histogram``, and
        ``scholar_articles``. Returns an empty dict if no exact title match is found.
    """
    resolved_kwargs = _resolve_search_api_kwargs(search_api_kwargs)
    title = paper.get("title", "")
    citations = []
    remaining_requests = max(0, resolved_kwargs["max_author_requests"])
    authors = [author for author in paper.get("authors", [])[:3] if author.get("id")]
    for index, author in enumerate(authors):
        if remaining_requests < 2:
            break
        author_id = author.get("id")
        author_count = len(authors) - index
        reserved_requests = 2 * (author_count - 1) + 1
        page_requests = max(1, remaining_requests - reserved_requests)
        citation_id, requests_used = _find_searchapi_citation_id(
            title, author_id, api_key, page_requests
        )
        remaining_requests -= requests_used
        if not citation_id:
            continue
        if remaining_requests < 1:
            break
        remaining_requests -= 1
        try:
            citation = (
                search_api_requests_get(
                    api_key=api_key,
                    params={
                        "engine": "google_scholar_author",
                        "view_op": "view_citation",
                        "citation_id": citation_id,
                        "hl": "en",
                    },
                )
                .json()
                .get("citation", {})
            )
        except requests.exceptions.RequestException:
            continue
        citations.append(citation)
    return max(
        citations,
        key=lambda citation: int(citation.get("cited_by", {}).get("total") or -1),
        default={},
    )


def _find_searchapi_citation_id(
    title: str, author_id: str, api_key: Optional[str], max_requests: int
) -> Tuple[Optional[str], int]:
    """Find an author-profile citation id by exact normalized title match."""
    normalized_title = _normalize_searchapi_title(title)
    pages = {}
    request_count = 0

    def search_page(page: int) -> Tuple[str, Optional[str], bool]:
        nonlocal request_count
        if page not in pages:
            if request_count >= max_requests:
                return "limit", None, False
            request_count += 1
            try:
                pages[page] = search_api_requests_get(
                    api_key=api_key,
                    params={
                        "engine": "google_scholar_author",
                        "author_id": author_id,
                        "sortby": "title",
                        "page": page,
                        "hl": "en",
                    },
                ).json()
            except requests.exceptions.RequestException:
                return "error", None, False
        return _get_searchapi_title_page_position(pages[page], normalized_title)

    status, citation_id, has_next = search_page(1)
    if citation_id or status != "after" or not has_next:
        return citation_id, request_count

    low_page = 2
    high_page = None
    probe_page = min(
        _get_searchapi_author_initial_probe_page(normalized_title),
        2 ** max(1, max_requests - 1),
    )

    while request_count < max_requests:
        status, citation_id, has_next = search_page(probe_page)
        if citation_id:
            return citation_id, request_count
        if status in {"before", "empty"}:
            high_page = probe_page - 1
            break
        if status in {"error", "limit", "miss"} or (status == "after" and not has_next):
            return None, request_count
        low_page = probe_page + 1
        probe_page *= 2

    while (
        high_page is not None and low_page <= high_page and request_count < max_requests
    ):
        page = (low_page + high_page) // 2
        status, citation_id, has_next = search_page(page)
        if citation_id:
            return citation_id, request_count
        if status in {"before", "empty"}:
            high_page = page - 1
        elif status == "after" and has_next:
            low_page = page + 1
        else:
            return None, request_count

    return None, request_count


def _get_searchapi_title_page_position(
    response: dict, normalized_title: str
) -> Tuple[str, Optional[str], bool]:
    """Compare a target title to one title-sorted author article page."""
    articles = response.get("articles", [])
    if not articles:
        return "empty", None, False

    for article in articles:
        if normalized_title == _normalize_searchapi_title(article.get("title", "")):
            return "match", article.get("citation_id"), False

    titles = [
        _normalize_searchapi_title(article.get("title", ""))
        for article in articles
        if article.get("title")
    ]
    if not titles:
        return "empty", None, False
    if normalized_title < titles[0]:
        return "before", None, False
    if normalized_title <= titles[-1]:
        return "miss", None, False
    return "after", None, bool(response.get("pagination", {}).get("next"))


def _get_searchapi_author_initial_probe_page(normalized_title: str) -> int:
    """Choose a first author-profile page probe from the title prefix."""
    first_char = normalized_title[:1]
    if first_char < "g":
        return 2
    if first_char < "n":
        return 4
    if first_char < "t":
        return 8
    return 16


def _parse_searchapi_authors(paper: dict, citation: dict) -> List[str]:
    """Parse author names from citation details or the Scholar result."""
    citation_authors = citation.get("authors")
    if citation_authors:
        return [
            author.strip() for author in citation_authors.split(",") if author.strip()
        ]

    publication_authors = _normalize_searchapi_text(paper.get("publication", "")).split(
        " - ", 1
    )[0]
    if publication_authors:
        return [
            author.strip()
            for author in publication_authors.split(",")
            if author.strip()
        ]
    return [author["name"] for author in paper.get("authors", []) if author.get("name")]


def _parse_searchapi_journal(publication: str) -> str:
    """Parse journal information from a SearchApi publication string."""
    parts = publication.split(" - ")
    if len(parts) < 2:
        return ""
    journal = parts[1]
    year = _parse_searchapi_year(journal)
    if year:
        journal = journal.rsplit(f", {year}", 1)[0]
    return journal.strip()


def _parse_searchapi_year(publication: str) -> Optional[str]:
    """Parse a publication year from SearchApi publication text."""
    match = re.search(r"\b(?:19|20)\d{2}\b", publication)
    return match.group() if match else None


def _normalize_searchapi_title(title: str) -> str:
    """Normalize titles for exact SearchApi article matching."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _normalize_searchapi_text(text: str) -> str:
    """Normalize SearchApi ellipsis characters to plain text."""
    return text.replace("\u2026", "...") if text else ""


def get_and_dump_scholar_papers(
    title: str,
    output_filepath: str,
    fields: List = ["title", "authors", "year", "abstract", "journal", "citations"],
    backend: Literal["auto", "scholarly", "searchapi"] = "auto",
    *,
    api_key: Optional[str] = None,
    search_api_kwargs: Optional[dict] = None,
) -> None:
    """
    Combines get_scholar_papers and dump_papers.

    Args:
        title: Paper to search for on Google Scholar.
        output_filepath: Path where the dump will be saved.
        fields: List of strings with fields to keep in output.
        backend: Scholar backend.
        api_key: Explicit SearchApi key.
        search_api_kwargs: SearchApi-specific keyword arguments.
    """
    papers = get_scholar_papers(
        title,
        fields,
        backend,
        api_key=api_key,
        search_api_kwargs=search_api_kwargs,
    )
    dump_papers(papers, output_filepath)
