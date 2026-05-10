import importlib
import logging
import multiprocessing
import os
import shutil
import time
from datetime import datetime, timedelta
from functools import partial

import arxiv as arxiv_api
import pytest

import paperscraper.load_dumps as load_dumps_module
from paperscraper import dump_queries
from paperscraper.arxiv import get_and_dump_arxiv_papers
from paperscraper.get_dumps import arxiv, biorxiv, chemrxiv, medrxiv
from paperscraper.load_dumps import QUERY_FN_DICT
from paperscraper.utils import get_server_dumps_dir

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
    def run_with_arxiv_retries(self, func, retries=3, sleep_seconds=2):
        retryable_statuses = {406, 429, 500, 502, 503, 504}
        last_exc = None

        for attempt in range(1, retries + 1):
            try:
                return func()
            except arxiv_api.HTTPError as exc:
                status = getattr(exc, "status", None)
                if status == 429:
                    pytest.skip(
                        "Skipping arXiv-backed test due to HTTP 429 rate limiting"
                    )
                if status not in retryable_statuses:
                    raise
                if attempt == retries:
                    raise
                last_exc = exc
                # arXiv frequently rate-limits shared CI runners. Use a longer
                # cooldown for transient server-side failures.
                time.sleep(sleep_seconds * attempt)

        if last_exc is not None:
            raise last_exc

    def test_dump_existence_initial(self):
        assert {"arxiv", "pubmed"} <= set(QUERY_FN_DICT), (
            f"Expected QUERY_FN_DICT to contain at least arxiv and pubmed, {QUERY_FN_DICT}"
        )

    @pytest.fixture
    def setup_medrxiv(self):
        return partial(medrxiv, max_retries=2)

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

    @pytest.mark.timeout(15)
    def test_medrxiv(self, setup_medrxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(setup_medrxiv, 15), (
            "medrxiv should still be running after 15 seconds"
        )

    @pytest.mark.timeout(15)
    def test_biorxiv(self, setup_biorxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(setup_biorxiv, 15), (
            "biorxiv should still be running after 15 seconds"
        )

    @pytest.mark.timeout(15)
    def test_chemrxiv(self, setup_chemrxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(setup_chemrxiv, 15), (
            "chemrxiv should still be running after 15 seconds"
        )

    @pytest.mark.timeout(15)
    def test_arxiv(self, setup_arxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(setup_arxiv, 15), (
            "arxiv should still be running after 15 seconds"
        )

    def test_chemrxiv_date(self):
        chemrxiv(start_date="2024-06-01", end_date="2024-06-01")

    def test_medrxiv_date(self):
        medrxiv(start_date="2024-06-01", end_date="2024-06-01")

    def test_biorxiv_date(self):
        biorxiv(start_date="2014-06-01", end_date="2014-06-04")

    def test_arxiv_date(self):
        # Result of this may be empty because arxiv updates not daily.
        # With days=4 it should never be empty.
        arxiv(start_date=(datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d"))

        arxiv(end_date="1991-01-01")
        arxiv(start_date="1993-04-03", end_date="1993-04-03")

    def test_arxiv_wrong_date(self):
        with pytest.raises(
            ValueError, match=r"start_date .* cannot be later than end_date .*"
        ):
            arxiv(start_date="2024-06-02", end_date="2024-06-01")

    def test_dumping(self):
        queries = [["MPEGO"]]
        self.run_with_arxiv_retries(
            lambda: dump_queries(queries, "tmpdir"),
            retries=5,
            sleep_seconds=10,
        )
        assert os.path.exists("tmpdir/pubmed")

    def test_arxiv_dumping(self):
        self.run_with_arxiv_retries(
            lambda: get_and_dump_arxiv_papers(
                ["MPEGO"],
                output_filepath="covid19_ai_imaging.jsonl",
                backend="api",
                max_results=5,
                client_options={
                    "delay_seconds": 6.0,
                    "page_size": 50,
                    "num_retries": 3,
                },
            ),
            retries=5,
            sleep_seconds=10,
        )
        assert os.path.exists("covid19_ai_imaging.jsonl")

    def test_get_arxiv_date(self):
        def run_once():
            get_and_dump_arxiv_papers(
                [["MPEGO"]],
                output_filepath="mpego.jsonl",
                start_date="2020-06-01",
                end_date="2024-06-02",
                backend="api",
            )
            # Ensure infer/local backends read a valid local dump even if a
            # broken bundled arxiv dump is present in server_dumps.
            local_dump_path = os.path.join(
                get_server_dumps_dir(),
                "arxiv_9999-12-31.jsonl",
            )
            shutil.copyfile("mpego.jsonl", local_dump_path)
            arxiv_module = importlib.import_module("paperscraper.arxiv.arxiv")
            arxiv_module.ARXIV_QUERIER = None

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

        self.run_with_arxiv_retries(
            run_once,
            retries=5,
            sleep_seconds=10,
        )

    def test_dump_existence(self):
        importlib.reload(load_dumps_module)
        from paperscraper.load_dumps import QUERY_FN_DICT

        expected_dbs = {"arxiv", "pubmed", "biorxiv", "chemrxiv", "medrxiv"}
        assert expected_dbs <= set(QUERY_FN_DICT), (
            f"Expected QUERY_FN_DICT to contain {expected_dbs}, {QUERY_FN_DICT}"
        )
