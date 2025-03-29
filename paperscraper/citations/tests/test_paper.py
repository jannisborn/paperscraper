import logging

import pytest

from paperscraper.citations import SelfLinkClient
from paperscraper.citations.entity import PaperResult

logging.disable(logging.INFO)


class TestPaper:
    @pytest.fixture
    def ssids(self):
        return [
            "a732443cae8cd2d6a76f4f3cf785a562baf41137",  # semantic scholar ID
        ]

    @pytest.fixture
    def dois(self):
        return [
            "10.1038/s41586-023-06600-9",
            "10.1016/j.neunet.2014.09.003",
            "10.1016/j.isci.2021.102269",
        ]

    def test_paper_doi(self, dois):
        for doi in dois:
            client = SelfLinkClient(entity=doi, mode="paper")
            client.extract()
            result = client.get_result()
            assert isinstance(result, PaperResult)
            assert isinstance(result.ssid, str)
            assert isinstance(result.title, str)
            assert isinstance(result.citation_score, float)
            assert isinstance(result.reference_score, float)
            assert result.citation_score >= 0
            assert result.reference_score >= 0
            assert isinstance(result.self_references, dict)
            assert isinstance(result.self_citations, dict)

    def test_paper_ssid(self, ssids):
        for ssid in ssids:
            client = SelfLinkClient(entity=ssid, mode="paper")
            client.extract()
            result = client.get_result()
            assert isinstance(result, PaperResult)
            assert isinstance(result.ssid, str)
            assert isinstance(result.title, str)
            assert isinstance(result.citation_score, float)
            assert isinstance(result.reference_score, float)
            assert result.citation_score >= 0
            assert result.reference_score >= 0
            assert isinstance(result.self_references, dict)
            assert isinstance(result.self_citations, dict)
