"""Query dumps from bioRxiv and medRXiv."""
import pandas as pd
from typing import List


class XRXivQuery:
    """Query class."""

    def __init__(
        self,
        dump_filepath: str,
        fields: List[str] = ['title', 'doi', 'authors', 'abstract', 'date']
    ):
        """
        Initialize the query class.

        Args:
            dump_filepath (str): filepath to the dump to be queried.
            fields (List[str], optional): fields to contained in the dump per paper.
                Defaults to ['title', 'doi', 'authors', 'abstract', 'date'].
        """
        self.dump_filepath = dump_filepath
        self.fields = fields
        self.df = pd.read_json(self.dump_filepath, lines=True)

    def search(
        self, query: dict,
        fields: List[dict] = None
    ) -> List[dict]:
        """
        Search for papers in the dump.

        Args:
            query (dict): a dictionary representing a query.
            fields (List[dict], optional): fields to be used in the query search. Defaults to None.

        Returns:
            List[dict]: a list of papers associated to the query.
        """
        raise NotImplementedError('query mechanism to be implemented')
