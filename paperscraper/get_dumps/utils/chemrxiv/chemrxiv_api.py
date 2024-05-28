import logging
import os
import sys
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urljoin

import requests

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
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
        begin_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page_size: Optional[int] = None,
    ):
        """
        Initialize API class.

        Args:
            begin_date (Optional[str], optional): begin date expressed as YYYY-MM-DD.
                Defaults to None.
            end_date (Optional[str], optional): end date expressed as YYYY-MM-DD.
                Defaults to None.
            page_size (int, optional): The batch size used to fetch the records from chemrxiv.
        """

        self.page_size = page_size or 50

        # Begin Date and End Date of the search
        launch_date = launch_dates["chemrxiv"]
        launch_datetime = datetime.fromisoformat(launch_date)

        if begin_date:
            begin_datetime = datetime.fromisoformat(begin_date)
            if begin_datetime < launch_datetime:
                self.begin_date = launch_date
                logger.warning(
                    f"Begin date {begin_date} is before chemrxiv launch date. Will use {launch_date} instead."
                )
            else:
                self.begin_date = begin_date
        else:
            self.begin_date = launch_date
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

        if method.casefold() == "get":
            return requests.get(url, params=params, timeout=10)
        elif method.casefold() == "post":
            return requests.post(url, json=params, timeout=10)
        else:
            raise ConnectionError(f"Unknown method for query: {method}")

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
                    "searchDateFrom": self.begin_date,
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
