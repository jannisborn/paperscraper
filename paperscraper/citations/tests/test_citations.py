import logging

from paperscraper.citations import get_citations_by_doi

logging.disable(logging.INFO)


class TestCitations:
    def test_citations(self):
        num = get_citations_by_doi("10.1038/s42256-023-00639-z")
        assert isinstance(num, int) and num > 50

        # Try invalid DOI
        num = get_citations_by_doi("10.1035348/s42256-023-00639-z")
        assert isinstance(num, int) and num == 0


num = get_citations_by_doi("10.1035348/s42256-023-00639-z")
assert isinstance(num, int) and num == 0
