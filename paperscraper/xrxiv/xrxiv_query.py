"""Query dumps from bioRxiv and medRXiv."""

import logging
import sys
from typing import List, Union

import pandas as pd

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


class XRXivQuery:
    """Query class."""

    def __init__(
        self,
        dump_filepath: str,
        fields: List[str] = ["title", "doi", "authors", "abstract", "date", "journal"],
    ):
        """
        Initialize the query class.

        Args:
            dump_filepath (str): filepath to the dump to be queried.
            fields (List[str], optional): fields to contained in the dump per paper.
                Defaults to ['title', 'doi', 'authors', 'abstract', 'date', 'journal'].
        """
        self.dump_filepath = dump_filepath
        self.fields = fields
        self.errored = False

        try:
            self.df = pd.read_json(self.dump_filepath, lines=True)
            self.df["date"] = [date.strftime("%Y-%m-%d") for date in self.df["date"]]
        except ValueError as e:
            logger.warning(f"Problem in reading file {dump_filepath}: {e} - Skipping!")
            self.errored = True
        except KeyError as e:
            logger.warning(f"Key {e} missing in file from {dump_filepath} - Skipping!")
            self.errored = True

    def search_keywords(
        self,
        keywords: List[Union[str, List[str]]],
        fields: List[str] = None,
        output_filepath: str = None,
    ) -> pd.DataFrame:
        """
        Search for papers in the dump using keywords.

        Args:
            keywords (List[str, List[str]]): Items will be AND separated. If items
                are lists themselves, they will be OR separated.
            fields (List[str], optional): fields to be used in the query search.
                Defaults to None, a.k.a. search in all fields excluding date.
            output_filepath (str, optional): optional output filepath where to store
                the hits in JSONL format. Defaults to None, a.k.a., no export to a file.

        Returns:
            pd.DataFrame: A dataframe with one paper per row.
        """
        if fields is None:
            fields = self.fields
        fields = [field for field in fields if field != "date"]
        hits_per_field = []
        for field in fields:
            field_data = self.df[field].str.lower()
            hits_per_keyword = []
            for keyword in keywords:
                if isinstance(keyword, list):
                    query = "|".join([_.lower() for _ in keyword])
                else:
                    query = keyword.lower()
                hits_per_keyword.append(field_data.str.contains(query))
            if len(hits_per_keyword):
                keyword_hits = hits_per_keyword[0]
                for single_keyword_hits in hits_per_keyword[1:]:
                    keyword_hits &= single_keyword_hits
                hits_per_field.append(keyword_hits)
        if len(hits_per_field):
            hits = hits_per_field[0]
            for single_hits in hits_per_field[1:]:
                hits |= single_hits
        if output_filepath is not None:
            self.df[hits].to_json(output_filepath, orient="records", lines=True)
        return self.df[hits]
