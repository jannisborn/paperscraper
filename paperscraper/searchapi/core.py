"""SearchApi transport and Google Scholar workflows.

The client owns HTTP and cache access. Scholar and citation services compose it
and share metadata logic without importing one another's public wrappers.
Retry policies remain local to the operation that knows whether a result is complete.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

from ..utils import DOI_PATTERN, retry_with_exponential_backoff

logger = logging.getLogger(__name__)
SEARCH_API_URL = "https://www.searchapi.io/api/v1/search"
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
SEARCH_API_CACHE_PATH = os.getenv("SEARCH_API_CACHE_PATH")
_AUTHOR_PAPER_FIELDS = ["title", "authors", "publication", "year", "citations"]
_AUTHOR_DETAIL_FIELDS = [
    "journal",
    "date",
    "volume",
    "issue",
    "pages",
    "publisher",
    "description",
]
_AUTHOR_PAGE_SIZE = 20


class SearchAPIClient:
    """SearchApi HTTP transport and the shared citation cache.

    Credentials are checked when a request is made, so cached results and empty
    queries retain their existing behavior without requiring an API key.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self.cache = SEARCH_API_CACHE

    @staticmethod
    def request(url: str, **kwargs) -> requests.Response:
        """Make one request; callers supply the headers appropriate to its host."""
        return requests.get(url, timeout=90, **kwargs)

    def get(self, url: str = SEARCH_API_URL, **kwargs) -> requests.Response:
        """Perform one authenticated SearchApi request without adding retries."""
        api_key = self.api_key if self.api_key is not None else SEARCH_API_KEY
        if not api_key:
            raise ValueError(
                "SearchApi requires api_key or the SEARCH_API_KEY environment variable."
            )
        response = self.request(
            url, headers={"Authorization": f"Bearer {api_key}"}, **kwargs
        )
        response.raise_for_status()
        return response

    @staticmethod
    def load_cache(cache_path: Optional[str]) -> dict:
        """Load the shared citation cache, preserving any additional namespaces."""
        cache = (
            json.loads(Path(cache_path).read_text())
            if cache_path and Path(cache_path).is_file()
            else {}
        )
        cache.setdefault("citations", {})
        return cache

    def save_cache(self) -> None:
        """Persist the shared cache only when a path was configured."""
        if SEARCH_API_CACHE_PATH:
            Path(SEARCH_API_CACHE_PATH).write_text(
                json.dumps(self.cache, indent=2, sort_keys=True) + "\n"
            )

    def cache_citation(self, title: str, count: int) -> int:
        """Store a validated count using the original title as its cache key."""
        self.cache["citations"][title] = count
        self.save_cache()
        return count

    def get_cached_citation(self, title: str) -> int:
        """Return a cached count; raise KeyError if the title has not been cached."""
        return self.cache["citations"][title]

    def get_data(self, params: dict, *, required_key: Optional[str] = None) -> dict:
        """Fetch SearchApi JSON with bounded retries."""

        @retry_with_exponential_backoff(
            retry_if=lambda data: (
                bool(data.get("error"))
                or (required_key is not None and (not data.get(required_key)))
            ),
            exceptions=(requests.exceptions.RequestException,),
        )
        def fetch() -> dict:
            return self.get(params=params).json()

        data = fetch()
        if data.get("error"):
            raise RuntimeError(f"SearchApi request failed: {data['error']}")
        if required_key is not None and not data.get(required_key):
            raise RuntimeError(
                f"SearchApi returned no {required_key.replace('_', ' ')}."
            )
        return data


