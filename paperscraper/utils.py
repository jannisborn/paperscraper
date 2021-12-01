import json
from typing import Dict, List


def dump_papers(papers: List[dict], filepath: str) -> None:
    """
    Receives a list of dicts, one dict per paper and dumps it into a .jsonl
    file with one paper per line.

    Args:
        papers (list[dict]): List of papers
        filepath (str): Path to dump the papers.
    """

    with open(filepath, "w") as f:
        for paper in papers:
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
    Load data from a `.jsonl` file, i.e., a file with one dictionary per line

    Args:
        filepath (str): Path to `.jsonl` file.

    Returns:
        List[Dict[str, str]]: A list of dictionaries, one per paper.
    """

    with open(filepath, "r") as f:
        data = [json.loads(line) for line in f.readlines()]
    return data
