import datetime
from typing import List, Union

from pymed import PubMed

from paperscraper.pubmed.utils import get_query_from_keywords_and_date
from paperscraper.utils import dump_papers

PUBMED = PubMed(tool="MyTool", email="abc@def.gh")

pubmed_field_mapper = {'publication_date': 'date'}

# Authors fields needs specific processing
process_fields = {
    'authors': lambda authors: list(
        map(
            lambda a: str(a.get('firstname', '')) + '' + str(a.get('lastname', '')),
            authors,
        )
    ),
    'date': lambda date: (
        date.strftime('%Y-%m-%d') if isinstance(date, datetime.date) else date
    ),
}


def get_pubmed_papers(
    query: str,
    fields: List = ['title', 'authors', 'date', 'abstract', 'journal', 'doi'],
    max_results: int = 999999,
    *args,
    **kwargs
):
    """
    Performs PubMed API request of a query and returns list of papers with
    fields as desired.

    Args:
        query (str): Query to PubMed API. Needs to match PubMed API notation.
        fields (list[str]): List of strings with fields to keep in output.
        max_results (int): Maximal number of results retrieved from DB.
        NOTE: *args, **kwargs are additional arguments for pubmed.query

    Returns:
        list of dicts. One dict per paper.

    """
    raw = list(PUBMED.query(query, max_results=max_results, *args, **kwargs))

    processed = [
        {
            pubmed_field_mapper.get(key, key): process_fields.get(
                pubmed_field_mapper.get(key, key), lambda x: x
            )(value)
            for key, value in paper.toDict().items()
            if pubmed_field_mapper.get(key, key) in fields
        }
        for paper in raw
    ]

    return processed


def get_and_dump_pubmed_papers(
    keywords: List[Union[str, List[str]]],
    output_filepath: str,
    fields: List = ['title', 'authors', 'date', 'abstract', 'journal', 'doi'],
    start_date: str = 'None',
    end_date: str = 'None',
    *args,
    **kwargs
):
    """
    Combines get_pubmed_papers and dump_papers.

    Args:
        keywords (List[Union[str, List[str]]]): List of keywords to request
            pubmed API. The outer list level will be considered as AND
            separated keys, the inner level as OR separated.
        filepath (str): Path where the dump will be saved.
        fields (List, optional): List of strings with fields to keep in output.
            Defaults to ['title', 'authors', 'date', 'abstract',
            'journal', 'doi'].
        start_date (str): Start date for the search. Needs to be in format:
            YYYY/MM/DD, e.g. '2020/07/20'. Defaults to 'None', i.e. no specific
            dates are used.
        end_date (str): End date for the search. Same notation as start_date.
    """
    # Translate keywords into query.
    query = get_query_from_keywords_and_date(
        keywords, start_date=start_date, end_date=end_date
    )
    papers = get_pubmed_papers(query, fields, *args, **kwargs)
    dump_papers(papers, output_filepath)
