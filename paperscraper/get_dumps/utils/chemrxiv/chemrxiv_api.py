import os
from typing import Optional

import requests


class ChemrxivAPI:
    """Handle figshare API requests, using access token.
    Adapted from https://github.com/fxcoudert/tools/blob/master/chemRxiv/chemRxiv.py.
    """

    base = 'https://api.figshare.com/v2'

    def __init__(self, token=None, page_size: Optional[int] = None):

        if token is None:
            token_path = os.path.join(
                os.path.expanduser('~'), '.config', 'figshare', 'chemrxiv.txt'
            )
            if not os.path.exists(token_path):
                raise ValueError('No access token found.')
            with open(token_path, 'r') as file:
                token = file.read().strip()

        self.page_size = page_size or 500
        #: corresponds to chemrxiv
        self.institution = 259
        self.token = token
        self.headers = {'Authorization': f'token {self.token}'}

        r = requests.get(os.path.join(f'{self.base}', 'account'), headers=self.headers)
        r.raise_for_status()

    def request(self, url, *, params=None):
        """Send a figshare API request."""
        return requests.get(url, headers=self.headers, params=params)

    def query(self, query, *, params=None):
        """Perform a direct query."""
        r = self.request(
            os.path.join(f'{self.base}', f'{query.lstrip("/")}'), params=params
        )
        r.raise_for_status()
        return r.json()

    def query_generator(self, query, params=None):
        """Query for a list of items, with paging. Returns a generator."""
        if params is None:
            params = {}

        page = 1
        while True:
            params.update({'page_size': self.page_size, 'page': page})
            r = self.request(os.path.join(f'{self.base}', '{query}'), params=params)
            if r.status_code == 400:
                raise ValueError(r.json()['message'])
            r.raise_for_status()
            r = r.json()

            # Special case if a single item, not a list, was returned
            if not isinstance(r, list):
                yield r
                return

            # If we have no more results, bail out
            if len(r) == 0:
                return

            yield from r
            page += 1

    def all_preprints(self):
        """Return a generator to all the chemRxiv articles_short.
        .. seealso:: https://docs.figshare.com/#articles_list
        """
        return self.query_generator(
            'articles', params={'institution': self.institution}
        )

    def preprint(self, article_id):
        """Information on a given preprint.
        .. seealso:: https://docs.figshare.com/#public_article
        """
        return self.query(os.path.join('articles', f'{article_id}'))
