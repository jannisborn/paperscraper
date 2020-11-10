"""Initialize the module."""
__name__ = 'paperscraper'
__version__ = '0.1'

import logging
import os
import sys

from .load_dumps import QUERY_FN_DICT
from .utils import get_filename_from_query

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def dump_queries(keywords, dump_root):
    """Performs keyword search on all 4 servers and dumps the results.

    Args:
        keywords (list): List of lists of keywords.
        dump_root (str): Path to root for dumping.
    """

    for idx, keyword in enumerate(keywords):
        for db, f in QUERY_FN_DICT.items():

            logger.info(f' Keyword {idx+1}/{len(keywords)}, DB: {db}')
            filename = get_filename_from_query(keyword)
            f(keyword, output_filepath=os.path.join(dump_root, db, filename))
