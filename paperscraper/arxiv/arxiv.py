import glob
import logging
import os
import sys
from typing import Dict, List, Literal, Union

import arxiv
import pandas as pd
import pkg_resources
from tqdm import tqdm

from ..utils import dump_papers
from ..xrxiv.xrxiv_query import XRXivQuery
from .utils import get_query_from_keywords, infer_backend

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

dump_root = pkg_resources.resource_filename("paperscraper", "server_dumps")

global ARXIV_QUERIER
ARXIV_QUERIER = None


def search_local_arxiv():
    global ARXIV_QUERIER
    if ARXIV_QUERIER is not None:
        return
    dump_paths = glob.glob(os.path.join(dump_root, "arxiv*"))

    if len(dump_paths) > 0:
        path = sorted(dump_paths, reverse=True)[0]
        querier = XRXivQuery(path)
        if not querier.errored:
            ARXIV_QUERIER = querier.search_keywords
            logger.info(f"Loaded arxiv dump with {len(querier.df)} entries")


arxiv_field_mapper = {
    "published": "date",
    "journal_ref": "journal",
    "summary": "abstract",
    "entry_id": "doi",
}

# Authors, date, and journal fields need specific processing
process_fields = {
    "authors": lambda authors: ", ".join([a.name for a in authors]),
    "date": lambda date: date.strftime("%Y-%m-%d"),
    "journal": lambda j: j if j is not None else "",
    "doi": lambda entry_id: f"10.48550/arXiv.{entry_id.split('/')[-1].split('v')[0]}",
}


def get_arxiv_papers_local(
    keywords: List[Union[str, List[str]]],
    fields: List[str] = None,
    output_filepath: str = None,
) -> pd.DataFrame:
    """
    Search for papers in the dump using keywords.

    Args:
        keywords: Items will be AND separated. If items
            are lists themselves, they will be OR separated.
        fields: fields to be used in the query search.
            Defaults to None, a.k.a. search in all fields excluding date.
        output_filepath: optional output filepath where to store the hits in JSONL format.
            Defaults to None, a.k.a., no export to a file.

    Returns:
        pd.DataFrame: A dataframe with one paper per row.
    """
    search_local_arxiv()
    if ARXIV_QUERIER is None:
        raise ValueError(
            "Could not find local arxiv dump. Use `backend=api` or download dump via `paperscraper.get_dumps.arxiv"
        )
    return ARXIV_QUERIER(
        keywords=keywords, fields=fields, output_filepath=output_filepath
    )


def get_arxiv_papers_api(
    query: str,
    fields: List = ["title", "authors", "date", "abstract", "journal", "doi"],
    max_results: int = 99999,
    client_options: Dict = {"num_retries": 10},
    search_options: Dict = dict(),
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Performs arxiv API request of a given query and returns list of papers with
    fields as desired.

    Args:
        query: Query to arxiv API. Needs to match the arxiv API notation.
        fields: List of strings with fields to keep in output.
        max_results: Maximal number of results, defaults to 99999.
        client_options: Optional arguments for `arxiv.Client`. E.g.:
            page_size (int), delay_seconds (int), num_retries (int).
            NOTE: Decreasing 'num_retries' will speed up processing but might
            result in more frequent 'UnexpectedEmptyPageErrors'.
        search_options: Optional arguments for `arxiv.Search`. E.g.:
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
                if arxiv_field_mapper.get(key, key) in fields and key != "doi"
            }
            for paper in tqdm(results, desc=f"Processing {query}", disable=not verbose)
        ]
    )
    return processed


def get_and_dump_arxiv_papers(
    keywords: List[Union[str, List[str]]],
    output_filepath: str,
    fields: List = ["title", "authors", "date", "abstract", "journal", "doi"],
    start_date: str = "None",
    end_date: str = "None",
    backend: Literal["api", "local", "infer"] = "api",
    *args,
    **kwargs,
):
    """
    Combines get_arxiv_papers and dump_papers.

    Args:
        keywords: List of keywords for arxiv search.
            The outer list level will be considered as AND separated keys, the
            inner level as OR separated.
        output_filepath: Path where the dump will be saved.
        fields: List of strings with fields to keep in output.
            Defaults to ['title', 'authors', 'date', 'abstract',
            'journal', 'doi'].
        start_date: Start date for the search. Needs to be in format:
            YYYY/MM/DD, e.g. '2020/07/20'. Defaults to 'None', i.e. no specific
            dates are used.
        end_date: End date for the search. Same notation as start_date.
        backend: If `api`, the arXiv API is queried. If `local` the local arXiv dump
            is queried (has to be downloaded before). If `infer` the local dump will
            be used if exists, otherwise API will be queried. Defaults to `api`
            since it is faster.
        *args, **kwargs are additional arguments for `get_arxiv_papers`.
    """
    # Translate keywords into query.
    query = get_query_from_keywords(keywords, start_date=start_date, end_date=end_date)

    if backend not in {"api", "local", "infer"}:
        raise ValueError(
            f"Invalid backend: {backend}. Must be one of ['api', 'local', 'infer']"
        )
    elif backend == "infer":
        backend = infer_backend()

    if backend == "api":
        papers = get_arxiv_papers_api(query, fields, *args, **kwargs)
    elif backend == "local":
        papers = get_arxiv_papers_local(keywords, fields, *args, **kwargs)
    dump_papers(papers, output_filepath)
