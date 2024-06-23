import logging
import pandas as pd

import pytest

from paperscraper.scholar import get_scholar_papers

logging.disable(logging.INFO)


class TestScholar:

    def test_basic_search(self):
        results = get_scholar_papers("GT4SD")
        assert len(results) > 0  # Ensure we get some results
        assert isinstance(results, pd.DataFrame)
        assert all(
            [
                x in results.columns
                for x in [
                    "title",
                    "abstract",
                    "citations",
                    "year",
                    "authors",
                    "journal",
                ]
            ]
        )
