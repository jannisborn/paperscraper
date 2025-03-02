import logging
import os
import sys
from datetime import datetime
from time import time
from typing import Dict, Optional
from urllib.parse import urljoin

import requests
from requests.exceptions import ChunkedEncodingError

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

now_datetime = datetime.now()
launch_dates = {"chemrxiv": "2017-01-01"}


class ChemrxivAPI:
    """Handle OpenEngage API requests, using access.
    Adapted from https://github.com/fxcoudert/tools/blob/master/chemRxiv/chemRxiv.py.
    """

    base = "https://chemrxiv.org/engage/chemrxiv/public-api/v1/"

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

    def request(self, url, method, params=None):
        """Send an API request to open Engage."""

        for attempt in range(self.max_retries):
            try:
                if method.casefold() == "get":
                    return requests.get(url, params=params, timeout=10)
                elif method.casefold() == "post":
                    return requests.post(url, json=params, timeout=10)
                else:
                    raise ConnectionError(f"Unknown method for query: {method}")
            except ChunkedEncodingError as e:
                logger.warning(f"ChunkedEncodingError occurred for {url}: {e}")
                if attempt + 1 == self.max_retries:
                    raise e
                time.sleep(3)

    def query(self, query, method="get", params=None):
        """Perform a direct query."""

        r = self.request(urljoin(self.base, query), method, params=params)
        r.raise_for_status()
        return r.json()

    def query_generator(self, query, method: str = "get", params: Dict = {}):
        """Query for a list of items, with paging. Returns a generator."""

        page = 0
        while True:
            params.update(
                {
                    "limit": self.page_size,
                    "skip": page * self.page_size,
                    "searchDateFrom": self.start_date,
                    "searchDateTo": self.end_date,
                }
            )
            r = self.request(urljoin(self.base, query), method, params=params)
            if r.status_code == 400:
                raise ValueError(r.json()["message"])
            r.raise_for_status()
            r = r.json()
            r = r["itemHits"]

            # If we have no more results, bail out
            if len(r) == 0:
                return

            yield from r
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
