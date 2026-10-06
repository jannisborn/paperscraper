"""Focused checks for the shared client and functional compatibility wrappers."""

from unittest.mock import Mock

import pytest
import requests

from paperscraper.citations import get_citations_from_title
from paperscraper.citations.utils import SEARCH_API_CACHE, search_api_requests_get
from paperscraper.scholar import get_scholar_papers
from paperscraper.searchapi import (
    SearchAPICitations,
    SearchAPIClient,
    SearchAPIScholar,
    core,
)


def test_client_credentials_and_external_requests(monkeypatch):
    response = requests.Response()
    response.status_code = 200
    response._content = b"citation text"
    get = Mock(return_value=response)
    monkeypatch.setattr(core.requests, "get", get)
    monkeypatch.setattr(core, "SEARCH_API_KEY", "environment-key")

    client = SearchAPIClient("explicit-key")
    client.get(params={"engine": "google_scholar"})
    get.assert_called_once_with(
        core.SEARCH_API_URL,
        timeout=90,
        headers={"Authorization": "Bearer explicit-key"},
        params={"engine": "google_scholar"},
    )
    search_api_requests_get()
    assert get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer environment-key"
    }

    citations = SearchAPICitations(client)
    assert (
        citations._get_export("https://scholar.google.com/export", "bibtex")
        == "citation text"
    )
    assert "Authorization" not in get.call_args.kwargs["headers"]
    citations._get_doi_metadata("10.1234/example")
    assert "Authorization" not in get.call_args.kwargs["headers"]

    get.reset_mock()
    monkeypatch.setattr(core, "SEARCH_API_KEY", None)
    with pytest.raises(ValueError, match="requires api_key"):
        SearchAPIClient().get()
    get.assert_not_called()


def test_clients_share_legacy_cache_without_authentication(monkeypatch, tmp_path):
    cache = {"citations": {"Cached paper": 7, "Uncited paper": 0}, "other": {}}
    monkeypatch.setattr(core, "SEARCH_API_CACHE", cache)
    monkeypatch.setattr(core, "SEARCH_API_KEY", None)
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(core, "SEARCH_API_CACHE_PATH", str(cache_path))

    first, second = SearchAPIClient(), SearchAPIClient()
    assert first.cache is second.cache is cache
    assert get_citations_from_title("Cached paper", backend="searchapi") == 7
    assert get_citations_from_title("Uncited paper", backend="searchapi") == 0
    assert first.get_cached_citation("Cached paper") == 7
    with pytest.raises(KeyError):
        first.get_cached_citation("Not cached")
    first.cache_citation("Another paper", 3)
    assert second.cache["citations"]["Another paper"] == 3
    assert first.load_cache(str(cache_path)) == cache


def test_scholar_and_citations_use_casefold_matching(monkeypatch):
    assert SEARCH_API_CACHE is core.SEARCH_API_CACHE
    response = Mock()
    response.json.return_value = {
        "organic_results": [
            {"title": "STRASSE", "inline_links": {"cited_by": {"total": 4}}}
        ]
    }
    monkeypatch.setattr(SearchAPIClient, "get", Mock(return_value=response))
    monkeypatch.setattr(core, "SEARCH_API_CACHE", {"citations": {}})
    monkeypatch.setattr(core, "SEARCH_API_CACHE_PATH", None)

    papers = get_scholar_papers(
        '"Straße"',
        backend="searchapi",
        search_api_kwargs={"num_enrich": 0},
    )
    assert papers.iloc[0]["title"] == "STRASSE"
    assert get_citations_from_title("Straße", backend="searchapi") == 4


def test_services_reuse_injected_client_without_leaking_request_budgets(monkeypatch):
    paper = {
        "title": "Example paper",
        "authors": [{"id": "author"}],
        "inline_links": {"cited_by": {"total": 1}},
    }
    search = {"organic_results": [paper]}
    profile = {"articles": [{"title": "Example paper", "citation_id": "author:paper"}]}
    details = {
        "citation": {
            "title": "Example paper",
            "authors": "Alice Author",
            "description": "Full abstract",
            "cited_by": {"total": 1},
        }
    }
    responses = [
        Mock(json=Mock(return_value=data))
        for data in [search, profile, details, profile, details] * 2
    ]
    client = SearchAPIClient("test-key")
    get = Mock(side_effect=responses)
    monkeypatch.setattr(client, "get", get)
    scholar = SearchAPIScholar(client)
    citations = SearchAPICitations(client)
    assert scholar.client is scholar.citations.client is citations.client is client

    for _ in range(2):
        papers = scholar.get_papers(
            '"Example paper"',
            search_api_kwargs={"top_k": 1, "num_enrich": 1, "max_author_requests": 2},
        )
        assert papers.iloc[0]["abstract"] == "Full abstract"
        assert papers.iloc[0]["authors"] == ["Alice Author"]
        assert (
            citations.get_citation_details(paper, {"max_author_requests": 2})
            == details["citation"]
        )
    assert get.call_count == 10
