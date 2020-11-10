import logging
import sys
from typing import List

from paperscraper.utils import dump_papers
from scholarly import scholarly

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


scholar_field_mapper = {
    'venue': 'journal',
    'author': 'authors',
    'cites': 'citations',
}
process_fields = {'year': lambda x: int(x) if x.isdigit() else -1, 'citations': int}


def get_scholar_papers(
    title: str,
    fields: List = ['title', 'authors', 'year', 'abstract', 'journal', 'citations'],
    *args,
    **kwargs,
):
    """
    Performs Google Scholar API request of a given query and returns list of papers with
    fields as desired.

    Args:
        query (str): Query to arxiv API. Needs to match the arxiv API notation.
        fields (list[str]): List of strings with fields to keep in output.

    Returns:
        list of dicts. One dict per paper.

    """
    logger.info(
        'NOTE: Scholar API cannot be used with Boolean logic in keywords.'
        'Query should be a single string to be entered in the Scholar search field.'
    )
    if not isinstance(title, str):
        raise TypeError(f'Pass str not {type(title)}')

    matches = scholarly.search_pubs(title)

    processed = [
        {
            scholar_field_mapper.get(key, key): process_fields.get(
                scholar_field_mapper.get(key, key), lambda x: x
            )(value)
            for key, value in paper.bib.items()
            if scholar_field_mapper.get(key, key) in fields
        }
        for paper in matches
    ]
    return processed


def get_and_dump_scholar_papers(
    title: str,
    output_filepath: str,
    fields: List = ['title', 'authors', 'year', 'abstract', 'journal', 'citations'],
):
    """
    Combines get_scholar_papers and dump_papers.

    Args:
        keywords (List[str, List[str]]): List of keywords to request arxiv API.
            The outer list level will be considered as AND separated keys, the
            inner level as OR separated.
        filepath (str): Path where the dump will be saved.
        fields (List, optional): List of strings with fields to keep in output.
            Defaults to ['title', 'authors', 'date', 'abstract',
            'journal', 'doi'].
    """
    papers = get_scholar_papers(title, fields)
    dump_papers(papers, output_filepath)


def get_citations_from_title(title: str) -> int:
    """
    Args:
        title (str): Title of paper to be searched on Scholar.

    Raises:
        TypeError: If sth else than str is passed.

    Returns:
        int: Number of citations of paper.
    """

    if not isinstance(title, str):
        raise TypeError(f'Pass str not {type(title)}')

    matches = scholarly.search_pubs(title)
    counts = list(map(lambda p: int(p.bib['cites']), matches))
    if len(counts) == 0:
        logger.warning(f'Found no match for {title}.')
        return 0
    if len(counts) > 1:
        logger.warning(f'Found {len(counts)} matches for {title}.')
    return counts[0]
