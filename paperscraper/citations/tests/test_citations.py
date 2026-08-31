import json
import logging
import os

import pytest
from dotenv import dotenv_values
from scholarly._proxy_generator import MaxTriesExceededException

from paperscraper.citations import get_citations_by_doi, get_citations_from_title, utils
from paperscraper.citations.citations import (
    _get_citations_from_title_searchapi,
    _resolve_citation_backend,
    get_citation_count_from_searchapi_author,
)
from paperscraper.citations.utils import author_name_to_ssaid, check_overlap

logging.disable(logging.INFO)

API_KEYS = dotenv_values("api_keys.txt")
PAPER_TITLE = "GT4SD: Generative Toolkit for Scientific Discovery"


@pytest.fixture(autouse=True)
def clear_searchapi_cache(monkeypatch):
    monkeypatch.setattr(utils, "SEARCH_API_CACHE", {"citations": {}})
    monkeypatch.setattr(utils, "SEARCH_API_CACHE_PATH", None)


class SearchApiResponse:
    def __init__(self, data=None, text=""):
        self.data = data
        self.text = text

    def json(self):
        return self.data


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

    def test_citations_from_title_scholarly_auto(self, monkeypatch):
        monkeypatch.setattr(utils, "SEARCH_API_KEY", None)
        monkeypatch.setattr(utils, "SS_API_KEY", None)
        try:
            num = get_citations_from_title(PAPER_TITLE)
        except MaxTriesExceededException as exc:
            pytest.skip(f"Google Scholar unavailable: {exc}")
        assert isinstance(num, int) and num > 0

    def test_citations_from_title_semantic_scholar(self, monkeypatch):
        api_key = os.getenv("SS_API_KEY") or API_KEYS.get("SS_API_KEY")
        if api_key:
            monkeypatch.setattr(utils, "SS_API_KEY", "invalid-key")
            monkeypatch.setattr(utils, "HEADERS", {"x-api-key": "invalid-key"})
        num = get_citations_from_title(
            PAPER_TITLE, backend="semantic_scholar", api_key=api_key
        )
        assert isinstance(num, int) and num > 0

    def test_citations_from_title_searchapi(self, monkeypatch):
        api_key = os.getenv("SEARCH_API_KEY") or API_KEYS.get("SEARCH_API_KEY")
        if not api_key:
            pytest.skip("SEARCH_API_KEY is not configured")
        monkeypatch.setattr(utils, "SEARCH_API_KEY", "invalid-key")
        num = get_citations_from_title(
            PAPER_TITLE, backend="searchapi", api_key=api_key
        )
        assert isinstance(num, int) and num > 0

    def test_searchapi_uses_exact_match_and_persists_cache(self, monkeypatch, tmp_path):
        calls = []
        cache_path = tmp_path / "searchapi-cache.json"
        monkeypatch.setattr(utils, "SEARCH_API_CACHE_PATH", str(cache_path))
        data = {
            "search_metadata": {"id": "search-correct"},
            "organic_results": [
                {
                    "title": PAPER_TITLE,
                    "inline_links": {"cited_by": {"total": 9}},
                }
            ],
        }

        def mock_get(**kwargs):
            calls.append(kwargs)
            return SearchApiResponse(data)

        monkeypatch.setattr(utils, "search_api_requests_get", mock_get)

        assert _get_citations_from_title_searchapi(PAPER_TITLE, "key") == 9
        assert _get_citations_from_title_searchapi(PAPER_TITLE, "key") == 9
        assert len(calls) == 1
        assert json.loads(cache_path.read_text()) == {"citations": {PAPER_TITLE: 9}}

    def test_searchapi_loads_cache(self, tmp_path):
        cache_path = tmp_path / "searchapi-cache.json"
        cache_path.write_text(json.dumps({"citations": {PAPER_TITLE: 9}, "other": {}}))

        assert utils._load_search_api_cache(str(cache_path)) == {
            "citations": {PAPER_TITLE: 9},
            "other": {},
        }

    def test_searchapi_recovers_count_from_html(self, monkeypatch):
        responses = iter(
            [
                SearchApiResponse(
                    {
                        "search_metadata": {
                            "id": "search-html",
                            "html_url": "https://example.test/search.html",
                        },
                        "organic_results": [
                            {"title": PAPER_TITLE, "data_cid": "paper-id"}
                        ],
                    }
                ),
                SearchApiResponse(
                    text="""
                    <div class="gs_r" data-cid="paper-id">
                      <a href="/scholar?cites=paper">Cited by 9</a>
                    </div>
                    """
                ),
            ]
        )
        calls = []

        def mock_get(**kwargs):
            calls.append(kwargs)
            return next(responses)

        monkeypatch.setattr(utils, "search_api_requests_get", mock_get)

        assert _get_citations_from_title_searchapi(PAPER_TITLE, "key") == 9
        assert calls[1]["url"] == "https://example.test/search.html"

    def test_searchapi_retries_missing_exact_match(self, monkeypatch):
        responses = iter(
            [
                SearchApiResponse(
                    {
                        "search_metadata": {"id": "search-unrelated"},
                        "organic_results": [{"title": "An unrelated paper"}],
                    }
                ),
                SearchApiResponse(
                    {
                        "search_metadata": {"id": "search-correct"},
                        "organic_results": [
                            {
                                "title": PAPER_TITLE,
                                "inline_links": {"cited_by": {"total": 9}},
                            }
                        ],
                    }
                ),
            ]
        )
        monkeypatch.setattr(
            utils, "search_api_requests_get", lambda **kwargs: next(responses)
        )

        assert _get_citations_from_title_searchapi(PAPER_TITLE, "key") == 9

    def test_searchapi_uses_author_fallback(self, monkeypatch):
        unrelated = SearchApiResponse(
            {
                "search_metadata": {"id": "search-unrelated"},
                "organic_results": [{"title": "An unrelated paper"}],
            }
        )
        responses = iter(
            [
                unrelated,
                unrelated,
                unrelated,
                SearchApiResponse(
                    {
                        "organic_results": [
                            {
                                "title": f"{PAPER_TITLE}, Journal 1 (2022)",
                                "type": "CITATION",
                                "authors": [{"name": "M Manica"}],
                            }
                        ],
                    }
                ),
                SearchApiResponse(
                    {"profiles": [{"author_id": "author-id", "name": "Matteo Manica"}]}
                ),
                SearchApiResponse(
                    {"articles": [{"title": PAPER_TITLE, "citation_id": "citation-id"}]}
                ),
                SearchApiResponse(
                    {
                        "citation": {
                            "scholar_articles": {
                                "title": PAPER_TITLE,
                                "cited_by": {"total": 9},
                            }
                        }
                    }
                ),
            ]
        )
        calls = []

        def mock_get(**kwargs):
            calls.append(kwargs["params"])
            return next(responses)

        monkeypatch.setattr(utils, "search_api_requests_get", mock_get)

        assert _get_citations_from_title_searchapi(PAPER_TITLE, "key") == 9
        assert calls[-1]["view_op"] == "view_citation"

    def test_searchapi_author_lookup_is_standalone(self, monkeypatch):
        responses = iter(
            [
                SearchApiResponse(
                    {
                        "organic_results": [
                            {
                                "title": PAPER_TITLE,
                                "authors": [{"name": "M Manica"}],
                            }
                        ]
                    }
                ),
                SearchApiResponse({"profiles": [{"author_id": "author-id"}]}),
                SearchApiResponse(
                    {"articles": [{"title": PAPER_TITLE, "citation_id": "paper-id"}]}
                ),
                SearchApiResponse(
                    {
                        "citation": {
                            "scholar_articles": {
                                "title": PAPER_TITLE,
                                "cited_by": {"total": 9},
                            }
                        }
                    }
                ),
            ]
        )
        monkeypatch.setattr(
            utils, "search_api_requests_get", lambda **kwargs: next(responses)
        )

        assert get_citation_count_from_searchapi_author(PAPER_TITLE, "key") == 9

    def test_searchapi_rejects_unrelated_results(self, monkeypatch):
        data = {
            "search_metadata": {"id": "search-unrelated"},
            "organic_results": [
                {
                    "title": "A survey of AI for materials science",
                    "inline_links": {
                        "versions": {"cluster_id": "15019771125301041201"}
                    },
                }
            ],
        }
        monkeypatch.setattr(
            utils,
            "search_api_requests_get",
            lambda **kwargs: SearchApiResponse(data),
        )

        with pytest.raises(RuntimeError, match="no complete exact match"):
            _get_citations_from_title_searchapi(PAPER_TITLE, "key")

    def test_searchapi_rejects_incomplete_exact_result(self, monkeypatch):
        data = {
            "search_metadata": {"id": "search-incomplete"},
            "organic_results": [
                {
                    "title": PAPER_TITLE,
                    "type": "CITATION",
                    "inline_links": {"versions": {"cluster_id": "wrong-cluster-id"}},
                }
            ],
        }
        monkeypatch.setattr(
            utils,
            "search_api_requests_get",
            lambda **kwargs: SearchApiResponse(data),
        )

        with pytest.raises(RuntimeError, match="no complete exact match"):
            _get_citations_from_title_searchapi(PAPER_TITLE, "key")

    def test_citation_backend_resolution(self, monkeypatch):
        monkeypatch.setattr(utils, "SEARCH_API_KEY", "search-key")
        monkeypatch.setattr(utils, "SS_API_KEY", "semantic-scholar-key")
        assert _resolve_citation_backend("auto", None) == "searchapi"

        monkeypatch.setattr(utils, "SEARCH_API_KEY", None)
        assert _resolve_citation_backend("auto", None) == "semantic_scholar"

        monkeypatch.setattr(utils, "SS_API_KEY", None)
        assert _resolve_citation_backend("auto", None) == "scholarly"

        with pytest.raises(ValueError, match="cannot be used"):
            get_citations_from_title(PAPER_TITLE, api_key="key")
        with pytest.raises(ValueError, match="Unknown backend"):
            get_citations_from_title(PAPER_TITLE, backend="invalid")
        with pytest.raises(ValueError, match="SEARCH_API_KEY"):
            get_citations_from_title(PAPER_TITLE, backend="searchapi")
        with pytest.raises(ValueError, match="not supported"):
            get_citations_from_title(PAPER_TITLE, backend="scholarly", api_key="key")

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
