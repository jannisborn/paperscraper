import os

from paperscraper.get_dumps import medrxiv
from paperscraper.xrxiv.xrxiv_query import XRXivQuery

covid19 = ["COVID-19", "SARS-CoV-2"]
ai = ["Artificial intelligence", "Deep learning", "Machine learning"]
mi = ["Medical imaging"]


class TestXRXiv:
    def test_get_medrxiv(self):
        medrxiv(
            start_date="2020-05-01",
            end_date="2020-05-10",
            save_path="medrix_tmp_dump.jsonl",
        )

    def test_xriv_querier(self):
        querier = XRXivQuery("medrix_tmp_dump.jsonl")
        query = [covid19, ai, mi]
        querier.search_keywords(query, output_filepath="covid19_ai_imaging.jsonl")
        assert os.path.exists("covid19_ai_imaging.jsonl")
