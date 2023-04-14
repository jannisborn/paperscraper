"""Dump bioRxiv data in JSONL format."""
import json
import os
from datetime import datetime
from typing import Optional

import pkg_resources
from tqdm import tqdm

from ..xrxiv.xrxiv_api import BioRxivApi

today = datetime.today().strftime("%Y-%m-%d")
save_path = os.path.join(
    pkg_resources.resource_filename("paperscraper", "server_dumps"),
    f"biorxiv_{today}.jsonl",
)


def biorxiv(
        begin_date: Optional[str] = None,
        end_date: Optional[str] = None,
        save_path: str = save_path):
    """Fetches papers from biorxiv based on time range, i.e., begin_date and end_date. 
    If the begin_date and end_date are not provided, papers will be fetched from biorxiv 
    from the launch date of biorxiv until the current date. The fetched papers will be 
    stored in jsonl format in save_path.

    Args:
        save_path (str, optional): Path where the dump is stored.
            Defaults to save_path.
        begin_date (Optional[str], optional): begin date expressed as YYYY-MM-DD. 
            Defaults to None.
        end_date (Optional[str], optional): end date expressed as YYYY-MM-DD.
            Defaults to None.
    """
    # create API client
    api = BioRxivApi()

    # dump all papers
    with open(save_path, "w") as fp:
        for index, paper in enumerate(tqdm(api.get_papers(begin_date=begin_date, end_date=end_date))):
            if index > 0:
                fp.write(os.linesep)
            fp.write(json.dumps(paper))
