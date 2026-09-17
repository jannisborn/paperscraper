import logging
import time

import pandas as pd

from paperscraper.pdf import load_api_keys
from paperscraper.scholar import get_and_dump_scholar_papers, get_scholar_papers
from paperscraper.tests.scholar import handle_scholarly_exception

logging.disable(logging.INFO)

API_KEYS = load_api_keys("api_keys.txt")
FIELDS = ["title", "abstract", "citations", "year", "authors", "journal"]
SEARCH_API_TEST_COOLDOWN = 5
GT4SD_TITLE = (
    "Accelerating material design with the generative toolkit for scientific discovery"
)
REGRESSION_TRANSFORMER_TITLE = (
    "Regression transformer enables concurrent sequence regression and generation "
    "for molecular language modelling"
)


class TestScholar:
    @handle_scholarly_exception
    def test_dump_search(self, tmpdir):
        temp_dir = tmpdir.mkdir("scholar_papers")
        output_filepath = temp_dir.join("results.jsonl")
        get_and_dump_scholar_papers("GT4SD", str(output_filepath), backend="scholarly")
        assert output_filepath.check(file=1)

    @handle_scholarly_exception
    def test_basic_search(self):
        results = get_scholar_papers("GT4SD", backend="scholarly")
        assert len(results) > 0 and isinstance(results, pd.DataFrame)
        assert all(x in results.columns for x in FIELDS)

    def test_searchapi(self):
        results = get_scholar_papers(
            f'"{GT4SD_TITLE}"',
            backend="searchapi",
            api_key=API_KEYS["SEARCH_API_KEY"],
            search_api_kwargs={
                "top_k": 1,
                "num_enrich": 1,
                "max_author_requests": 4,
            },
        )
        assert len(results) > 0 and isinstance(results, pd.DataFrame)
        assert all(x in results.columns for x in FIELDS)
        gt4sd = results.iloc[0]
        assert gt4sd["title"].casefold() == GT4SD_TITLE.casefold()
        assert gt4sd["citations"] > 0
        assert gt4sd["year"] == 2023
        assert gt4sd["journal"].lower() == "npj computational materials"
        assert "John R Smith" in gt4sd["authors"]
        assert "Generative Toolkit for Scientific Discovery" in gt4sd["abstract"]
        time.sleep(SEARCH_API_TEST_COOLDOWN)

        regression_transformer = get_scholar_papers(
            f'"{REGRESSION_TRANSFORMER_TITLE}"',
            backend="searchapi",
            api_key=API_KEYS["SEARCH_API_KEY"],
            search_api_kwargs={
                "top_k": 1,
                "num_enrich": 1,
                "max_author_requests": 5,
            },
        ).iloc[0]
        assert (
            regression_transformer["title"].casefold()
            == REGRESSION_TRANSFORMER_TITLE.casefold()
        )
        assert regression_transformer["citations"] > 0
        assert regression_transformer["journal"] == "Nature Machine Intelligence"
        time.sleep(SEARCH_API_TEST_COOLDOWN)

    @handle_scholarly_exception
    def test_bad_search(self):
        results = get_scholar_papers("GT4SDfsdhfiobfpsdfbsdp", backend="scholarly")
        assert len(results) == 0
