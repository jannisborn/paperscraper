import os

from paperscraper.get_dumps import medrxiv
from paperscraper.xrxiv.xrxiv_query import XRXivQuery

ai = ["Artificial intelligence", "Deep learning", "Machine learning"]
qc = ["Quantum computing", "Quantum information", "Quantum algorithm"]
mi = ["Medical imaging"]


class TestXRXiv:
    def test_get_medrxiv(self):
        medrxiv(
            start_date="2020-05-01",
            end_date="2020-05-02",
            save_path="medriv_tmp_dump.jsonl",
        )

    def test_xriv_querier(self):
        querier = XRXivQuery("medriv_tmp_dump.jsonl")
        query = [ai, qc, mi]
        querier.search_keywords(query, output_filepath="ai_quantum_imaging.jsonl")
        assert os.path.exists("ai_quantum_imaging.jsonl")
