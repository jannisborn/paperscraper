import logging
import time

import pytest

from paperscraper.citations import self_citations_paper
from paperscraper.citations.self_citations import CitationResult

logging.disable(logging.INFO)


class TestSelfCitations:
    @pytest.fixture
    def dois(self):
        return [
            "10.1038/s41586-023-06600-9",
            "ed69978f1594a4e2b9dccfc950490fa1df817ae8",
        ]

    def test_single_doi(self, dois):
        result = self_citations_paper(dois[0])
        assert isinstance(result, CitationResult)
        assert isinstance(result.ssid, str)
        assert isinstance(result.num_citations, int)
        assert result.num_citations > 10
        assert isinstance(result.citation_score, float)
        assert result.citation_score > 0
        for author, self_cites in result.self_citations.items():
            assert isinstance(author, str)
            assert isinstance(self_cites, float)
            assert self_cites >= 0 and self_cites <= 100
        time.sleep(5)

    def test_multiple_dois(self, dois):
        start_time = time.perf_counter()
        result = self_citations_paper(dois)
        async_duration = time.perf_counter() - start_time
        assert isinstance(result, list)
        assert len(result) == len(dois)
        for cit_result in result:
            assert isinstance(cit_result, CitationResult)
            assert isinstance(cit_result.ssid, str)
            assert isinstance(cit_result.num_citations, int)
            assert cit_result.num_citations > 0
            assert cit_result.citation_score > 0
            assert isinstance(cit_result.citation_score, float)
            for author, self_cites in cit_result.self_citations.items():
                assert isinstance(author, str)
                assert isinstance(self_cites, float)
                assert self_cites >= 0 and self_cites <= 100
        time.sleep(5)

        # compare async and sync performance

        # Measure synchronous execution time (three independent calls)
        start_time = time.perf_counter()
        sync_result = [self_citations_paper(doi) for doi in dois]
        sync_duration = time.perf_counter() - start_time

        print(f"Asynchronous execution time (batch): {async_duration:.2f} seconds")
        print(
            f"Synchronous execution time (independent calls): {sync_duration:.2f} seconds"
        )

        # Assert that async execution (batch) is faster or at least not slower
        assert 0.9 * async_duration <= sync_duration, (
            f"Async execution ({async_duration:.2f}s) is slower than sync execution "
            f"({sync_duration:.2f}s)"
        )

        for a, s in zip(result, sync_result):
            assert a == s, f"{a} vs {s}"
