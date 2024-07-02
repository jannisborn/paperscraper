import logging
import os
import threading

import pytest

from paperscraper import dump_queries
from paperscraper.arxiv import get_and_dump_arxiv_papers
from paperscraper.get_dumps import biorxiv, chemrxiv, medrxiv

logging.disable(logging.INFO)

covid19 = ["COVID-19", "SARS-CoV-2"]
ai = ["Artificial intelligence", "Deep learning", "Machine learning"]
mi = ["Medical imaging"]


class TestDumper:
    @pytest.fixture
    def setup_medrxiv(self):
        return medrxiv

    @pytest.fixture
    def setup_biorxiv(self):
        return lambda: biorxiv(max_retries=2)
   
    @pytest.fixture
    def setup_chemrxiv(self):
        return chemrxiv

    @pytest.fixture
    def setup_chemrxiv_date(self):
        return lambda: chemrxiv(begin_date="2024-06-01", end_date="2024-06-02")

    @pytest.fixture
    def setup_biorxiv_date(self):
        return lambda: biorxiv(begin_date="2024-06-01", end_date="2024-06-02")

    def run_function_with_timeout(self, func, timeout):
        # Define the target function for the thread
        def target():
            func()

        # Create a daemon thread that runs the target function
        thread = threading.Thread(target=target)
        thread.daemon = True  # This makes the thread exit when the main thread exits
        thread.start()
        thread.join(
            timeout=timeout
        )  # Wait for the specified time or until the function finishes
        if thread.is_alive():
            return True  # Function is still running, which is our success condition
        return False  # Function has completed or failed within the timeout, which we don't expect

    @pytest.mark.timeout(30)
    def test_medrxiv(self, setup_medrxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(
            setup_medrxiv, 15
        ), "medrxiv should still be running after 15 seconds"

    @pytest.mark.timeout(30)
    def test_biorxiv(self, setup_biorxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(
            setup_biorxiv, 15
        ), "biorxiv should still be running after 15 seconds"

    def test_dumping(self):
        queries = [[covid19, ai, mi]]
        dump_queries(queries, "tmpdir")
        assert os.path.exists("tmpdir/pubmed")

    def test_arxiv_dumping(self):
        query = [covid19, ai, mi]
        get_and_dump_arxiv_papers(query, output_filepath="covid19_ai_imaging.jsonl")
        assert os.path.exists("covid19_ai_imaging.jsonl")

    def test_dump_existence(self):
        from paperscraper.load_dumps import QUERY_FN_DICT
        assert len(QUERY_FN_DICT) > 2
