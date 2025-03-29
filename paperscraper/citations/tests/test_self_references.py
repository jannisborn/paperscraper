import logging
import time

import pytest

from paperscraper.citations import self_references
from paperscraper.citations.self_references import ReferenceResult

logging.disable(logging.INFO)


class TestSelfReferences:
    @pytest.fixture
    def dois(self):
        return [
            "10.1038/s43586-024-00334-2",
            "10.1038/s41586-023-06600-9",
            "10.1016/j.neunet.2014.09.003",
        ]

    def test_single_doi(self, dois):
        result = self_references(dois[0])
        assert isinstance(result, dict)
        assert len(result) > 0
        for doi, ref_result in result.items():
            assert isinstance(doi, str)
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

    def test_multiple_dois(self, dois):
        result = self_references(dois[1:])
        assert isinstance(result, dict)
        assert len(result) == len(dois[1:])
        for doi, ref_result in result.items():
            assert isinstance(doi, str)
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
        self_references(dois)
        async_duration = time.perf_counter() - start_time

        # Measure synchronous execution time (three independent calls)
        start_time = time.perf_counter()
        for doi in dois:
            self_references(doi)
        sync_duration = time.perf_counter() - start_time

        print(f"Asynchronous execution time (batch): {async_duration:.2f} seconds")
        print(
            f"Synchronous execution time (independent calls): {sync_duration:.2f} seconds"
        )

        # Assert that async execution (batch) is faster or at least not slower
        assert 0.75 * async_duration <= sync_duration, (
            f"Async execution ({async_duration:.2f}s) is slower than sync execution "
            f"({sync_duration:.2f}s)"
        )
