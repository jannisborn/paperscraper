import json
import logging
import sys
from typing import Dict, List

import pandas as pd

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def dump_papers(papers: pd.DataFrame, filepath: str) -> None:
    """
    Receives a pd.DataFrame, one paper per row and dumps it into a .jsonl
    file with one paper per line.

    Args:
        papers (pd.DataFrame): A dataframe of paper metadata, one paper per row.
        filepath (str): Path to dump the papers, has to end with `.jsonl`.
    """
    if not isinstance(filepath, str):
        raise TypeError(f"filepath must be a string, not {type(filepath)}")
    if not filepath.endswith(".jsonl"):
        raise ValueError("Please provide a filepath with .jsonl extension")

    if isinstance(papers, List) and all([isinstance(p, Dict) for p in papers]):
        papers = pd.DataFrame(papers)
        logger.warning(
            "Preferably pass a pd.DataFrame, not a list of dictionaries. "
            "Passing a list is a legacy functionality that might become deprecated."
        )

    if not isinstance(papers, pd.DataFrame):
        raise TypeError(f"papers must be a pd.DataFrame, not {type(papers)}")

    paper_list = list(papers.T.to_dict().values())

    with open(filepath, "w") as f:
        for paper in paper_list:
            f.write(json.dumps(paper) + "\n")


def get_filename_from_query(query: List[str]) -> str:
    """Convert a keyword query into filenames to dump the paper.

    Args:
        query (list): List of string with keywords.

    Returns:
        str: Filename.
    """
    filename = "_".join([k if isinstance(k, str) else k[0] for k in query]) + ".jsonl"
    filename = filename.replace(" ", "").lower()
    return filename


def load_jsonl(filepath: str) -> List[Dict[str, str]]:
    """
    Load data from a `.jsonl` file, i.e., a file with one dictionary per line.

    Args:
        filepath (str): Path to `.jsonl` file.

    Returns:
        List[Dict[str, str]]: A list of dictionaries, one per paper.
    """

    with open(filepath, "r") as f:
        data = [json.loads(line) for line in f.readlines()]
    return data