class _ScholarMetadata:
    """Shared Scholar metadata lookup, matching and response parsing.

    Both services compose this helper with their injected client. It holds no
    per-query state: request budgets and profile-page caches stay local to a call.
    """

    def __init__(self, client: SearchAPIClient) -> None:
        self.client = client

    def get_citation_details(
        self, paper: dict, search_api_kwargs: Optional[dict] = None
    ) -> dict:
        """
        Retrieve citation details for a SearchApi Scholar result when available.

        Args:
            paper: SearchApi ``google_scholar`` organic result.
            search_api_kwargs: Supports ``max_author_requests``.

        Returns:
            SearchApi ``google_scholar_author`` citation dict. Common entries are
            ``title``, ``link``, ``resources``, ``description``, ``authors``,
            ``publication_date``, ``journal``, ``volume``, ``issue``, ``pages``,
            ``publisher``, ``cited_by``, ``cites_histogram``, and
            ``scholar_articles``. Returns an empty dict if no exact title match is found.
        """
        resolved_kwargs = self.resolve_options(search_api_kwargs)
        title = paper.get("title", "")
        citations = []
        remaining_requests = max(0, resolved_kwargs["max_author_requests"])
        authors = [
            author for author in paper.get("authors", [])[:3] if author.get("id")
        ]
        for index, author in enumerate(authors):
            if remaining_requests < 2:
                break
            author_id = author.get("id")
            author_count = len(authors) - index
            reserved_requests = 2 * (author_count - 1) + 1
            page_requests = max(1, remaining_requests - reserved_requests)
            citation_id, requests_used = self._find_citation_id(
                title, author_id, page_requests
            )
            remaining_requests -= requests_used
            if not citation_id:
                continue
            if remaining_requests < 1:
                break
            remaining_requests -= 1
            try:
                citation = (
                    self.client.get(
                        params={
                            "engine": "google_scholar_author",
                            "view_op": "view_citation",
                            "citation_id": citation_id,
                            "hl": "en",
                        }
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

    def _find_citation_id(
        self, title: str, author_id: str, max_requests: int
    ) -> Tuple[Optional[str], int]:
        """Find an author-profile citation id by exact normalized title match."""
        normalized_title = self.normalize_title(title)
        pages = {}
        request_count = 0

        def search_page(page: int) -> Tuple[str, Optional[str], bool]:
            nonlocal request_count
            if page not in pages:
                if request_count >= max_requests:
                    return "limit", None, False
                request_count += 1
                try:
                    pages[page] = self.client.get(
                        params={
                            "engine": "google_scholar_author",
                            "author_id": author_id,
                            "sortby": "title",
                            "page": page,
                            "hl": "en",
                        }
                    ).json()
                except requests.exceptions.RequestException:
                    return "error", None, False
            return self._title_page_position(pages[page], normalized_title)

        status, citation_id, has_next = search_page(1)
        if citation_id or status != "after" or not has_next:
            return citation_id, request_count

        low_page = 2
        high_page = None
        probe_page = min(
            self._initial_probe_page(normalized_title), 2 ** max(1, max_requests - 1)
        )

        while request_count < max_requests:
            status, citation_id, has_next = search_page(probe_page)
            if citation_id:
                return citation_id, request_count
            if status in {"before", "empty"}:
                high_page = probe_page - 1
                break
            if status in {"error", "limit", "miss"} or (
                status == "after" and not has_next
            ):
                return None, request_count
            low_page = probe_page + 1
            probe_page *= 2

        while (
            high_page is not None
            and low_page <= high_page
            and request_count < max_requests
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

    @classmethod
    def _title_page_position(
        cls, response: dict, normalized_title: str
    ) -> Tuple[str, Optional[str], bool]:
        """Compare a target title to one title-sorted author article page."""
        articles = response.get("articles", [])
        if not articles:
            return "empty", None, False

        for article in articles:
            if normalized_title == cls.normalize_title(article.get("title", "")):
                return "match", article.get("citation_id"), False

        titles = [
            cls.normalize_title(article.get("title", ""))
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

    @staticmethod
    def _initial_probe_page(normalized_title: str) -> int:
        """Choose a first author-profile page probe from the title prefix."""
        first_char = normalized_title[:1]
        if first_char < "g":
            return 2
        if first_char < "n":
            return 4
        if first_char < "t":
            return 8
        return 16

    @staticmethod
    def resolve_options(search_api_kwargs: Optional[dict]) -> Dict[str, int]:
        """Resolve SearchApi Scholar keyword arguments with defaults."""
        kwargs = {"top_k": 20, "num_enrich": 3, "max_author_requests": 9}
        kwargs.update(search_api_kwargs or {})
        return kwargs

    @classmethod
    def parse_paper(cls, paper: dict, citation: dict) -> dict:
        """Parse SearchApi Scholar result fields into paperscraper metadata."""
        publication = cls.normalize_text(paper.get("publication", ""))
        citation_date = citation.get("publication_date") or ""
        year = citation_date[:4] if re.match(r"(?:19|20)\d{2}", citation_date) else None
        year = year or citation.get("year") or cls.parse_year(publication)

        cited_by = paper.get("inline_links", {}).get("cited_by", {})
        citations = citation.get("cited_by", {}).get("total")
        citations = citations if citations is not None else cited_by.get("total")

        return {
            "title": citation.get("title") or paper.get("title", ""),
            "authors": cls._parse_authors(paper, citation),
            "year": int(year) if year else -1,
            "date": citation_date,
            "abstract": citation.get("description", ""),
            "snippet": paper.get("snippet", ""),
            "journal": citation.get("journal") or cls._parse_journal(publication),
            "citations": int(citations) if citations is not None else -1,
        }

    @classmethod
    def _parse_authors(cls, paper: dict, citation: dict) -> List[str]:
        """Parse author names from citation details or the Scholar result."""
        citation_authors = citation.get("authors")
        if citation_authors:
            return [
                author.strip()
                for author in citation_authors.split(",")
                if author.strip()
            ]

        publication_authors = cls.normalize_text(paper.get("publication", "")).split(
            " - ", 1
        )[0]
        if publication_authors:
            return [
                author.strip()
                for author in publication_authors.split(",")
                if author.strip()
            ]
        return [
            author["name"] for author in paper.get("authors", []) if author.get("name")
        ]

    @classmethod
    def _parse_journal(cls, publication: str) -> str:
        """Parse journal information from a SearchApi publication string."""
        parts = publication.split(" - ")
        if len(parts) < 2:
            return ""
        journal = parts[1]
        year = cls.parse_year(journal)
        if year:
            journal = journal.rsplit(f", {year}", 1)[0]
        return journal.strip()

    @staticmethod
    def parse_year(publication: str) -> Optional[str]:
        """Parse a publication year from SearchApi publication text."""
        match = re.search(r"\b(?:19|20)\d{2}\b", publication)
        return match.group() if match else None

    @staticmethod
    def normalize_title(title: str) -> str:
        """Case-fold titles and ignore punctuation for Scholar article matching."""
        return re.sub("[^a-z0-9]+", " ", title.casefold()).strip()

    @staticmethod
    def normalize_match_text(author: str) -> str:
        """Case-fold and collapse whitespace, preserving punctuation for strict matches."""
        return " ".join(author.casefold().split())

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize SearchApi ellipsis characters to plain text."""
        return text.replace("…", "...") if text else ""


class SearchAPICitations:
    """Citation counts, exports and citing-paper retrieval through one client."""

    def __init__(self, client: SearchAPIClient) -> None:
        self.client = client
        self._metadata = _ScholarMetadata(client)

    def get_citation_details(
        self, paper: dict, search_api_kwargs: Optional[dict] = None
    ) -> dict:
        """Retrieve full Scholar citation metadata within the author-request budget."""
        return self._metadata.get_citation_details(paper, search_api_kwargs)

    def get_citations_from_title(self, title: str) -> int:
        """Retrieve a Google Scholar citation count through SearchApi."""
        normalized_title = self._metadata.normalize_match_text(title)
        try:
            return self.client.get_cached_citation(title)
        except KeyError:
            pass

        search_ids = []
        author_names = set()

        @retry_with_exponential_backoff(
            retry_if=lambda count: count is None, base_delay=0
        )
        def search() -> Optional[int]:
            response = self.client.get(
                params={
                    "engine": "google_scholar",
                    "q": f'"{title}"',
                    "hl": "en",
                    "num": 20,
                }
            )
            data = response.json()
            metadata = data.get("search_metadata", {})
            search_ids.append(metadata.get("id", "unknown"))
            author_names.update(
                (
                    author["name"]
                    for paper in data.get("organic_results", [])
                    if self._metadata.normalize_match_text(
                        paper.get("title", "")
                    ).startswith(normalized_title)
                    for author in paper.get("authors", [])
                    if author.get("name")
                )
            )
            exact_matches = [
                paper
                for paper in data.get("organic_results", [])
                if self._metadata.normalize_match_text(paper.get("title", ""))
                == normalized_title
            ]
            if not exact_matches:
                return None

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
                return self.client.cache_citation(title, count)
            if len(counts) > 1:
                raise RuntimeError(
                    f"SearchApi returned conflicting counts for {title!r}."
                )

            data_cids = {
                paper["data_cid"]
                for paper in preferred_matches
                if paper.get("data_cid")
            }
            html_url = metadata.get("html_url")
            if html_url and data_cids:
                count = self._get_citation_count_from_html(html_url, data_cids)
                if count is not None:
                    return self.client.cache_citation(title, count)
            return None

        count = search()
        if count is not None:
            return count

        count = self.get_citation_count_from_author(title, author_names=author_names)
        if count is not None:
            return self.client.cache_citation(title, count)

        raise RuntimeError(
            f"SearchApi returned no complete exact match for {title!r} "
            f"(search IDs: {', '.join(search_ids)})."
        )

    def get_citation_count_from_author(
        self, title: str, *, author_names: Optional[Iterable[str]] = None
    ) -> Optional[int]:
        """Retrieve a canonical count through a matching Scholar author profile."""
        normalized_title = self._metadata.normalize_match_text(title)
        candidate_authors = set(author_names or ())

        # Discover authors when the initial paper search did not provide them.
        @retry_with_exponential_backoff(retry_if=lambda found: not found, base_delay=0)
        def discover_authors() -> bool:
            response = self.client.get(
                params={
                    "engine": "google_scholar",
                    "q": f"allintitle: {title}",
                    "hl": "en",
                    "num": 20,
                }
            )
            candidate_authors.update(
                (
                    author["name"]
                    for paper in response.json().get("organic_results", [])
                    if self._metadata.normalize_match_text(
                        paper.get("title", "")
                    ).startswith(normalized_title)
                    for author in paper.get("authors", [])
                    if author.get("name")
                )
            )
            return bool(candidate_authors)

        if not candidate_authors:
            discover_authors()

        # Resolve the most specific candidate names to Scholar profiles.
        for author_name in sorted(candidate_authors, key=len, reverse=True)[:3]:
            response = self.client.get(
                params={
                    "engine": "google_scholar",
                    "q": f"author:{author_name}",
                    "hl": "en",
                    "num": 20,
                }
            )
            for profile in response.json().get("profiles", [])[:3]:
                author_id = profile.get("author_id")
                if not author_id:
                    continue

                # Only accept a citation_id from an exact article-title match.
                response = self.client.get(
                    params={"engine": "google_scholar_author", "author_id": author_id}
                )
                article = next(
                    (
                        article
                        for article in response.json().get("articles", [])
                        if self._metadata.normalize_match_text(article.get("title", ""))
                        == normalized_title
                    ),
                    None,
                )
                if article is None or not article.get("citation_id"):
                    continue

                # Fetch the paper-level count and verify the title once more.
                response = self.client.get(
                    params={
                        "engine": "google_scholar_author",
                        "view_op": "view_citation",
                        "citation_id": article["citation_id"],
                    }
                )
                scholar_article = (
                    response.json().get("citation", {}).get("scholar_articles", {})
                )
                if (
                    self._metadata.normalize_match_text(
                        scholar_article.get("title", "")
                    )
                    != normalized_title
                ):
                    continue
                total = scholar_article.get("cited_by", {}).get("total")
                if total is not None:
                    return int(total)
        return None

    def get_citation_entry(
        self,
        title_or_doi: str,
        format: Literal["endnote", "bibtex"],
        *,
        search_title: Optional[str] = None,
    ) -> str:
        """Fetch a BibTeX or EndNote export through SearchApi."""
        if search_title == "":
            raise RuntimeError(
                f"SearchApi returned no exact Scholar match for {title_or_doi!r}."
            )
        paper = self._get_paper(
            title_or_doi if search_title is None else search_title, title_or_doi
        )
        data_cid = paper["data_cid"]
        data = {}
        last_error = None

        @retry_with_exponential_backoff(
            retry_if=lambda export: export is None,
            exceptions=(requests.exceptions.RequestException,),
        )
        def fetch_export() -> Optional[str]:
            nonlocal data, last_error
            data = self.client.get(
                params={
                    "engine": "google_scholar_cite",
                    "data_cid": data_cid,
                    "hl": "en",
                    "no_cache": "true",
                }
            ).json()
            link = next(
                (
                    entry.get("link")
                    for entry in data.get("links", [])
                    if entry.get("title", "").casefold() == format
                ),
                None,
            )
            if link:
                try:
                    return self._get_export(
                        link,
                        format,
                        referer=data.get("search_metadata", {}).get("request_url"),
                    )
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    if (
                        exc.response is not None
                        and exc.response.status_code == 403
                        and data.get("citations")
                    ):
                        return self._format_export(data, paper, title_or_doi, format)
                    # Export links can be stale even when the cite response succeeds.
            # SearchApi may intermittently return no cite results for a valid CID.
            return None

        export = fetch_export()
        if export is not None:
            return export

        if data.get("citations"):
            return self._format_export(data, paper, title_or_doi, format)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"SearchApi returned no {format} export for {data_cid!r}.")

    def _get_cites_params(self, title: str) -> list[dict]:
        """Resolve a title to parameters accepted by Scholar's cites query."""
        normalized_title = self._metadata.normalize_title(title)

        @retry_with_exponential_backoff(retry_if=lambda cites_params: not cites_params)
        def find_cites_params(query: str) -> list[dict]:
            try:
                data = self._search_title_data(title, query=query)
            except requests.exceptions.RequestException:
                return []
            exact_matches = [
                paper
                for paper in data.get("organic_results", [])
                if self._metadata.normalize_title(paper.get("title", ""))
                == normalized_title
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
                return self._get_cites_params_from_html(html_url, data_cids)
            return []

        for query in ("allintitle", "plain"):
            cites_params = find_cites_params(query)
            if cites_params:
                return cites_params
        raise RuntimeError(f"SearchApi returned no exact cited-by match for {title!r}.")

    def _get_cites_params_from_html(
        self, html_url: str, data_cids: set[str]
    ) -> list[dict]:
        """Extract exact-result cites parameters from SearchApi Scholar HTML."""
        response = self.client.get(url=html_url)
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

    def get_citing_papers(
        self, title: str, max_results: Optional[int] = None
    ) -> list[dict]:
        """Retrieve papers from Google Scholar Cited By result pages."""
        if max_results == 0:
            return []

        cites_params = self._get_cites_params(title)
        papers = []
        seen = set()
        advertised_total = 0
        failures = []
        search_ids = []
        for cites_query in cites_params:
            total = cites_query.get("total") or 0
            advertised_total = max(advertised_total, total)
            attempt = 0

            # SearchApi exposes independent live pages, so retry a whole sweep after
            # an incomplete page and keep unique results from earlier sweeps.
            @retry_with_exponential_backoff(
                max_attempts=5, retry_if=lambda complete: not complete
            )
            def fetch_pages(cites_query: dict) -> bool:
                nonlocal advertised_total, attempt, total
                attempt += 1
                page_size = 20 if attempt == 1 else 10
                page = 1
                while True:
                    try:
                        data = self.client.get(
                            params={
                                "engine": "google_scholar",
                                "hl": "en",
                                "num": page_size,
                                "page": page,
                                "cites": cites_query["cites"],
                            }
                        ).json()
                    except requests.exceptions.RequestException as exc:
                        status = (
                            exc.response.status_code
                            if exc.response is not None
                            else None
                        )
                        if (
                            status is not None
                            and status not in {408, 429}
                            and status < 500
                        ):
                            raise
                        failures.append(
                            f"page {page}: HTTP {status}"
                            if status
                            else f"page {page}: {type(exc).__name__}"
                        )
                        return False
                    search_ids.append(
                        data.get("search_metadata", {}).get("id", "unknown")
                    )
                    if data.get("error"):
                        failures.append(f"page {page}: {data['error']}")
                        return False

                    total = max(
                        total,
                        data.get("search_information", {}).get("total_results") or 0,
                    )
                    advertised_total = max(advertised_total, total)
                    for paper in data.get("organic_results", []):
                        if not paper.get("title"):
                            continue
                        identity = paper.get(
                            "data_cid"
                        ) or self._metadata.normalize_title(paper["title"])
                        if identity not in seen:
                            seen.add(identity)
                            papers.append(paper)

                    required = (
                        min(total, max_results) if max_results is not None else total
                    )
                    if required and len(papers) >= required:
                        return True
                    if required:
                        if page * page_size >= required:
                            failures.append(
                                f"page {page}: {len(papers)} of {required} results"
                            )
                            return False
                    elif not data.get("pagination", {}).get("next"):
                        return True
                    page += 1

            if fetch_pages(cites_query):
                if max_results is not None and len(papers) >= max_results:
                    return papers[:max_results]
                if total and len(papers) >= total:
                    return papers
        required = (
            min(advertised_total, max_results)
            if max_results is not None
            else advertised_total
        )
        if required and len(papers) < required:
            raise RuntimeError(
                f"Incomplete SearchApi Cited By results for {title!r}: "
                f"retrieved {len(papers)} of {required} requested papers "
                f"(last failure: {failures[-1] if failures else 'unknown'}; "
                f"search IDs: {', '.join(search_ids[-5:])})."
            )
        return papers

    def _search_title(self, title: str, *, query: str = "allintitle") -> list[dict]:
        """Search Google Scholar for a title and return organic results."""
        return self._search_title_data(title, query=query).get("organic_results", [])

    def _search_title_data(self, title: str, *, query: str = "allintitle") -> dict:
        """Search Google Scholar for a title and return the full response."""
        if not title:
            return {}
        search_query = f"allintitle: {title}" if query == "allintitle" else title
        response = self.client.get(
            params={
                "engine": "google_scholar",
                "q": search_query,
                "hl": "en",
                "num": 20,
                "as_sdt": 0,
            }
        )
        return response.json()

    def _format_export(
        self,
        data: dict,
        paper: dict,
        title_or_doi: str,
        format: Literal["endnote", "bibtex"],
    ) -> str:
        """Format Cite metadata when Google blocks its signed export link."""

        metadata = self._parse_chicago_citation(data)
        if format == "bibtex":
            key = re.sub(r"\W", "", metadata["authors"][0].split(",")[0].casefold())
            key += metadata["year"]
            key += re.sub(r"\W", "", metadata["title"].split()[0].casefold())
            fields = [
                ("title", metadata["title"]),
                ("author", " and ".join(metadata["authors"])),
                ("journal", metadata["journal"]),
                ("volume", metadata["volume"]),
                ("number", metadata.get("issue")),
                ("pages", metadata["pages"].replace("-", "--")),
                ("year", metadata["year"]),
            ]
            body = ",\n".join(
                (f"  {name}={{{value}}}" for name, value in fields if value)
            )
            return f"@article{{{key},\n{body}\n}}"

        details = self._metadata.get_citation_details(paper, {"max_author_requests": 9})
        if details.get("authors"):
            metadata["authors"] = [
                self._to_last_first(author.strip())
                for author in details["authors"].split(",")
            ]
        for key in ("title", "journal", "volume", "issue", "pages", "publisher"):
            if details.get(key):
                metadata[key] = details[key]

        doi = re.search(DOI_PATTERN, title_or_doi, re.IGNORECASE)
        doi_metadata = self._get_doi_metadata(doi.group(0)) if doi else {}
        lines = [
            ("%0", "Journal Article"),
            ("%T", metadata["title"]),
            *(("%A", author) for author in metadata["authors"]),
            ("%J", metadata["journal"]),
            ("%V", metadata["volume"]),
            ("%N", metadata.get("issue")),
            ("%P", metadata["pages"]),
            ("%@", doi_metadata.get("SN")),
            ("%D", metadata["year"]),
            ("%I", metadata.get("publisher") or doi_metadata.get("PB")),
        ]
        return "\n".join((f"{name} {value}" for name, value in lines if value))

    @classmethod
    def _parse_chicago_citation(cls, data: dict) -> dict:
        """Parse SearchApi's structured Chicago citation into common fields."""
        snippet = next(
            (
                citation.get("snippet", "")
                for citation in data.get("citations", [])
                if citation.get("title") == "Chicago"
            ),
            "",
        )
        match = re.fullmatch(
            r'(?P<authors>.+?)\. ["“](?P<title>.+?)\.["”] '
            r"(?P<journal>.+?) (?P<volume>\d+)"
            r"(?:, no\. (?P<issue>[^ ]+))? \((?P<year>\d{4})\): "
            r"(?P<pages>[\d–-]+)\.",
            snippet,
        )
        if not match:
            raise RuntimeError("Could not parse SearchApi's Chicago citation export.")
        metadata = match.groupdict()
        author_parts = [part.strip() for part in metadata.pop("authors").split(",")]
        metadata["authors"] = [f"{author_parts[0]}, {author_parts[1]}"] + [
            cls._to_last_first(author.removeprefix("and "))
            for author in author_parts[2:]
        ]
        return metadata

    @staticmethod
    def _to_last_first(author: str) -> str:
        """Convert a Google Scholar author name to ``Last, First``."""
        names = author.split()
        return f"{names[-1]}, {' '.join(names[:-1])}" if len(names) > 1 else author

    def _get_doi_metadata(self, doi: str) -> dict:
        """Retrieve RIS metadata for fields omitted by Google Scholar Cite."""
        try:
            response = self.client.request(
                f"https://doi.org/{doi}",
                headers={"Accept": "application/x-research-info-systems"},
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return {}
        metadata = {}
        for line in response.text.splitlines():
            parts = line.split("  - ", 1)
            if len(parts) == 2:
                metadata[parts[0]] = parts[1]
        return metadata

    def _get_export(
        self,
        link: str,
        format: Literal["endnote", "bibtex"],
        referer: Optional[str] = None,
    ) -> str:
        """Fetch citation text from a Google Scholar export link."""

        @retry_with_exponential_backoff(
            retry_if=lambda response: response.status_code in {429, 500, 502, 503, 504},
            exceptions=(requests.exceptions.RequestException,),
        )
        def fetch_export() -> requests.Response:
            export = self.client.request(
                link,
                headers={
                    "Referer": referer or "https://scholar.google.com/",
                    "User-Agent": "Mozilla/5.0",
                },
            )
            return export

        # Google Scholar export links can transiently reject a fresh request.
        export = fetch_export()
        if export.ok:
            citation = export.text.strip()
            if not citation:
                raise RuntimeError(f"SearchApi returned an empty {format} export.")
            return citation
        export.raise_for_status()
        raise RuntimeError(f"Could not retrieve the {format} export.")

    def _get_citation_count_from_html(
        self, html_url: str, data_cids: set[str]
    ) -> Optional[int]:
        """Retrieve citation counts omitted from a SearchApi JSON response."""
        response = self.client.get(url=html_url)
        soup = BeautifulSoup(response.text, "html.parser")
        counts = set()
        for result in soup.select(".gs_r[data-cid]"):
            if result.get("data-cid") not in data_cids:
                continue
            cited_by = result.select_one('a[href*="cites="]')
            if cited_by is None:
                continue
            match = re.fullmatch(
                r"Cited by ([\d,]+)", cited_by.get_text(" ", strip=True)
            )
            if match:
                counts.add(int(match.group(1).replace(",", "")))

        if len(counts) > 1:
            raise RuntimeError("SearchApi HTML returned conflicting citation counts.")
        return counts.pop() if counts else None

    def _get_paper(self, title: str, original_input: str) -> dict:
        """Find an exact Scholar result after the caller resolves any DOI."""
        for query in ("allintitle", "plain"):
            paper = self._find_exact_paper(title, query)
            if paper is not None:
                return paper
        raise RuntimeError(
            f"SearchApi returned no exact Scholar match for {original_input!r}."
        )

    @retry_with_exponential_backoff(retry_if=lambda paper: paper is None)
    def _find_exact_paper(self, title: str, query: str) -> Optional[dict]:
        try:
            papers = self._search_title(title, query=query)
        except requests.exceptions.RequestException:
            return None
        normalized_title = self._metadata.normalize_title(title)
        return next(
            (
                paper
                for paper in papers
                if paper.get("data_cid")
                and self._metadata.normalize_title(paper.get("title", ""))
                == normalized_title
            ),
            None,
        )


class SearchAPIScholar:
    """Keyword and author searches composed with metadata and citation services."""

    def __init__(self, client: SearchAPIClient) -> None:
        self.client = client
        self._metadata = _ScholarMetadata(client)
        self.citations = SearchAPICitations(client)

    def get_papers(
        self,
        title: str,
        fields: Sequence[str] = (
            "title",
            "authors",
            "year",
            "abstract",
            "journal",
            "citations",
        ),
        search_api_kwargs: Optional[dict] = None,
    ) -> pd.DataFrame:
        """
        Retrieve Google Scholar paper metadata through SearchApi.

        Args:
            title: Google Scholar search query.
            fields: List of strings with fields to keep in output.
            search_api_kwargs: Supports ``top_k``, ``num_enrich`` and
                ``max_author_requests``.

        Returns:
            pd.DataFrame. One paper per row.
        """
        resolved_kwargs = self._metadata.resolve_options(search_api_kwargs)
        exact_title = title[1:-1] if re.fullmatch('"[^"]+"', title) else None

        @retry_with_exponential_backoff(
            retry_if=lambda papers: exact_title is not None and (not papers),
            exceptions=(requests.exceptions.RequestException,),
        )
        def search() -> list[dict]:
            response = self.client.get(
                params={
                    "engine": "google_scholar",
                    "q": f"allintitle: {exact_title}" if exact_title else title,
                    "hl": "en",
                    "num": 20 if exact_title else resolved_kwargs["top_k"],
                }
            )
            papers = response.json().get("organic_results", [])
            if exact_title:
                normalized_title = self._metadata.normalize_title(exact_title)
                papers = [
                    paper
                    for paper in papers
                    if self._metadata.normalize_title(paper.get("title", ""))
                    == normalized_title
                ]
            return papers

        papers = search()

        processed = []
        for index, paper in enumerate(papers[: resolved_kwargs["top_k"]]):
            # Search result snippets are not abstracts; only the citation view exposes one.
            citation = (
                self._metadata.get_citation_details(
                    paper, search_api_kwargs=resolved_kwargs
                )
                if index < resolved_kwargs["num_enrich"]
                else {}
            )
            entry = self._metadata.parse_paper(paper, citation)
            if "citations" in fields and entry["citations"] < 0:
                entry["citations"] = self.citations.get_citations_from_title(
                    paper["title"]
                )
            processed.append(
                {key: value for key, value in entry.items() if key in fields}
            )

        return pd.DataFrame(processed, columns=fields)

    def get_author_papers(
        self,
        author: str,
        max_results: int = 30,
        *,
        author_id: Optional[str] = None,
        full_info: bool = False,
    ) -> pd.DataFrame:
        """Return papers by a researcher from Google Scholar through SearchApi.

        An exact Google Scholar profile is preferred. If none exists, results from
        an ``author:\"name\"`` Scholar query are returned and may mix namesakes.
        The default limit is 30 papers; explicit integer limits are respected.
        ``full_info=True`` requires a profile and consumes one extra SearchApi
        request per paper.

        Args:
            author: Researcher name.
            max_results: Maximum papers to return. Defaults to 30.
            author_id: Optional Google Scholar author ID for exact identification.
            full_info: Add journal, date, volume, issue, pages, publisher, and
                description from each paper's citation detail.

        Returns:
            pd.DataFrame. One paper per row.
        """
        if not isinstance(author, str):
            raise TypeError(f"Pass str not {type(author)}")
        author = author.strip()
        if not author:
            raise ValueError("author must not be empty")
        if not isinstance(max_results, int) or isinstance(max_results, bool):
            raise TypeError(f"Pass int not {type(max_results)}")
        if max_results < 0:
            raise ValueError("max_results must be non-negative")
        if author_id is not None and (not isinstance(author_id, str) or not author_id):
            raise ValueError("author_id must be a non-empty string")
        if not isinstance(full_info, bool):
            raise TypeError(f"Pass bool not {type(full_info)}")

        fields = _AUTHOR_PAPER_FIELDS + (_AUTHOR_DETAIL_FIELDS if full_info else [])
        if max_results == 0:
            return pd.DataFrame(columns=fields)

        search = None
        if author_id is None:
            search_params = {
                "engine": "google_scholar",
                "q": f'author:"{author}"',
                "hl": "en",
                "num": _AUTHOR_PAGE_SIZE,
            }
            search = self.client.get_data(search_params)
            exact_profiles = [
                profile
                for profile in search.get("profiles", [])
                if self._metadata.normalize_match_text(profile.get("name", ""))
                == self._metadata.normalize_match_text(author)
                and profile.get("author_id")
            ]
            if len(exact_profiles) > 1:
                candidates = ", ".join(
                    (
                        f"{profile['author_id']} ({profile.get('affiliations', 'unknown')})"
                        for profile in exact_profiles
                    )
                )
                raise RuntimeError(
                    f"Multiple exact Google Scholar profiles found for {author!r}: "
                    f"{candidates}. Pass author_id to disambiguate."
                )
            author_id = exact_profiles[0]["author_id"] if exact_profiles else None

        if author_id is not None:
            profile_params = {
                "engine": "google_scholar_author",
                "author_id": author_id,
                "hl": "en",
            }
            profile = self.client.get_data(profile_params)
            if not profile.get("author"):
                raise RuntimeError(
                    f"SearchApi returned no author profile for {author_id!r}."
                )
            articles = self._get_pages(
                profile_params,
                "articles",
                "citation_id",
                max_results,
                first_page=profile,
            )
            return pd.DataFrame(
                [
                    self._parse_author_article(article, full_info=full_info)
                    for article in articles
                ],
                columns=fields,
            )

        if full_info:
            raise RuntimeError(
                f"full_info requires a Google Scholar profile for {author!r}."
            )
        logger.warning(
            "No exact Google Scholar profile found for %r; returning name-query results that may mix namesakes.",
            author,
        )
        papers = self._get_pages(
            search_params, "organic_results", "data_cid", max_results, first_page=search
        )

        processed = []
        for paper in papers:
            entry = self._metadata.parse_paper(paper, {})
            if entry["citations"] < 0:
                entry["citations"] = self.citations.get_citations_from_title(
                    paper["title"]
                )
            entry["publication"] = self._metadata.normalize_text(
                paper.get("publication", "")
            )
            processed.append({field: entry[field] for field in fields})
        return pd.DataFrame(processed, columns=fields)

    def _get_pages(
        self,
        params: dict,
        result_key: str,
        identity_key: str,
        limit: int,
        *,
        first_page: dict,
    ) -> list[dict]:
        """Collect deduplicated results from numeric SearchApi pages."""
        results = []
        seen = set()
        page = 1
        while len(results) < limit:
            data = (
                first_page
                if page == 1
                else self.client.get_data({**params, "page": page})
            )
            page_results = data.get(result_key, [])
            added = 0
            for result in page_results:
                if not result.get("title"):
                    continue
                identity = result.get(identity_key) or self._metadata.normalize_title(
                    result["title"]
                )
                if identity not in seen:
                    seen.add(identity)
                    results.append(result)
                    added += 1
                    if len(results) == limit:
                        return results
            if not page_results or not added:
                break
            if len(page_results) < _AUTHOR_PAGE_SIZE and not data.get(
                "pagination", {}
            ).get("next"):
                break
            page += 1
        return results

    def _parse_author_article(self, article: dict, *, full_info: bool) -> dict:
        """Parse a Google Scholar Author article and optionally enrich it."""
        publication = self._metadata.normalize_text(article.get("publication", ""))
        year = article.get("year") or self._metadata.parse_year(publication)
        cited_by = article.get("cited_by", {}).get("total")
        authors = self._metadata.normalize_text(article.get("authors", ""))
        citation = {}
        if full_info or cited_by is None:
            citation_id = article.get("citation_id")
            if not citation_id:
                raise RuntimeError(
                    f"SearchApi returned no citation ID for {article.get('title')!r}."
                )
            citation = self.client.get_data(
                {
                    "engine": "google_scholar_author",
                    "view_op": "view_citation",
                    "citation_id": citation_id,
                    "hl": "en",
                },
                required_key="citation",
            )["citation"]
            cited_by = citation.get("cited_by", {}).get("total", cited_by)
        entry = {
            "title": article.get("title", ""),
            "authors": [name.strip() for name in authors.split(",") if name.strip()],
            "publication": publication,
            "year": int(year) if year else -1,
            "citations": int(cited_by) if cited_by is not None else 0,
        }
        if not full_info:
            return entry

        parsed = self._metadata.parse_paper(article, citation)
        entry.update(
            {
                "title": parsed["title"],
                "authors": parsed["authors"],
                "year": parsed["year"],
                "citations": parsed["citations"]
                if parsed["citations"] >= 0
                else entry["citations"],
                "journal": parsed["journal"],
                "date": parsed["date"],
                "volume": citation.get("volume", ""),
                "issue": citation.get("issue", ""),
                "pages": citation.get("pages", ""),
                "publisher": citation.get("publisher", ""),
                "description": citation.get("description", ""),
            }
        )
        return entry


SEARCH_API_CACHE = SearchAPIClient.load_cache(SEARCH_API_CACHE_PATH)
