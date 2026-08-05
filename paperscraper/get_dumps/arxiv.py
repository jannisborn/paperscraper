"""Dump arxiv data in JSONL format."""

import json
import os
from datetime import datetime, timedelta
from typing import Literal, Optional

from tqdm import tqdm

from ..arxiv import get_arxiv_papers_api
from ..arxiv.kaggle import arxiv_kaggle
from ..utils import get_server_dumps_dir

today = datetime.today().strftime("%Y-%m-%d")
save_folder = get_server_dumps_dir()
save_path = os.path.join(save_folder, f"arxiv_{today}.jsonl")


def arxiv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: str = save_path,
    backend: Literal["api", "kaggle"] = "kaggle",
    page_size: int = 2000,
    delay_seconds: float = 3.0,
    num_retries: int = 3,
):
    """
    Fetches papers from arXiv based on time range, i.e., start_date and end_date.
    If the start_date and end_date are not provided, fetches papers from the earliest
    possible date to the current date. The fetched papers are stored in JSONL format.

    Args:
        start_date (str, optional): Start date in format YYYY-MM-DD. Defaults to None.
        end_date (str, optional): End date in format YYYY-MM-DD. Defaults to None.
        save_path (str, optional): Path to save the JSONL dump. Defaults to save_path.
        backend: Metadata source. If `api`, use the arxiv package/API. If `kaggle`,
            use the Kaggle arXiv metadata snapshot. Defaults to `kaggle`.
        page_size (int, optional): Number of records requested per API page.
            arXiv allows at most 2000. Defaults to 2000.
        delay_seconds (float, optional): Delay between API requests. arXiv asks for
            at least 3 seconds. Defaults to 3.0.
        num_retries (int, optional): Number of retries per API page. Defaults to 3.
    """
    if backend not in {"api", "kaggle"}:
        raise ValueError("backend must be one of ['api', 'kaggle']")

    # Set default dates
    EARLIEST_START = "1991-01-01"
    if start_date is None:
        start_date = EARLIEST_START
    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")

    # Convert dates to datetime objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    if start_date > end_date:
        raise ValueError(
            f"start_date {start_date} cannot be later than end_date {end_date}"
        )

    if backend == "kaggle":
        return arxiv_kaggle(
            start_date=start_date,
            end_date=end_date,
            save_path=save_path,
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
                    client_options={
                        "page_size": page_size,
                        "delay_seconds": delay_seconds,
                        "num_retries": num_retries,
                    },
                    verbose=False,
                )
                if not papers.empty:
                    for paper in papers.to_dict(orient="records"):
                        fp.write(json.dumps(paper) + "\n")
            except Exception as e:
                print(f"Arxiv scraping error: {current_date.strftime('%Y-%m-%d')}: {e}")
            current_date = next_date
            progress_bar.update(1)
