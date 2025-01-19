import glob
import os
from datetime import datetime
from typing import List, Union

import pkg_resources

finalize_disjunction = lambda x: "(" + x[:-4] + ") AND "
finalize_conjunction = lambda x: x[:-5]

EARLIEST_START = "1970-01-01"


def format_date(date_str: str) -> str:
    """Converts a date in YYYY-MM-DD format to arXiv's YYYYMMDDTTTT format."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.strftime("%Y%m%d0000")


def get_query_from_keywords(
    keywords: List[Union[str, List[str]]],
    start_date: str = "None",
    end_date: str = "None",
) -> str:
    """Receives a list of keywords and returns the query for the arxiv API.

    Args:
        keywords (List[str, List[str]]): Items will be AND separated. If items
            are lists themselves, they will be OR separated.
        start_date (str): Start date for the search. Needs to be in format:
            YYYY-MM-DD, e.g. '2020-07-20'. Defaults to 'None', i.e. no specific
            dates are used.
        end_date (str): End date for the search. Same notation as start_date.

    Returns:
        str: query to enter to arxiv API.
    """

    query = ""
    for i, key in enumerate(keywords):
        if isinstance(key, str):
            query += f"all:{key} AND "
        elif isinstance(key, list):
            inter = "".join([f"all:{syn} OR " for syn in key])
            query += finalize_disjunction(inter)

    query = finalize_conjunction(query)
    if start_date == "None" and end_date == "None":
        return query
    elif start_date == "None":
        start_date = EARLIEST_START
    elif end_date == "None":
        end_date = datetime.now().strftime("%Y-%m-%d")

    start = format_date(start_date)
    end = format_date(end_date)
    date_filter = f" AND submittedDate:[{start} TO {end}]"
    return query + date_filter


def infer_backend():
    dump_root = pkg_resources.resource_filename("paperscraper", "server_dumps")
    dump_paths = glob.glob(os.path.join(dump_root, "arxiv" + "*"))
    return "api" if not dump_paths else "local"
