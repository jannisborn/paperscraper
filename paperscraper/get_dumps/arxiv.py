"""Dump arxiv data in JSONL format."""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

import pkg_resources
from tqdm import tqdm

from ..arxiv import get_arxiv_papers_api

today = datetime.today().strftime("%Y-%m-%d")
save_folder = pkg_resources.resource_filename("paperscraper", "server_dumps")
save_path = os.path.join(save_folder, f"arxiv_{today}.jsonl")


def arxiv(
    begin_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: str = save_path,
):
    """
    Fetches papers from arXiv based on time range, i.e., begin_date and end_date.
    If the begin_date and end_date are not provided, fetches papers from the earliest
    possible date to the current date. The fetched papers are stored in JSONL format.

    Args:
        begin_date (str, optional): Start date in format YYYY-MM-DD. Defaults to None.
        end_date (str, optional): End date in format YYYY-MM-DD. Defaults to None.
        save_path (str, optional): Path to save the JSONL dump. Defaults to save_path.
    """
    # Set default dates
    EARLIEST_START = "1991-01-01"
    if begin_date is None:
        begin_date = EARLIEST_START
    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")

    # Convert dates to datetime objects
    start_date = datetime.strptime(begin_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    if start_date > end_date:
        raise ValueError(
            f"begin_date {begin_date} cannot be later than end_date {end_date}"
        )

    # Open file for writing results
    with open(save_path, "w") as fp:
        progress_bar = tqdm(total=(end_date - start_date).days + 1)

        current_date = start_date
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            progress_bar.set_description(
                f"Fetching {current_date.strftime('%Y-%m-%d')}"
            )

            # Format dates for query
            query = f"submittedDate:[{current_date.strftime('%Y%m%d0000')} TO {next_date.strftime('%Y%m%d0000')}]"
            try:
                papers = get_arxiv_papers_api(
                    query=query,
                    fields=["title", "authors", "date", "abstract", "journal", "doi"],
                    verbose=False,
                )
                if not papers.empty:
                    for paper in papers.to_dict(orient="records"):
                        fp.write(json.dumps(paper) + "\n")
            except Exception as e:
                print(f"Arxiv scraping error: {current_date.strftime('%Y-%m-%d')}: {e}")
            current_date = next_date
            progress_bar.update(1)
