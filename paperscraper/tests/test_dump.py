import importlib
import logging
import multiprocessing
import os
import time
from datetime import datetime, timedelta
from functools import partial

import pytest

import paperscraper.load_dumps as load_dumps_module
from paperscraper import dump_queries
from paperscraper.arxiv import get_and_dump_arxiv_papers
from paperscraper.get_dumps import arxiv, biorxiv, chemrxiv, medrxiv
from paperscraper.load_dumps import QUERY_FN_DICT

logging.disable(logging.INFO)

covid19 = ["COVID-19", "SARS-CoV-2"]
ai = ["Artificial intelligence", "Deep learning", "Machine learning"]
mi = ["Medical imaging"]


def target_func(queue, func):
    try:
        func()
        queue.put(True)  # Function completed (this should never happen)
    except Exception as e:
        queue.put(e)


class TestDumper:
    def test_dump_existence_initial(self):
        # This test checks the initial state, should be run first if order matters
        assert len(QUERY_FN_DICT) == 2, "Initial length of QUERY_FN_DICT should be 2"

    @pytest.fixture
    def setup_medrxiv(self):
        return medrxiv

    @pytest.fixture
    def setup_biorxiv(self):
        return partial(biorxiv, max_retries=2)

    @pytest.fixture
    def setup_chemrxiv(self):
        return chemrxiv

    @pytest.fixture
    def setup_arxiv(self):
        return arxiv

    def run_function_with_timeout(self, func, timeout):
        queue = multiprocessing.Queue()
        process = multiprocessing.Process(target=target_func, args=(queue, func))
        process.start()
        time.sleep(timeout)

        was_alive = process.is_alive()
        process.terminate()
        process.join()

        if not was_alive and not queue.empty():
            raise queue.get()
        elif not was_alive:
            return False
        else:
            return True

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

    @pytest.mark.timeout(30)
    def test_chemrxiv(self, setup_chemrxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(
            setup_chemrxiv, 15
        ), "chemrxiv should still be running after 15 seconds"

    @pytest.mark.timeout(30)
    def test_arxiv(self, setup_arxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(
            setup_arxiv, 15
        ), "arxiv should still be running after 90 seconds"

    def test_chemrxiv_date(self):
        chemrxiv(start_date="2024-06-01", end_date="2024-06-02")

    def test_biorxiv_date(self):
        biorxiv(start_date="2024-06-01", end_date="2024-06-02")

    def test_arxiv_date(self):
        # Result of this may be empty because arxiv updates not daily.
        # With days=4 it should never be empty.
        arxiv(start_date=(datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d"))

        arxiv(end_date="1991-01-01")
        arxiv(start_date="1993-04-01", end_date="1993-04-03")

    def test_arxiv_wrong_date(self):
        with pytest.raises(
            ValueError, match=r"start_date .* cannot be later than end_date .*"
        ):
            arxiv(start_date="2024-06-02", end_date="2024-06-01")

    def test_dumping(self):
        queries = [[covid19, ai, mi]]
        dump_queries(queries, "tmpdir")
        assert os.path.exists("tmpdir/pubmed")

    def test_arxiv_dumping(self):
        query = [covid19, ai, mi]
        get_and_dump_arxiv_papers(query, output_filepath="covid19_ai_imaging.jsonl")
        assert os.path.exists("covid19_ai_imaging.jsonl")

    def test_get_arxiv_date(self):
        get_and_dump_arxiv_papers(
            [["MPEGO"]],
            output_filepath="mpego.jsonl",
            start_date="2020-06-01",
            end_date="2024-06-02",
            backend="api",
        )
        get_and_dump_arxiv_papers(
            [["PaccMann"]],
            output_filepath="paccmann.jsonl",
            end_date="2023-06-02",
            backend="infer",
        )
        get_and_dump_arxiv_papers(
            [["QontOT"]],
            output_filepath="qontot.jsonl",
            start_date="2023-01-02",
            backend="local",
        )

    def test_dump_existence(self):
        importlib.reload(load_dumps_module)
        from paperscraper.load_dumps import QUERY_FN_DICT

        assert (
            len(QUERY_FN_DICT) == 5
        ), f"Expected QUERY_FN_DICT to also contain med/bio/chemrxiv, {QUERY_FN_DICT}"
