import logging
import re
import sys
import time
from typing import Literal, Optional

import requests
from bs4 import BeautifulSoup
from scholarly import scholarly

from .utils import (
    DOI_PATTERN,
    PAPER_URL,
    SEARCH_API_CACHE,
    SEARCH_API_KEY,
    SS_API_KEY,
    _resolve_backend,
    _semantic_scholar_requests_get_with_backoff,
    save_search_api_cache,
    search_api_requests_get,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# SearchApi queries are stochastic.
_SEARCH_API_ATTEMPTS = 3


def _get_searchapi_citation_entry(
    title_or_doi: str,
    format: Literal["endnote", "bibtex"],
    api_key: Optional[str],
) -> str:
    """Fetch a BibTeX or EndNote export through SearchApi."""
    data_cid = _get_searchapi_data_cid(title_or_doi, api_key)
    for attempt in range(_SEARCH_API_ATTEMPTS):
        response = search_api_requests_get(
            api_key=api_key,
            params={
                "engine": "google_scholar_cite",
                "data_cid": data_cid,
                "hl": "en",
                "no_cache": "true",
            },
        )
        link = next(
            (
                entry.get("link")
                for entry in response.json().get("links", [])
                if entry.get("title", "").casefold() == format
            ),
            None,
        )
        if link:
            try:
                return _get_searchapi_export(link, format)
            except requests.exceptions.HTTPError:
                if attempt >= _SEARCH_API_ATTEMPTS - 1:
                    raise
                # Export links can be stale even when the cite response succeeds.
                time.sleep(1)
                continue
        if attempt < _SEARCH_API_ATTEMPTS - 1:
            # SearchAPI may intermittently return no cite results for a valid CID.
            time.sleep(1)

    raise RuntimeError(
        f"SearchApi returned no {format} export for data_cid {data_cid!r}."
    )


def _get_searchapi_data_cid(title_or_doi: str, api_key: Optional[str]) -> str:
    """Resolve a title or DOI to an exact Google Scholar data CID."""
    doi = re.search(DOI_PATTERN, title_or_doi, re.IGNORECASE)
    search_title = title_or_doi

    def find_exact(title: str) -> Optional[str]:
        normalized_title = _normalize_citation_title(title)
        # SearchApi results can vary between requests, so retry exact matching.
        for query in ("allintitle", "plain"):
            for _ in range(_SEARCH_API_ATTEMPTS):
                for paper in _search_searchapi_title(title, api_key, query=query):
                    if (
                        paper.get("data_cid")
                        and _normalize_citation_title(paper.get("title", ""))
                        == normalized_title
                    ):
                        return paper["data_cid"]
        return None

    if doi:
        response = _semantic_scholar_requests_get_with_backoff(
            f"{PAPER_URL}DOI:{doi.group(0)}",
            params={"fields": "title"},
            max_retries=3,
        )
        paper = response.json()
        search_title = paper.get("title", "")
        data_cid = find_exact(search_title) if search_title else None
        if data_cid:
            return data_cid
    else:
        data_cid = find_exact(search_title)
        if data_cid:
            return data_cid
    raise RuntimeError(
        f"SearchApi returned no exact Scholar match for {title_or_doi!r}."
    )


def _get_searchapi_cites_params(title: str, api_key: Optional[str]) -> list[dict]:
    """Resolve a title to parameters accepted by Scholar's cites query."""
    normalized_title = _normalize_citation_title(title)
    for query in ("allintitle", "plain"):
        for _ in range(_SEARCH_API_ATTEMPTS):
            data = _search_searchapi_title_data(title, api_key, query=query)
            exact_matches = [
                paper
                for paper in data.get("organic_results", [])
                if _normalize_citation_title(paper.get("title", "")) == normalized_title
            ]
            preferred_matches = [
                paper for paper in exact_matches if paper.get("type") != "CITATION"
            ] or exact_matches
            cites_params = []
            for paper in preferred_matches:
                cited_by = paper.get("inline_links", {}).get("cited_by", {})
                cites_id = cited_by.get("cites_id")
                if cites_id:
                    cites_params.append(
                        {"cites": cites_id, "total": cited_by.get("total")}
                    )
            if cites_params:
                return cites_params

            data_cids = {
                paper["data_cid"]
                for paper in preferred_matches
                if paper.get("data_cid")
            }
            html_url = data.get("search_metadata", {}).get("html_url")
            if html_url and data_cids:
                cites_params = _get_searchapi_cites_params_from_html(
                    html_url, data_cids, api_key
                )
                if cites_params:
                    return cites_params
    raise RuntimeError(f"SearchApi returned no exact cited-by match for {title!r}.")


def _get_searchapi_cites_params_from_html(
    html_url: str, data_cids: set[str], api_key: Optional[str]
) -> list[dict]:
    """Extract exact-result cites parameters from SearchApi Scholar HTML."""
    response = search_api_requests_get(api_key=api_key, url=html_url)
    soup = BeautifulSoup(response.text, "html.parser")
    cites_params = []
    for result in soup.select(".gs_r[data-cid]"):
        if result.get("data-cid") not in data_cids:
            continue
        cited_by = result.select_one('a[href*="cites="]')
        match = (
            re.search(r"[?&]cites=([^&]+)", cited_by.get("href", ""))
            if cited_by
            else None
        )
        count = (
            re.fullmatch(r"Cited by ([\d,]+)", cited_by.get_text(" ", strip=True))
            if cited_by
            else None
        )
        params = (
            {
                "cites": match.group(1),
                "total": int(count.group(1).replace(",", "")) if count else None,
            }
            if match
            else None
        )
        if params and params not in cites_params:
            cites_params.append(params)
    return cites_params


def _get_searchapi_citing_papers(
    title: str,
    api_key: Optional[str],
    max_results: Optional[int] = None,
) -> list[dict]:
    """Retrieve papers from Google Scholar Cited By result pages."""
    if max_results == 0:
        return []

    cites_params = _get_searchapi_cites_params(title, api_key)
    for cites_query in cites_params:
        papers = []
        total = cites_query.get("total")
        max_pages = (total + 19) // 20 if total else None
        page = 1
        while True:
            data = _get_searchapi_citing_page(cites_query, page, api_key)
            if data is None:
                break

            page_results = [
                paper for paper in data.get("organic_results", []) if paper.get("title")
            ]
            papers.extend(page_results)
            if not page_results:
                return papers
            if max_results is not None and len(papers) >= max_results:
                return papers[:max_results]
            if max_pages is not None and page >= max_pages:
                return papers
            if max_pages is None:
                if not page_results or (
                    not data.get("pagination", {}).get("next")
                    and len(page_results) < 20
                ):
                    return papers
            page += 1
    raise RuntimeError(f"SearchApi returned no Cited By results for {title!r}.")


def _get_searchapi_citing_page(
    cites_query: dict,
    page: int,
    api_key: Optional[str],
) -> Optional[dict]:
    """Retrieve one Google Scholar Cited By page with bounded retries."""
    last_error = None
    last_response_error = None
    for attempt in range(_SEARCH_API_ATTEMPTS):
        try:
            data = search_api_requests_get(
                api_key=api_key,
                params={
                    "engine": "google_scholar",
                    "hl": "en",
                    "num": 20,
                    "page": page,
                    "cites": cites_query["cites"],
                    "as_sdt": 0,
                    "filter": 1,
                },
            ).json()
        except requests.exceptions.RequestException as exc:
            last_error = exc
            data = None
        if data is not None and data.get("error"):
            last_response_error = data["error"]
        if data is not None and "error" not in data and data.get("organic_results"):
            return data
        if (
            attempt == _SEARCH_API_ATTEMPTS - 1
            and data is not None
            and "error" not in data
        ):
            return data
        if attempt < _SEARCH_API_ATTEMPTS - 1:
            # SearchAPI may intermittently fail a valid Cited By query.
            time.sleep(5)
    if last_error is not None:
        raise last_error
    if last_response_error is not None:
        if (
            page > 1
            and last_response_error == "Google Scholar didn't return any results."
        ):
            return {}
        raise RuntimeError(f"SearchApi Cited By error: {last_response_error}")
    return None


def _search_searchapi_title(
    title: str, api_key: Optional[str], *, query: str = "allintitle"
) -> list[dict]:
    """Search Google Scholar for a title and return organic results."""
    return _search_searchapi_title_data(title, api_key, query=query).get(
        "organic_results", []
    )


def _search_searchapi_title_data(
    title: str, api_key: Optional[str], *, query: str = "allintitle"
) -> dict:
    """Search Google Scholar for a title and return the full response."""
    if not title:
        return {}
    search_query = f"allintitle: {title}" if query == "allintitle" else title
    for attempt in range(_SEARCH_API_ATTEMPTS):
        try:
            response = search_api_requests_get(
                api_key=api_key,
                params={
                    "engine": "google_scholar",
                    "q": search_query,
                    "hl": "en",
                    "num": 20,
                    "as_sdt": 0,
                },
            )
            return response.json()
        except requests.exceptions.RequestException:
            if attempt == _SEARCH_API_ATTEMPTS - 1:
                raise
            time.sleep(1)
    return {}


def _normalize_citation_title(title: str) -> str:
    """Normalize a title for exact Scholar result matching."""
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()


def _get_searchapi_export(link: str, format: Literal["endnote", "bibtex"]) -> str:
    """Fetch citation text from a Google Scholar export link."""
    for attempt in range(_SEARCH_API_ATTEMPTS):
        export = requests.get(
            link,
            headers={
                "Referer": "https://scholar.google.com/",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=90,
        )
        if export.ok:
            citation = export.text.strip()
            if not citation:
                raise RuntimeError(f"SearchApi returned an empty {format} export.")
            return citation
        if export.status_code not in {429, 500, 502, 503, 504}:
            export.raise_for_status()
        if attempt < _SEARCH_API_ATTEMPTS - 1:
            # Google Scholar export links can transiently reject a fresh request.
            time.sleep(1)
    export.raise_for_status()
    raise RuntimeError(f"Could not retrieve the {format} export.")


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


def _cache_search_api_citation(title: str, count: int) -> int:
    """Cache a citation count and persist the SearchApi cache."""
    SEARCH_API_CACHE["citations"][title] = count
    save_search_api_cache()
    return count


def _get_citation_count_from_searchapi_html(
    html_url: str, data_cids: set[str], api_key: Optional[str]
) -> Optional[int]:
    """Retrieve citation counts omitted from a SearchApi JSON response."""
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


def _resolve_citation_backend(backend: str, api_key: Optional[str]) -> str:
    """Resolve the citation backend."""
    return _resolve_backend(
        backend,
        api_key,
        (("searchapi", SEARCH_API_KEY), ("semantic_scholar", SS_API_KEY)),
        "scholarly",
    )
