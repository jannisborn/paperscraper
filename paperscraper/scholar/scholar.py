import logging
import re
import sys
from typing import List, Literal, Optional

import pandas as pd
from scholarly import scholarly

from ..searchapi.core import (
    SEARCH_API_KEY,
    SearchAPICitations,
    SearchAPIClient,
    SearchAPIScholar,
)
from ..utils import _resolve_backend, dump_papers

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


scholar_field_mapper = {
    "venue": "journal",
    "author": "authors",
    "cites": "citations",
    "pub_year": "year",
}
process_fields = {"year": lambda x: int(x) if x.isdigit() else -1, "citations": int}


def get_scholar_papers(
    title: str,
    fields: List = ["title", "authors", "year", "abstract", "journal", "citations"],
    backend: Literal["auto", "scholarly", "searchapi"] = "auto",
    *,
    api_key: Optional[str] = None,
    search_api_kwargs: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Performs Google Scholar API request of a given title and returns list of papers with
    fields as desired.

    Args:
        title: Google Scholar search query.
        fields: List of strings with fields to keep in output.
        backend: Scholar backend. ``auto`` uses SearchApi when configured.
        api_key: Explicit SearchApi key.
        search_api_kwargs: SearchApi-specific keyword arguments.

    Returns:
        pd.DataFrame. One paper per row.

    """
    if not isinstance(title, str):
        raise TypeError(f"Pass str not {type(title)}")

    if re.search(r"\b(?:AND|OR)\b", title):
        logger.info(
            "NOTE: Scholar API cannot be used with Boolean logic in keywords."
            " Query should be a single string to be entered in the Scholar search field."
        )

    resolved_backend = _resolve_backend(
        backend, api_key, (("searchapi", SEARCH_API_KEY),), "scholarly"
    )
    if resolved_backend == "searchapi":
        return get_scholar_papers_searchapi(
            title,
            fields,
            api_key,
            search_api_kwargs=search_api_kwargs,
        )
    if resolved_backend != "scholarly":
        raise ValueError(f"Unknown backend: {backend}")
    if api_key is not None:
        raise ValueError("api_key is not supported by backend='scholarly'")

    matches = scholarly.search_pubs(title)

    processed = []
    for paper in matches:
        # Extracts title, author, year, journal, abstract
        entry = {
            scholar_field_mapper.get(key, key): process_fields.get(
                scholar_field_mapper.get(key, key), lambda x: x
            )(value)
            for key, value in paper["bib"].items()
            if scholar_field_mapper.get(key, key) in fields
        }

        entry["citations"] = paper["num_citations"]
        processed.append(entry)

    return pd.DataFrame(processed)


def get_scholar_papers_searchapi(
    title: str,
    fields: List = ["title", "authors", "year", "abstract", "journal", "citations"],
    api_key: Optional[str] = None,
    search_api_kwargs: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Retrieve Google Scholar paper metadata through SearchApi.

    Args:
        title: Google Scholar search query.
        fields: List of strings with fields to keep in output.
        api_key: Explicit SearchApi key.
        search_api_kwargs: Supports ``top_k``, ``num_enrich`` and
            ``max_author_requests``.

    Returns:
        pd.DataFrame. One paper per row.
    """
    return SearchAPIScholar(SearchAPIClient(api_key)).get_papers(
        title, fields, search_api_kwargs=search_api_kwargs
    )


def get_scholar_author_papers(
    author: str,
    max_results: int = 30,
    *,
    author_id: Optional[str] = None,
    api_key: Optional[str] = None,
    full_info: bool = False,
) -> pd.DataFrame:
    """Return papers by a researcher from Google Scholar through SearchApi.

    An exact Google Scholar profile is preferred. If none exists, results from
    an ``author:\"name\"`` Scholar query are returned and may mix namesakes.
    The default limit is 30 papers; explicit integer limits are respected.
    ``full_info=True`` requires a profile and consumes one extra SearchApi
    request per paper.

    Args:
        author: Researcher name.
        max_results: Maximum papers to return. Defaults to 30.
        author_id: Optional Google Scholar author ID for exact identification.
        api_key: Explicit SearchApi key.
        full_info: Add journal, date, volume, issue, pages, publisher, and
            description from each paper's citation detail.

    Returns:
        pd.DataFrame. One paper per row.
    """
    return SearchAPIScholar(SearchAPIClient(api_key)).get_author_papers(
        author, max_results, author_id=author_id, full_info=full_info
    )


def get_searchapi_scholar_citation(
    paper: dict,
    api_key: Optional[str] = None,
    search_api_kwargs: Optional[dict] = None,
) -> dict:
    """
    Retrieve citation details for a SearchApi Scholar result when available.

    Args:
        paper: SearchApi ``google_scholar`` organic result.
        api_key: Explicit SearchApi key.
        search_api_kwargs: Supports ``max_author_requests``.

    Returns:
        SearchApi ``google_scholar_author`` citation dict. Common entries are
        ``title``, ``link``, ``resources``, ``description``, ``authors``,
        ``publication_date``, ``journal``, ``volume``, ``issue``, ``pages``,
        ``publisher``, ``cited_by``, ``cites_histogram``, and
        ``scholar_articles``. Returns an empty dict if no exact title match is found.
    """
    return SearchAPICitations(SearchAPIClient(api_key)).get_citation_details(
        paper, search_api_kwargs
    )


def get_and_dump_scholar_papers(
    title: str,
    output_filepath: str,
    fields: List = ["title", "authors", "year", "abstract", "journal", "citations"],
    backend: Literal["auto", "scholarly", "searchapi"] = "auto",
    *,
    api_key: Optional[str] = None,
    search_api_kwargs: Optional[dict] = None,
) -> None:
    """
    Combines get_scholar_papers and dump_papers.

    Args:
        title: Paper to search for on Google Scholar.
        output_filepath: Path where the dump will be saved.
        fields: List of strings with fields to keep in output.
        backend: Scholar backend.
        api_key: Explicit SearchApi key.
        search_api_kwargs: SearchApi-specific keyword arguments.
    """
    papers = get_scholar_papers(
        title,
        fields,
        backend,
        api_key=api_key,
        search_api_kwargs=search_api_kwargs,
    )
    dump_papers(papers, output_filepath)
