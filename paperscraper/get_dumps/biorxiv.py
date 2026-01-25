"""Dump bioRxiv data in JSONL format."""

import json
import os
from datetime import datetime
from typing import Optional

from tqdm import tqdm

from ..utils import get_server_dumps_dir
from ..xrxiv.xrxiv_api import BioRxivApi

today = datetime.today().strftime("%Y-%m-%d")
save_path = os.path.join(
    get_server_dumps_dir(),
    f"biorxiv_{today}.jsonl",
)


def biorxiv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: str = save_path,
    max_retries: int = 10,
):
    """Fetches papers from biorxiv based on time range, i.e., start_date and end_date.
    If the start_date and end_date are not provided, papers will be fetched from biorxiv
    from the launch date of biorxiv until the current date. The fetched papers will be
    stored in jsonl format in save_path.

    Args:
        start_date (str, optional): begin date expressed as YYYY-MM-DD.
            Defaults to None, i.e., earliest possible.
        end_date (str, optional): end date expressed as YYYY-MM-DD.
            Defaults to None, i.e., today.
        save_path (str, optional): Path where the dump is stored.
            Defaults to save_path.
        max_retries (int, optional): Number of retries when API shows connection issues.
            Defaults to 10.
    """
    # create API client
    api = BioRxivApi(max_retries=max_retries)

    # dump all papers
    with open(save_path, "w") as fp:
        for index, paper in enumerate(
            tqdm(api.get_papers(start_date=start_date, end_date=end_date))
        ):
            if index > 0:
                fp.write(os.linesep)
            fp.write(json.dumps(paper))
