import datetime
import logging
import os
from typing import List, Union

import pandas as pd
from pymed_paperscraper import PubMed

from ..utils import dump_papers
from .utils import get_emails, get_query_from_keywords_and_date

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PUBMED = PubMed(tool=os.getenv("NCBI_TOOL", "paperscraper"), email="abc@def.gh")

pubmed_field_mapper = {"publication_date": "date"}

# Authors fields needs specific processing
process_fields = {
    "authors": lambda authors: list(
        map(
            lambda a: str(a.get("firstname", "")) + "" + str(a.get("lastname", "")),
            authors,
        )
    ),
    "date": lambda date: (
        date.strftime("%Y-%m-%d") if isinstance(date, datetime.date) else date
    ),
    "doi": lambda doi: doi.split("\n")[0] if isinstance(doi, str) else doi,
}


def get_pubmed_papers(
    query: str,
    fields: List = ["title", "authors", "date", "abstract", "journal", "doi"],
    max_results: int = 9998,
    *args,
    **kwargs,
) -> pd.DataFrame:
    """
    Performs PubMed API request of a query and returns list of papers with
    fields as desired.

    Args:
        query: Query to PubMed API. Needs to match PubMed API notation.
        fields: List of strings with fields to keep in output.
            NOTE: If 'emails' is passed, an attempt is made to extract author mail
            addresses.
        max_results: Maximal number of results retrieved from DB. Defaults
            to 9998, higher values likely raise problems due to PubMedAPI, see:
            https://stackoverflow.com/questions/75353091/biopython-entrez-article-limit
        args: additional arguments for pubmed.query
        kwargs: additional arguments for pubmed.query

    Returns:
        pd.DataFrame. One paper per row.

    """
    if max_results > 9998:
        logger.warning(
            f"\nmax_results cannot be larger than 9998, received {max_results}."
            "This will likely result in a JSONDecodeError. Considering lowering `max_results`.\n"
            "For PubMed, ESearch can only retrieve the first 9,999 records matching the query. "
            "To obtain more than 9,999 PubMed records, consider using EDirect that contains additional"
            "logic to batch PubMed search results automatically so that an arbitrary number can be retrieved"
        )

    try:
        raw = list(PUBMED.query(query, max_results=max_results, *args, **kwargs))
    except (TypeError, ValueError, KeyError) as e:
        logger.warning(
            "PubMed query returned malformed payload; treating as empty. %s", e
        )
        return pd.DataFrame(columns=list(fields))

    get_mails = "emails" in fields
    if get_mails:
        fields.pop(fields.index("emails"))

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
    if get_mails:
        for idx, paper in enumerate(raw):
            processed[idx].update({"emails": get_emails(paper)})

    return pd.DataFrame(processed)


def get_and_dump_pubmed_papers(
    keywords: List[Union[str, List[str]]],
    output_filepath: str,
    fields: List = ["title", "authors", "date", "abstract", "journal", "doi"],
    start_date: str = "None",
    end_date: str = "None",
    *args,
    **kwargs,
) -> None:
    """
    Combines get_pubmed_papers and dump_papers.

    Args:
        keywords: List of keywords to request pubmed API.
            The outer list level will be considered as AND separated keys.
            The inner level as OR separated.
        output_filepath: Path where the dump will be saved.
        fields: List of strings with fields to keep in output.
            Defaults to ['title', 'authors', 'date', 'abstract',
            'journal', 'doi'].
            NOTE: If 'emails' is passed, an attempt is made to extract author mail
            addresses.
        start_date: Start date for the search. Needs to be in format:
            YYYY/MM/DD, e.g. '2020/07/20'. Defaults to 'None', i.e. no specific
            dates are used.
        end_date: End date for the search. Same notation as start_date.
    """
    # Translate keywords into query.
    query = get_query_from_keywords_and_date(
        keywords, start_date=start_date, end_date=end_date
    )
    papers = get_pubmed_papers(query, fields, *args, **kwargs)
    dump_papers(papers, output_filepath)
