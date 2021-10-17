import os
from typing import Optional, Dict

import requests


class ChemrxivAPI:
    """Handle OpenEngage API requests, using access.
    Adapted from https://github.com/fxcoudert/tools/blob/master/chemRxiv/chemRxiv.py.
    """

    base = "https://chemrxiv.org/engage/chemrxiv/public-api/v1"

    def __init__(self, page_size: Optional[int] = None):

        self.page_size = page_size or 50

    def request(self, url, method, params=None):
        """Send an API request to open Engage."""

        if method.casefold() == "get":
            return requests.get(url, params=params)
        elif method.casefold() == "post":
            return requests.post(url, json=params)
        else:
            raise ConnectionError(f"Unknown method for query: {method}")

    def query(self, query, method="get", params=None):
        """Perform a direct query."""
        r = self.request(
            os.path.join(f"{self.base}", f"{query}"), method, params=params
        )
        r.raise_for_status()
        return r.json()

    def query_generator(self, query, method: str = "get", params: Dict = {}):
        """Query for a list of items, with paging. Returns a generator."""

        page = 0
        while True:
            params.update({"limit": self.page_size, "skip": page * self.page_size})
            r = self.request(os.path.join(self.base, query), method, params=params)
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
