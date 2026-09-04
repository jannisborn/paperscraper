import json
import logging

import pytest

from paperscraper.citations import get_citations_by_doi, get_citations_from_title
from paperscraper.citations.citations import _resolve_citation_backend
from paperscraper.citations.utils import (
    SEARCH_API_CACHE,
    SEARCH_API_CACHE_PATH,
    SEARCH_API_KEY,
    SS_API_KEY,
    _load_search_api_cache,
    author_name_to_ssaid,
    check_overlap,
)
from paperscraper.pdf import load_api_keys
from paperscraper.tests.scholar import handle_scholar_exception

logging.disable(logging.INFO)

API_KEYS = load_api_keys("api_keys.txt")
PAPER_TITLE = "GT4SD: Generative Toolkit for Scientific Discovery"


class TestCitations:
    def test_citations(self):
        num = get_citations_by_doi("10.1038/s42256-023-00639-z")
        assert isinstance(num, int) and num > 50

        # Try invalid DOI
        num = get_citations_by_doi("10.1035348/s42256-023-00639-z")
        assert isinstance(num, int) and num == 0

    def test_author_name_to_ssid(self):
        ssaid, name = author_name_to_ssaid("Fabian H Sinz")
        assert ssaid == "50095217"
        assert name == "Fabian H Sinz"

    @handle_scholar_exception
    def test_citations_from_title_scholarly(self):
        num = get_citations_from_title(PAPER_TITLE, backend="scholarly")
        assert isinstance(num, int) and num > 0

    def test_citations_from_title_semantic_scholar(self):
        num = get_citations_from_title(
            PAPER_TITLE,
            backend="semantic_scholar",
            api_key=API_KEYS["SS_API_KEY"],
        )
        assert isinstance(num, int) and num > 0

    def test_citations_from_title_searchapi(self):
        num = get_citations_from_title(
            PAPER_TITLE,
            backend="searchapi",
            api_key=API_KEYS["SEARCH_API_KEY"],
        )
        assert isinstance(num, int) and num > 0
        assert SEARCH_API_CACHE["citations"][PAPER_TITLE] == num

        # Repeated and auto calls use the validated citation cache.
        assert get_citations_from_title(PAPER_TITLE, backend="searchapi") == num
        if SEARCH_API_KEY:
            assert get_citations_from_title(PAPER_TITLE) == num

        if SEARCH_API_CACHE_PATH:
            with open(SEARCH_API_CACHE_PATH) as cache_file:
                persisted_cache = json.load(cache_file)
            assert persisted_cache["citations"][PAPER_TITLE] == num

    def test_searchapi_loads_cache(self, tmp_path):
        cache_path = tmp_path / "searchapi-cache.json"
        cache_path.write_text(json.dumps({"citations": {PAPER_TITLE: 9}, "other": {}}))

        assert _load_search_api_cache(str(cache_path)) == {
            "citations": {PAPER_TITLE: 9},
            "other": {},
        }

    def test_citation_backend_resolution(self):
        expected_backend = "scholarly"
        if SS_API_KEY:
            expected_backend = "semantic_scholar"
        if SEARCH_API_KEY:
            expected_backend = "searchapi"
        assert _resolve_citation_backend("auto", None) == expected_backend

        with pytest.raises(ValueError, match="cannot be used"):
            get_citations_from_title(PAPER_TITLE, api_key=API_KEYS["SEARCH_API_KEY"])
        with pytest.raises(ValueError, match="Unknown backend"):
            get_citations_from_title(PAPER_TITLE, backend="invalid")
        with pytest.raises(ValueError, match="not supported"):
            get_citations_from_title(
                PAPER_TITLE,
                backend="scholarly",
                api_key=API_KEYS["SEARCH_API_KEY"],
            )

    def test_name_overlap(self):
        assert check_overlap("John Smith", "J. Smith")
        assert check_overlap("J. Smith", "John Smith")
        assert check_overlap("John A. Smith", "J. Smith")
        assert check_overlap("John Smith", "John A. Smith")
        assert check_overlap("J A. Smith", "J. Smith")
        assert not check_overlap("Alice B. Cooper", "Bob A. Cooper")
        assert not check_overlap("Alice Cooper", "Bob A. Cooper")
        assert check_overlap("John Walter", "Walter John")
