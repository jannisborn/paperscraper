import logging

from paperscraper.citations import get_citations_by_doi
from paperscraper.citations.utils import check_overlap

logging.disable(logging.INFO)


class TestCitations:
    def test_citations(self):
        num = get_citations_by_doi("10.1038/s42256-023-00639-z")
        assert isinstance(num, int) and num > 50

        # Try invalid DOI
        num = get_citations_by_doi("10.1035348/s42256-023-00639-z")
        assert isinstance(num, int) and num == 0

    def test_name_overlap(self):
        assert check_overlap("John Smith", "J. Smith")
        assert check_overlap("J. Smith", "John Smith")
        assert check_overlap("John A. Smith", "J. Smith")
        assert check_overlap("John Smith", "John A. Smith")
        assert check_overlap("J A. Smith", "J. Smith")
        assert not check_overlap("Alice B. Cooper", "Bob A. Cooper")
        assert not check_overlap("Alice Cooper", "Bob A. Cooper")
        assert check_overlap("John Walter", "Walter John")
