[![Build Status](https://travis-ci.com/PhosphorylatedRabbits/paperscraper.svg?branch=master)](https://travis-ci.com/PhosphorylatedRabbits/paperscraper)
[![License:
MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/paperscraper.svg)](https://badge.fury.io/py/paperscraper)

# paperscraper

## Overview

`paperscraper` is a `python` package that ships via `pypi` and facilitates scraping
publication metadata from PubMed or from preprint servers such as arXiv, medRxiv,
bioRxiv or chemRiv. It provides a streamlined interface to scrape metadata and comes
with simple postprocessing functions and plotting routines for meta-analysis.


## Getting started 

```sh
pip install paperscraper
```
This is enough to query PubMed, arXiv or Google Scholar. 

#### Download X-rxiv Dumps
However, to scrape publication data from the preprint servers [biorxiv](https://www.biorxiv.org), [medrxiv](https://www.medrxiv.org) or [chemrxiv](https://chemrxiv.org), the setup is different. The entire dump is downloaded and stored in the `server_dumps` folder in a `.jsonl` format (one paper per line). 
```py
from paperscraper.get_dumps import chemrxiv, biorxiv, medrxiv
chemrxiv()  # Takes ~1h and should result in ~10 MB file
medrxiv()  # Takes ~30min and should result in ~35 MB file
biorxiv()  # Takes ~2.5h and should result in ~250 MB file
```
*NOTE*: For `chemrxiv` you need to create an access token in your account on [figshare.com](https://figshare.com/account/applications). Either pass the token to as keyword argument (`chemrxiv(token=your_token)`) or save it under `~/.config/figshare/chemrxiv.txt`.

### Examples
`paperscraper` is build on top of the packages [pymed](https://pypi.org/project/pymed/),
[arxiv](https://pypi.org/project/arxiv/) and ['scholarly'](https://pypi.org/project/scholarly/). 

Consider you want to perform a publication keyword search with the query `COVID-19` AND `Artificial Intelligence` AND `Medical Imaging`. 

* Scrape papers from PubMed: 
```py
from paperscraper.pubmed import get_and_dump_pubmed_papers
covid19 = ['COVID-19', 'SARS-CoV-2']
ai = ['Artificial intelligence', 'Deep learning', 'Machine learning']
mi = ['Medical imaging']
query = [covid19, ai, mi]

get_and_dump_pubmed_papers(query, output_filepath='covid19_ai_imaging.jsonl')
```
* Scrape papers from arXiv: 
```py
from paperscraper.pubmed import get_and_dump_arxiv_papers

get_and_dump_arxiv_papers(query, output_filepath='covid19_ai_imaging.jsonl')
```

* Scrape papers from bioRiv, medRxiv or chemRxiv:
```py
from paperscraper.xrxiv.xrxiv_query import XRXivQuery

querier = XRXivQuery('server_dumps/chemrxiv_2020-11-10.jsonl')
querier.search_keywords(query, output_filepath='covid19_ai_imaging.jsonl')
```

You can also use the `QUERY_FN_DICT` to iterate over all databases in one pass:
```py
from paperscraper import QUERY_FN_DICT

for db,f in QUERY_FN_DICT.items():
    print(f'Database = {db}')
    f(query, output_filepath=os.path.join(root, db, 'covid19_ai_imaging.jsonl')))


* Scrape papers from Google Scholar: 

- use exe_dict
- aggregate data
- plot results



### Citation
(Coming soon.)
