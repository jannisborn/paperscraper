import logging
import time
from typing import Dict

import pytest

from paperscraper.citations import self_references_paper
from paperscraper.citations.entity import Researcher
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

    def test_researcher(self):
        """
        Tests calculation of self-references for all papers of an author.
        """
        ssaid = "2326988211"
        researcher = Researcher(ssaid)
        result = researcher.self_references(verbose=True)
        assert result.ssaid == int(ssaid)
        assert isinstance(result.name, str)
        assert result.name == "Patrick Soga"
        assert isinstance(result.num_references, int)
        assert result.num_references > 0
        assert isinstance(result.num_citations, int)
        assert result.num_citations == -1
        assert isinstance(result.self_references, Dict)
        for title, ratio in result.self_references.items():
            assert isinstance(title, str)
            assert isinstance(ratio, float)
            assert ratio >= 0 and ratio <= 100

        assert result.self_reference_ratio >= 0 and result.self_reference_ratio <= 100
        print(result)

    def test_researcher_from_orcid(self):
        """
        Tests calculation of self-references for all papers of an author.
        """
        orcid = "0000-0003-4221-6988"
        researcher = Researcher(orcid)
        result = researcher.self_references(verbose=True)
        assert result.orcid == orcid
        assert isinstance(result.name, str)
        assert result.name == "Juan M. Galeazzi"
        assert isinstance(result.num_references, int)
        assert result.num_references > 0
        assert isinstance(result.num_citations, int)
        assert result.num_citations == -1
        assert isinstance(result.self_references, Dict)
        for title, ratio in result.self_references.items():
            assert isinstance(title, str)
            assert isinstance(ratio, float)
            assert ratio >= 0 and ratio <= 100

        assert result.self_reference_ratio >= 0 and result.self_reference_ratio <= 100
        print(result)
