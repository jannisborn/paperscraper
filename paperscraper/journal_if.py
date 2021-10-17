"""
Class to fetch the impact factor of all citefactor-indexed journals.
Limitation: Fetches the 2014 IFs.

Adapted from: https://github.com/andrew-hill/impactor/blob/master/impactor.py
Available via MIT License.

Adaptions:
- Converting code from Python2 to Python3.
- Fetching IFs from *all* journals not just from journals starting with "A".

"""

import logging
import pickle
import re
import string
from urllib.request import urlopen

# http://www.crummy.com/software/BeautifulSoup/
from bs4 import BeautifulSoup


class Impactor(object):
    """
    Class to fetch the impact factor of all citefactor-indexed journals as of 2014.
    """

    BASE_URL_PREFIX = r"http://www.citefactor.org/journal-impact-factor-list-"
    BASE_URL_SUFFIX = r".html"
    URL_REGEX_PREFIX = r"http://www\.citefactor\.org/journal-impact-factor-list-"
    URL_REGEX_SUFFIX = r"_?[A-Z]?\.html"

    def __init__(self, journal_db_file=None, year=2014):
        logging.debug("journal_db_file={}, year={}".format(journal_db_file, year))

        self.journal_data = None
        self.journal_db_file = journal_db_file
        self.matches = set()
        self.year = year

        assert year in (2014,), "Can only handle 2014 at the moment."
        self.base_url = self.BASE_URL_PREFIX + str(year) + self.BASE_URL_SUFFIX
        self.url_regex = self.URL_REGEX_PREFIX + str(year) + self.URL_REGEX_SUFFIX
        self.re = re.compile(self.url_regex)
        self.load()
        self.save()
        self.create_if_dict()

    def match(self, search_terms):
        # If no terms specified, show all entries
        if search_terms is None or len(search_terms) == 0:
            for j in self.journal_data.values():
                self.matches.add(j["ISSN"])
        # Otherwise do search
        issn_re = re.compile(r"\d{4}-\d{4}")
        for s in search_terms:
            if issn_re.match(s):
                self.matches.add(s)
            else:
                for j in self.journal_data.values():
                    if j["JOURNAL"].lower().find(s.lower()) >= 0:
                        self.matches.add(j["ISSN"])

    def load(self):
        # Try to load from file
        if self.journal_db_file is not None:
            try:
                with open(self.journal_db_file, "rb") as f:
                    self.journal_data = pickle.load(f)
                    logging.debug(
                        "loaded journals from {}".format(self.journal_db_file)
                    )
            except Exception:
                pass
        # If cannot load from file, load from URL
        if self.journal_data is None:
            logging.info("Fetching database from citefactor.org...")
            self.journal_data = self.get_all_journal_data()

    def save(self):
        if self.journal_db_file is not None:
            try:
                with open(self.journal_db_file, "wb") as f:
                    pickle.dump(self.journal_data, f, -1)
                    logging.debug("saved journals to {}".format(self.journal_db_file))
            except Exception:
                pass

    def get_all_urls(self):
        main_page_content = urlopen(self.base_url).read()
        soup = BeautifulSoup(main_page_content)
        soup.prettify()  # necessary?
        return [
            self.base_url,
        ] + [anchor["href"] for anchor in soup.find_all("a", href=self.re)]

    def get_journal_table(self, url):
        content = urlopen(url).read()
        soup = BeautifulSoup(content)
        soup.prettify()  # necessary?
        t = soup.table
        caption_re = re.compile(
            r"^Impact Factor " + str(self.year)
        )  # works for Year==2015 only
        while t is not None:
            if (
                t.caption is None
                or t.caption.string is None
                or caption_re.match(t.caption.string) is None
            ):
                t = t.find_next()
                continue
            return t

    def get_table_headers(self, table):
        return [str(x.string) for x in table.tr.find_all("td")]

    def get_journal_data(self, table):
        headers = self.get_table_headers(table)
        journals = dict()
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            j = dict(zip(headers, [str(x.string) for x in cells]))
            # logging.debug('importing: {}'.format(j))
            journals[j["ISSN"]] = j
        return journals

    def get_all_journal_data(self):
        journals = dict()
        for url in self.get_all_urls():

            for page in string.ascii_uppercase:
                page = "0-A" if page == "A" else page
                url_page = url.split("2014")[0] + "2014_" + page + url.split("2014")[1]
                table = self.get_journal_table(url_page)
                journals.update(self.get_journal_data(table))
        logging.info(
            "imported {} journal entries from citefactor.org".format(len(journals))
        )
        return journals

    def create_if_dict(self):
        """
        Creates a dictionary with journal names as key (lowercase) and impact factors
        as values.
        """

        stringparse = (
            lambda x: str(x).strip().lower().replace("\\", "_").replace(" ", "_")
        )
        self.journal_to_if = dict(
            (stringparse(value["JOURNAL"]), value["2013/2014"])
            for key, value in self.journal_data.items()
        )
