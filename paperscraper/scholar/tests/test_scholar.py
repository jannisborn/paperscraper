import logging

import pandas as pd

from paperscraper.pdf import load_api_keys
from paperscraper.scholar import get_and_dump_scholar_papers, get_scholar_papers
from paperscraper.tests.scholar import handle_scholar_exception

logging.disable(logging.INFO)

API_KEYS = load_api_keys("api_keys.txt")
FIELDS = ["title", "abstract", "citations", "year", "authors", "journal"]


class TestScholar:
    @handle_scholar_exception
    def test_dump_search(self, tmpdir):
        temp_dir = tmpdir.mkdir("scholar_papers")
        output_filepath = temp_dir.join("results.jsonl")
        get_and_dump_scholar_papers("GT4SD", str(output_filepath), backend="scholarly")
        assert output_filepath.check(file=1)

    @handle_scholar_exception
    def test_basic_search(self):
        results = get_scholar_papers("GT4SD", backend="scholarly")
        assert len(results) > 0 and isinstance(results, pd.DataFrame)
        assert all(x in results.columns for x in FIELDS)

    def test_searchapi(self):
        results = get_scholar_papers(
            "GT4SD",
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
        gt4sd = results[
            results["title"].str.contains("generative toolkit", case=False)
        ].iloc[0]
        assert gt4sd["citations"] > 0
        assert gt4sd["year"] == 2023
        assert gt4sd["journal"].lower() == "npj computational materials"
        assert "John R Smith" in gt4sd["authors"]
        assert "Generative Toolkit for Scientific Discovery" in gt4sd["abstract"]

        regression_transformer = get_scholar_papers(
            "Regression Transformer",
            backend="searchapi",
            api_key=API_KEYS["SEARCH_API_KEY"],
            search_api_kwargs={
                "top_k": 1,
                "num_enrich": 1,
                "max_author_requests": 5,
            },
        ).iloc[0]
        assert regression_transformer["citations"] > 0
        assert regression_transformer["journal"] == "Nature Machine Intelligence"

    @handle_scholar_exception
    def test_bad_search(self):
        results = get_scholar_papers("GT4SDfsdhfiobfpsdfbsdp", backend="scholarly")
        assert len(results) == 0
