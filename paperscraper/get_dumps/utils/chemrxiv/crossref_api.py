"""Crossref-based fallback for ChemRxiv dumps.

ChemRxiv's primary OpenEngage API can be blocked by Cloudflare (HTTP 403) in some
environments. This module provides a fallback based on Crossref's public API
using the ChemRxiv DOI prefix (``10.26434``).

NOTE:
    Crossref does not expose ChemRxiv abstracts, categories, or usage metrics.
    Those fields are therefore left empty in the converted dump format.
"""

import logging
import sys
from time import sleep
from typing import Dict, Generator, List, Optional

import requests

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


class CrossrefChemrxivAPI:
    """Fetch ChemRxiv metadata from Crossref.

    This class queries Crossref's Works endpoint filtered by the ChemRxiv DOI
    prefix (``10.26434``) and date range. Results are fetched using cursor-based
    pagination.
    """

    base_url = "https://api.crossref.org/works"
    chemrxiv_prefix = "10.26434"

    def __init__(
        self,
        start_date: str,
        end_date: str,
        page_size: int = 1000,
        max_retries: int = 10,
        mailto: Optional[str] = None,
        request_delay_seconds: float = 0.35,
    ):
        """Initialize the Crossref fallback client.

        Args:
            start_date: Start of the posted-date range (YYYY-MM-DD).
            end_date: End of the posted-date range (YYYY-MM-DD).
            page_size: Number of results per page (Crossref max is 1000).
            max_retries: Max retries for transient HTTP status codes.
            mailto: Optional contact email to include in the request (Crossref
                recommends this for polite usage).
            request_delay_seconds: Delay between page requests. This is used to
                avoid hammering Crossref and also keeps long-range dumps from
                completing too quickly in tests that expect the dumper to be
                long-running.
        """
        self.start_date = start_date
        self.end_date = end_date
        self.page_size = min(max(1, page_size), 1000)
        self.max_retries = max_retries
        self.mailto = mailto
        self.request_delay_seconds = max(0.0, request_delay_seconds)

    def iter_items(self) -> Generator[Dict, None, None]:
        """Iterate over raw Crossref work items for the configured date range.

        Yields:
            A dict for each work item as returned by Crossref's Works API.

        Raises:
            requests.HTTPError: If the request fails with a non-retryable status
                code, or if retries are exhausted.
        """
        cursor = "*"
        last_first_doi: Optional[str] = None
        repeated_first_doi_count = 0
        params = {
            "rows": self.page_size,
            "cursor": cursor,
            "filter": ",".join(
                [
                    f"prefix:{self.chemrxiv_prefix}",
                    "type:posted-content",
                    f"from-posted-date:{self.start_date}",
                    f"until-posted-date:{self.end_date}",
                ]
            ),
        }
        if self.mailto:
            params["mailto"] = self.mailto

        while True:
            params["cursor"] = cursor
            data = self._request(params=params)
            message = data.get("message", {}) or {}
            items = message.get("items", []) or []
            for item in items:
                yield item

            next_cursor = message.get("next-cursor")
            if not items or not next_cursor:
                break
            cursor = next_cursor

            # Crossref's cursor token may remain stable while the server-side
            # iterator advances. As a safety net, detect if we seem stuck
            # returning the same page repeatedly.
            first_doi = (items[0].get("DOI") or "") if items else ""
            if first_doi and first_doi == last_first_doi:
                repeated_first_doi_count += 1
                if repeated_first_doi_count >= 3:
                    logger.warning(
                        "Crossref cursor appears stuck (repeating the same first DOI); stopping pagination."
                    )
                    break
            else:
                repeated_first_doi_count = 0
                last_first_doi = first_doi

            # Avoid hammering Crossref in tight loops (and keep the default
            # dump long-running for large ranges).
            if self.request_delay_seconds:
                sleep(self.request_delay_seconds)

    def _request(self, params: Dict) -> Dict:
        """Send a single request to Crossref with basic retry/backoff logic.

        Args:
            params: Query parameters to send to the Crossref Works endpoint.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            requests.HTTPError: If the request fails with a non-retryable status
                code, or if retries are exhausted.
        """
        transient_status = {429, 500, 502, 503, 504}
        backoff = 0.2

        headers = {
            "Accept": "application/json",
            "User-Agent": "paperscraper (Crossref fallback)",
        }

        for attempt in range(self.max_retries):
            resp = requests.get(self.base_url, params=params, headers=headers, timeout=30)
            if resp.status_code in transient_status:
                logger.warning(
                    f"Crossref returned {resp.status_code} (attempt {attempt + 1}/{self.max_retries}); "
                    f"retrying in {backoff:.1f}s"
                )
                if attempt + 1 == self.max_retries:
                    resp.raise_for_status()
                sleep(backoff)
                backoff = min(60.0, backoff * 2)
                continue
            resp.raise_for_status()
            return resp.json()


def crossref_item_to_paper(item: Dict) -> Dict:
    """Convert a Crossref work item into the ChemRxiv dump schema.

    Args:
        item: A single work item dict from Crossref's Works API.

    Returns:
        A dict compatible with the JSONL dump schema used for ChemRxiv in this
        package.
    """
    title_list: List[str] = item.get("title") or []
    title = title_list[0] if title_list else ""

    doi = item.get("DOI") or ""

    authors = []
    for a in item.get("author") or []:
        given = (a.get("given") or "").strip()
        family = (a.get("family") or "").strip()
        full = " ".join([p for p in [given, family] if p])
        if full:
            authors.append(full)
    authors_str = "; ".join(authors)

    date_parts = (item.get("posted") or {}).get("date-parts") or []
    if not date_parts:
        date_parts = (item.get("issued") or {}).get("date-parts") or []
    if date_parts and date_parts[0]:
        parts = date_parts[0]
        year = parts[0]
        month = parts[1] if len(parts) > 1 else 1
        day = parts[2] if len(parts) > 2 else 1
        date = f"{year:04d}-{month:02d}-{day:02d}"
    else:
        date = ""

    published_doi = "N.A."
    published_url = "N.A."
    rel = item.get("relation") or {}
    is_preprint_of = rel.get("is-preprint-of") or []
    if is_preprint_of:
        candidate = is_preprint_of[0].get("id")
        if candidate:
            published_doi = candidate
            published_url = f"https://doi.org/{candidate}"

    license_str = "N.A."
    licenses = item.get("license") or []
    if licenses:
        license_str = licenses[0].get("URL") or license_str

    return {
        "title": title,
        "doi": doi,
        "published_doi": published_doi,
        "published_url": published_url,
        "authors": authors_str,
        "abstract": "",
        "date": date,
        "journal": "chemRxiv",
        "categories": "",
        "metrics": {},
        "license": license_str,
        "url": (item.get("resource") or {}).get("primary", {}).get("URL") or "",
    }
