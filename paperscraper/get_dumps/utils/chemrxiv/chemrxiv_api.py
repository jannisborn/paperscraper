import logging
import os
import sys
from datetime import datetime
from time import sleep
from typing import Dict, Optional
from urllib.parse import urljoin

import requests
from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    ContentDecodingError,
    JSONDecodeError,
    ReadTimeout,
)
from urllib3.exceptions import DecodeError

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

now_datetime = datetime.now()
launch_dates = {"chemrxiv": "2017-01-01"}


class ChemrxivAPI:
    """Handle OpenEngage API requests, using access.
    Adapted from https://github.com/fxcoudert/tools/blob/master/chemRxiv/chemRxiv.py.
    """

    base_primary = "https://chemrxiv.org/engage/chemrxiv/public-api/v1/"
    base_cambridge = "https://www.cambridge.org/engage/coe/public-api/v1/"
    cambridge_origin = "CHEMRXIV"

    def __init__(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page_size: Optional[int] = None,
        max_retries: int = 10,
    ):
        """
        Initialize API class.

        Args:
            start_date (Optional[str], optional): begin date expressed as YYYY-MM-DD.
                Defaults to None.
            end_date (Optional[str], optional): end date expressed as YYYY-MM-DD.
                Defaults to None.
            page_size (int, optional): The batch size used to fetch the records from chemrxiv.
            max_retries (int): Number of retries in case of error
        """

        self.page_size = page_size or 50
        self.max_retries = max_retries
        self._origin_filter = None
        self._set_base(self.base_primary)

        # Begin Date and End Date of the search
        launch_date = launch_dates["chemrxiv"]
        launch_datetime = datetime.fromisoformat(launch_date)

        if start_date:
            start_datetime = datetime.fromisoformat(start_date)
            if start_datetime < launch_datetime:
                self.start_date = launch_date
                logger.warning(
                    f"Begin date {start_date} is before chemrxiv launch date. Will use {launch_date} instead."
                )
            else:
                self.start_date = start_date
        else:
            self.start_date = launch_date
        if end_date:
            end_datetime = datetime.fromisoformat(end_date)
            if end_datetime > now_datetime:
                logger.warning(
                    f"End date {end_date} is in the future. Will use {now_datetime} instead."
                )
                self.end_date = now_datetime.strftime("%Y-%m-%d")
            else:
                self.end_date = end_date
        else:
            self.end_date = now_datetime.strftime("%Y-%m-%d")

    def request(self, url, method, params=None, parse_json: bool = False):
        """Send an API request to open Engage."""

        headers = {
            "Accept-Encoding": "identity",
            "Accept": "application/json",
            "User-Agent": "paperscraper",
        }
        retryable = (
            ChunkedEncodingError,
            ContentDecodingError,
            DecodeError,
            ReadTimeout,
            ConnectionError,
        )
        transient_status = {429, 500, 502, 503, 504}
        backoff = 0.1

        for attempt in range(self.max_retries):
            try:
                if method.casefold() == "get":
                    response = requests.get(
                        url, params=params, headers=headers, timeout=(5, 30)
                    )
                elif method.casefold() == "post":
                    response = requests.post(
                        url, json=params, headers=headers, timeout=(5, 30)
                    )
                else:
                    raise ConnectionError(f"Unknown method for query: {method}")
                if response.status_code in transient_status:
                    logger.warning(
                        f"{response.status_code} for {url} (attempt {attempt + 1}/{self.max_retries}); retrying in {backoff:.1f}s"
                    )
                    if attempt + 1 == self.max_retries:
                        response.raise_for_status()
                    sleep(backoff)
                    backoff = min(60.0, backoff * 2)
                    continue
                elif 400 <= response.status_code < 500:
                    response.raise_for_status()
                if not parse_json:
                    return response

                try:
                    return response.json()
                except JSONDecodeError:
                    logger.warning(
                        f"JSONDecodeError for {response.url} "
                        f"(attempt {attempt + 1}/{self.max_retries}); retrying in {backoff:.1f}s"
                    )
                    if attempt + 1 == self.max_retries:
                        raise
                    sleep(backoff)
                    backoff = min(60.0, backoff * 2)
                    continue

            except retryable as e:
                logger.warning(
                    f"{e.__class__.__name__} for {url} (attempt {attempt + 1}/{self.max_retries}); "
                    f"retrying in {backoff:.1f}s"
                )
                if attempt + 1 == self.max_retries:
                    raise
                sleep(backoff)
                backoff = min(60.0, backoff * 2)

    def query(self, query, method="get", params=None):
        """Perform a direct query."""

        return self.request(
            urljoin(self.base, query), method, params=params, parse_json=True
        )

    def query_generator(
        self, query, method: str = "get", params: Optional[Dict] = None
    ):
        """Query for a list of items, with paging. Returns a generator."""

        start_datetime = datetime.fromisoformat(self.start_date)
        end_datetime = datetime.fromisoformat(self.end_date)

        def year_windows():
            year = start_datetime.year
            while year <= end_datetime.year:
                year_start = datetime(year, 1, 1)
                year_end = datetime(year, 12, 31)
                win_start = max(start_datetime, year_start)
                win_end = min(end_datetime, year_end)
                yield win_start.strftime("%Y-%m-%d"), win_end.strftime("%Y-%m-%d")
                year += 1

        params = (params or {}).copy()

        for year_from, year_to in year_windows():
            logger.info(f"Starting to scrape data from {year_from} to {year_to}")
            page = 0
            while True:
                params.update(
                    {
                        "limit": self.page_size,
                        "skip": page * self.page_size,
                        "searchDateFrom": year_from,
                        "searchDateTo": year_to,
                    }
                )
                try:
                    data = self.request(
                        urljoin(self.base, query),
                        method,
                        params=params,
                        parse_json=True,
                    )
                except requests.HTTPError as e:
                    status = getattr(e.response, "status_code", None)
                    if status == 403 and query == "items":
                        if self._switch_to_cambridge():
                            logger.warning(
                                "ChemRxiv API returned 403 (likely Cloudflare); "
                                "retrying via Cambridge Open Engage API."
                            )
                            continue
                        raise
                    logger.warning(
                        f"Stopping year window {year_from}..{year_to} at skip={page * self.page_size} "
                        f"due to HTTPError {status}"
                    )
                    break
                items = data.get("itemHits", [])
                if not items:
                    break
                for item in items:
                    if (
                        self._origin_filter
                        and item.get("item", {}).get("origin") != self._origin_filter
                    ):
                        continue
                    yield item
                page += 1

    def all_preprints(self):
        """Return a generator to all the chemRxiv articles."""
        return self.query_generator("items")

    def preprint(self, article_id):
        """Information on a given preprint.
        .. seealso:: https://docs.figshare.com/#public_article
        """
        return self.query(os.path.join("items", article_id))

    def number_of_preprints(self):
        return self.query("items")["totalCount"]

    def _set_base(self, base_url: str) -> None:
        """Configure base URL and origin filter."""
        self.base = base_url
        self._origin_filter = (
            self.cambridge_origin
            if base_url == self.base_cambridge
            else None
        )

    def _switch_to_cambridge(self) -> bool:
        """Switch the API base to the Cambridge Open Engage endpoint."""
        if self.base == self.base_cambridge:
            return False
        self._set_base(self.base_cambridge)
        return True
