import logging
import time
from typing import Dict

import pytest

from paperscraper.citations import self_references_paper
from paperscraper.citations.self_references import ReferenceResult

logging.disable(logging.INFO)


class TestSelfReferences:
    @pytest.fixture
    def dois(self):
        return [
            "10.1038/s41586-023-06600-9",
            "10.1016/j.neunet.2014.09.003",
        ]

    def test_single_doi(self, dois):
        result = self_references_paper(dois[0])
        assert isinstance(result, ReferenceResult)
        assert isinstance(result.num_references, int)
        assert result.num_references > 0
        assert isinstance(result.ssid, str)
        assert isinstance(result.reference_score, float)
        assert result.reference_score > 0
        assert isinstance(result.self_references, Dict)
        for author, self_cites in result.self_references.items():
            assert isinstance(author, str)
            assert isinstance(self_cites, float)
            assert self_cites >= 0 and self_cites <= 100

    def test_multiple_dois(self, dois):
        results = self_references_paper(dois[1:])
        assert isinstance(results, list)
        assert len(results) == len(dois[1:])
        for ref_result in results:
            assert isinstance(ref_result, ReferenceResult)
            assert isinstance(ref_result.ssid, str)
            assert isinstance(ref_result.num_references, int)
            assert ref_result.num_references > 0
            assert ref_result.reference_score > 0
            assert isinstance(ref_result.reference_score, float)
            for author, self_cites in ref_result.self_references.items():
                assert isinstance(author, str)
                assert isinstance(self_cites, float)
                assert self_cites >= 0 and self_cites <= 100

    def test_compare_async_and_sync_performance(self, dois):
        """
        Compares the execution time of asynchronous and synchronous `self_references`
        for a list of DOIs.
        """

        start_time = time.perf_counter()
        async_results = self_references_paper(dois)
        async_duration = time.perf_counter() - start_time

        # Measure synchronous execution time (three independent calls)
        start_time = time.perf_counter()
        sync_results = [self_references_paper(doi) for doi in dois]

        sync_duration = time.perf_counter() - start_time

        print(f"Asynchronous execution time (batch): {async_duration:.2f} seconds")
        print(
            f"Synchronous execution time (independent calls): {sync_duration:.2f} seconds"
        )
        for a, s in zip(async_results, sync_results):
            assert a == s, f"{a} vs {s}"

        # Assert that async execution (batch) is faster or at least not slower
        assert 0.9 * async_duration <= sync_duration, (
            f"Async execution ({async_duration:.2f}s) is slower than sync execution "
            f"({sync_duration:.2f}s)"
        )
