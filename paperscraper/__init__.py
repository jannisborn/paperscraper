"""Initialize the module."""
__name__ = 'paperscraper'
__version__ = '0.0.1'

import logging
import os
import sys
from typing import List, Union

from .load_dumps import QUERY_FN_DICT
from .utils import get_filename_from_query

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def dump_queries(keywords: List[List[Union[str, List[str]]]], dump_root: str) -> None:
    """Performs keyword search on all available servers and dump the results.

    Args:
        keywords (list): List of lists of keywords.
        dump_root (str): Path to root for dumping.
    """

    for idx, keyword in enumerate(keywords):
        for db, f in QUERY_FN_DICT.items():

            logger.info(f' Keyword {idx+1}/{len(keywords)}, DB: {db}')
            filename = get_filename_from_query(keyword)
            f(keyword, output_filepath=os.path.join(dump_root, db, filename))
