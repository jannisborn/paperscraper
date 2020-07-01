from typing import List


def dump_papers(papers: List[dict], filepath: str) -> None:
    """
    Receives a list of dicts, one dict per paper and dumps it into a .jsonl
    file with one paper per line.

    Args:
        - papers (list[dict]): List of papers
        - filepath (str): Path to dump the papers.
    """

    with open(filepath, 'w') as f:
        for paper in papers:
            f.write(str(paper) + '\n')
