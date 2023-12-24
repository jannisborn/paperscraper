import logging

import pytest
from paperscraper.impact import Impactor

logging.disable(logging.INFO)


class TestImpactor:
    @pytest.fixture
    def impactor(self):
        return Impactor()

    def test_basic_search(self, impactor: Impactor):
        results = impactor.search("Nat Comm", threshold=99, sort_by="score")
        assert len(results) > 0  # Ensure we get some results
        assert all(
            "journal" in r and "factor" in r and "score" in r for r in results
        )  # Basic fields are present

    def test_fuzzy_search(self, impactor: Impactor):
        results = impactor.search("Nat Comm", threshold=99)
        assert any(
            r["journal"] == "Nature Communications" for r in results
        )  # Check for a specific journal

    def test_sort_by_score(self, impactor: Impactor):
        results = impactor.search("nature chem", threshold=80, sort_by="score")
        scores = [r["score"] for r in results]
        assert scores == sorted(
            scores, reverse=True
        )  # Ensure results are sorted by score

    def test_impact_factor_filtering(self, impactor: Impactor):
        results = impactor.search("Quantum information", threshold=70, min_impact=8)
        assert all(
            8 <= r["factor"] for r in results
        )  # Check if all results have a factor >= 8

    def test_return_all_fields(self, impactor: Impactor):
        results = impactor.search("nature chem", return_all=True)
        assert all(
            len(r) > 3 for r in results
        )  # Check if more than the basic fields are returned

    def test_quantum_information_search(self, impactor):
        expected_results = [
            {"journal": "npj Quantum Information", "factor": 10.758, "score": 95},
            {"journal": "InfoMat", "factor": 24.798, "score": 71},
            {"journal": "Information Fusion", "factor": 17.564, "score": 71},
        ]

        results = impactor.search(
            "Quantum information", threshold=70, sort_by="score", min_impact=8
        )

        # Ensure that the results match the expected results
        assert len(results) == len(expected_results), "Number of results does not match"
        for expected, actual in zip(expected_results, results):
            assert (
                expected["journal"] == actual["journal"]
            ), f"Journal name does not match for {expected['journal']}"
            assert (
                abs(expected["factor"] - actual["factor"]) < 0.001
            ), f"Impact factor does not match for {expected['journal']}"
            assert (
                expected["score"] == actual["score"]
            ), f"Score does not match for {expected['journal']}"
