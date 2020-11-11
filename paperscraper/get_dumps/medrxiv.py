"""Dump medrxiv data in JSONL format."""
import json
import os
from datetime import datetime

import pkg_resources
from paperscraper.xrxiv.xrxiv_api import MedRxivApi
from tqdm import tqdm

today = datetime.today().strftime('%Y-%m-%d')
save_folder = pkg_resources.resource_filename('paperscraper', 'server_dumps')
save_path = os.path.join(save_folder, f'medrxiv_{today}.jsonl')


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
