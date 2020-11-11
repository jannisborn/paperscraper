import glob
import logging
import os
import sys

import pkg_resources

from paperscraper.arxiv import get_and_dump_arxiv_papers
from paperscraper.pubmed import get_and_dump_pubmed_papers
from paperscraper.xrxiv.xrxiv_query import XRXivQuery

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set up the query dictionary
QUERY_FN_DICT = {
    'arxiv': get_and_dump_arxiv_papers,
    'pubmed': get_and_dump_pubmed_papers,
}
# For biorxiv, chemrxiv and medrxiv search for local dumps
dump_root = pkg_resources.resource_filename('paperscraper', 'server_dumps')

for db in ['biorxiv', 'chemrxiv', 'medrxiv']:
    dump_paths = glob.glob(os.path.join(dump_root, db + '*'))
    if not dump_paths:
        logger.warning(f' No dump found for {db}. Skipping entry.')
        continue
    elif len(dump_paths) > 1:
        logger.info(f' Multiple dumps found for {db}, taking most recent one')
    path = sorted(dump_paths, reverse=True)[0]
    querier = XRXivQuery(path)
    QUERY_FN_DICT.update({db: querier.search_keywords})

if len(QUERY_FN_DICT) == 2:
    logger.warning(
        ' No dumps found for either of biorxiv, medrxiv and chemrxiv.'
        ' Consider using paperscraper.get_dumps.* to fetch the dumps.'
    )
