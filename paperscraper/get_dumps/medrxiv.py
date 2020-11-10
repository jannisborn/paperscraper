"""Dump medrxiv data in JSONL format."""
import json
import os
from datetime import datetime

from paperscraper.xrxiv.xrxiv_api import MedRxivApi
from tqdm import tqdm

HERE = os.path.abspath(os.path.dirname(__file__))
today = datetime.today().strftime('%Y-%m-%d')
save_path = os.path.abspath(
    os.path.join(HERE, '..', '..', 'server_dumps', f'medrxiv_{today}.jsonl')
)


def medrxiv(save_path: str = save_path):
    """Fetches all papers from medrxiv until current date, stores them in jsonl
    format in save_path.

    Args:
        save_path (str, optional): Path where the dump is stored.
            Defaults to save_path.
    """
    # create API client
    api = MedRxivApi()
    # dump all papers
    with open(save_path, 'w') as fp:
        for index, paper in enumerate(tqdm(api.get_papers())):
            if index > 0:
                fp.write(os.linesep)
            fp.write(json.dumps(paper))
