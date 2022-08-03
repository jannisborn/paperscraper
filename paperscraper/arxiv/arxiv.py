from typing import Dict, List, Union

import pandas as pd

import arxiv

from ..utils import dump_papers
from .utils import get_query_from_keywords

arxiv_field_mapper = {
    "published": "date",
    "journal_ref": "journal",
    "summary": "abstract",
}

# Authors, date, and journal fields need specific processing
process_fields = {
    "authors": lambda authors: ", ".join([a.name for a in authors]),
    "date": lambda date: date.strftime("%Y-%m-%d"),
    "journal": lambda j: j if j is not None else "",
}


def get_arxiv_papers(
    query: str,
    fields: List = ["title", "authors", "date", "abstract", "journal", "doi"],
    max_results: int = 99999,
    client_options: Dict = {"num_retries": 10},
    search_options: Dict = dict(),
) -> pd.DataFrame:
    """
    Performs arxiv API request of a given query and returns list of papers with
    fields as desired.

    Args:
        query (str): Query to arxiv API. Needs to match the arxiv API notation.
        fields (List[str]): List of strings with fields to keep in output.
        max_results (int): Maximal number of results, defaults to 99999.
        client_options (Dict): Optional arguments for `arxiv.Client`. E.g.:
            page_size (int), delay_seconds (int), num_retries (int).
            NOTE: Decreasing 'num_retries' will speed up processing but might
            result in more frequent 'UnexpectedEmptyPageErrors'.
        search_options (Dict): Optional arguments for `arxiv.Search`. E.g.:
            id_list (List), sort_by, or sort_order.

    Returns:
        pd.DataFrame: One row per paper.

    """
    client = arxiv.Client(**client_options)
    search = arxiv.Search(query=query, max_results=max_results, **search_options)
    results = client.results(search)

    processed = pd.DataFrame(
        [
            {
                arxiv_field_mapper.get(key, key): process_fields.get(
                    arxiv_field_mapper.get(key, key), lambda x: x
                )(value)
                for key, value in vars(paper).items()
                if arxiv_field_mapper.get(key, key) in fields
            }
            for paper in results
        ]
    )
    return processed


def get_and_dump_arxiv_papers(
    keywords: List[Union[str, List[str]]],
    output_filepath: str,
    fields: List = ["title", "authors", "date", "abstract", "journal", "doi"],
    *args,
    **kwargs
):
    """
    Combines get_arxiv_papers and dump_papers.

    Args:
        keywords (List[str, List[str]]): List of keywords to request arxiv API.
            The outer list level will be considered as AND separated keys, the
            inner level as OR separated.
        filepath (str): Path where the dump will be saved.
        fields (List, optional): List of strings with fields to keep in output.
            Defaults to ['title', 'authors', 'date', 'abstract',
            'journal', 'doi'].
        *args, **kwargs are additional arguments for `get_arxiv_papers`.
    """
    # Translate keywords into query.
    query = get_query_from_keywords(keywords)
    papers = get_arxiv_papers(query, fields, *args, **kwargs)
    dump_papers(papers, output_filepath)
