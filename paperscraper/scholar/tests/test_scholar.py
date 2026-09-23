import logging
import time

import pandas as pd
import pytest

from paperscraper.pdf import load_api_keys
from paperscraper.scholar import (
    get_and_dump_scholar_papers,
    get_scholar_author_papers,
    get_scholar_papers,
)
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
AUTHOR_FIELDS = ["title", "authors", "publication", "year", "citations"]
JANNIS_AUTHOR_ID = "FHL-zfsAAAAJ"


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

    def test_searchapi_author_profile(self):
        results = get_scholar_author_papers(
            "Jannis Born",
            api_key=API_KEYS["SEARCH_API_KEY"],
        )
        assert len(results) == 30
        assert list(results.columns) == AUTHOR_FIELDS
        assert (
            REGRESSION_TRANSFORMER_TITLE.casefold()
            in results["title"].str.casefold().tolist()
        )
        assert all(results["publication"])
        assert all(results["authors"].map(bool))
        assert all(results["citations"] >= 0)
        time.sleep(SEARCH_API_TEST_COOLDOWN)

        detailed = get_scholar_author_papers(
            "Jannis Born",
            max_results=1,
            author_id=JANNIS_AUTHOR_ID,
            api_key=API_KEYS["SEARCH_API_KEY"],
            full_info=True,
        ).iloc[0]
        assert detailed["journal"]
        assert detailed["date"]
        assert detailed["description"]
        assert detailed["citations"] >= 0
        time.sleep(SEARCH_API_TEST_COOLDOWN)

    def test_searchapi_author_max_results(self):
        results = get_scholar_author_papers(
            "Jannis Born",
            max_results=31,
            author_id=JANNIS_AUTHOR_ID,
            api_key=API_KEYS["SEARCH_API_KEY"],
        )
        assert len(results) == 31
        time.sleep(SEARCH_API_TEST_COOLDOWN)

    def test_searchapi_author_without_profile(self):
        results = get_scholar_author_papers(
            "ali oskooei",
            max_results=1,
            api_key=API_KEYS["SEARCH_API_KEY"],
        )
        assert len(results) == 1
        assert list(results.columns) == AUTHOR_FIELDS
        assert any("Oskooei" in author for author in results.iloc[0]["authors"])
        assert results.iloc[0]["publication"]
        assert results.iloc[0]["citations"] >= 0
        time.sleep(SEARCH_API_TEST_COOLDOWN)

    def test_searchapi_author_validation(self):
        assert get_scholar_author_papers("Jannis Born", max_results=0).empty
        with pytest.raises(ValueError, match="non-negative"):
            get_scholar_author_papers("Jannis Born", max_results=-1)
        with pytest.raises(TypeError, match="Pass int"):
            get_scholar_author_papers("Jannis Born", max_results=True)
        with pytest.raises(TypeError, match="Pass int"):
            get_scholar_author_papers("Jannis Born", max_results=None)

    @handle_scholarly_exception
    def test_bad_search(self):
        results = get_scholar_papers("GT4SDfsdhfiobfpsdfbsdp", backend="scholarly")
        assert len(results) == 0
