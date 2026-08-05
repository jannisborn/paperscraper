import logging

from paperscraper.citations import get_citations_by_doi, utils
from paperscraper.citations.utils import author_name_to_ssaid, check_overlap

logging.disable(logging.INFO)


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

    def test_semantic_scholar_403_disables_api_key(self, monkeypatch):
        class Response:
            def __init__(self, status_code):
                self.status_code = status_code

        original_headers = utils.HEADERS.copy()
        original_disabled = utils.semantic_scholar_key_disabled()
        utils.HEADERS.clear()
        utils.HEADERS["x-api-key"] = "bad-key"
        utils._SEMANTIC_SCHOLAR_KEY_DISABLED = False

        calls = []

        def mock_get(url, headers=None, **kwargs):
            calls.append(dict(headers or {}))
            return Response(403 if len(calls) == 1 else 200)

        monkeypatch.setattr(utils.requests, "get", mock_get)
        try:
            response = utils.semantic_scholar_requests_get("https://example.test")
            assert response.status_code == 200
            assert calls == [{"x-api-key": "bad-key"}, {}]
            assert utils.HEADERS == {}
            assert utils.semantic_scholar_key_disabled()
        finally:
            utils.HEADERS.clear()
            utils.HEADERS.update(original_headers)
            utils._SEMANTIC_SCHOLAR_KEY_DISABLED = original_disabled

    def test_name_overlap(self):
        assert check_overlap("John Smith", "J. Smith")
        assert check_overlap("J. Smith", "John Smith")
        assert check_overlap("John A. Smith", "J. Smith")
        assert check_overlap("John Smith", "John A. Smith")
        assert check_overlap("J A. Smith", "J. Smith")
        assert not check_overlap("Alice B. Cooper", "Bob A. Cooper")
        assert not check_overlap("Alice Cooper", "Bob A. Cooper")
        assert check_overlap("John Walter", "Walter John")
