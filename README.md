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

```console
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

## Examples

`paperscraper` is build on top of the packages [pymed](https://pypi.org/project/pymed/),
[arxiv](https://pypi.org/project/arxiv/) and ['scholarly'](https://pypi.org/project/scholarly/). 

### Publication keyword search

Consider you want to perform a publication keyword search with the query:
`COVID-19` **AND** `Artificial Intelligence` **AND** `Medical Imaging`. 

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

You can also use `dump_queries` to iterate over a bunch of queries for all available databases.

```py
from paperscraper import dump_queries

queries = [[covid19, ai, mi], [covid19, ai], [ai]]
dump_queuries(queries os.path.join('paperscraper', 'keyword_dumps'))
```

* Scrape papers from Google Scholar:

Thanks to [scholarly](https://pypi.org/project/scholarly/), there is an endpoint for Google Scholar too.
It does not understand Boolean expressions like the others, but should be used just like
the [Google Scholar search fields](https://scholar.google.com).

```py
from paperscraper.scholar import get_and_dump_scholar_papers
topic = 'Machine Learning'
get_and_dump_scholar_papers(topic)
```

### Citation search

A plus of the Scholar endpoint is that the number of citations of a paper can be fetched:

```py
from paperscraper.scholar import get_citations_from_title
title = 'Über formal unentscheidbare Sätze der Principia Mathematica und verwandter Systeme I.'
get_citations_from_title(title)
```

*NOTE*: The scholar endpoint does not require authentification but since it regularly
prompts with captchas, it's difficult to apply large scale.

### Plotting

When multiple query searches are performed, two types of plots can be generated
automatically: Venn diagrams and bar plots.

#### Venn Diagrams

```py
from paperscraper.plotting import (
    plot_venn_two, plot_venn_three, plot_multiple_venn
)

sizes_2020 = (30842, 14474, 2292, 35476, 1904, 1408, 376)
sizes_2019 = (55402, 11899, 2563)
labels_2020 = ('Medical\nImaging', 'Artificial\nIntelligence', 'COVID-19')
labels_2019 = ['Medical Imaging', 'Artificial\nIntelligence']

plot_venn_two(sizes_2019, labels_2019, title='2019', figname='ai_imaging')
```

![2019](https://github.com/PhosphorylatedRabbits/paperscraper/raw/master/assets/ai_imaging.pdf)


```py
plot_venn_three(
    sizes_2020, labels_2020, title='2020', figname='ai_imaging_covid'
)
```

![2020](https://github.com/PhosphorylatedRabbits/paperscraper/raw/master/assets/ai_imaging_covid.pdf)

Or plot both together:

```py
plot_multiple_venn(
    [sizes_2019, sizes_2020], [labels_2019, labels_2020], 
    titles=['2019', '2020'], suptitle='Keyword search comparison', 
    gridspec_kw={'width_ratios': [1, 2]}, figsize=(10, 6),
    figname='both'
)
```

![both](https://github.com/PhosphorylatedRabbits/paperscraper/raw/master/assets/both.pdf)

#### Barplots

Compare the temporal evolution of different queries across different servers.

```py
from paperscraper import QUERY_FN_DICT
from paperscraper.postprocessing import aggregate_paper
from paperscraper.utils import get_filename_from_query

# Define search terms and their synonyms
ml = ['Deep learning', 'Neural Network', 'Machine learning']
mol = ['molecule', 'molecular', 'drug', 'ligand', 'compound']
gnn = ['gcn', 'gnn', 'graph neural', 'graph convolutional', 'molecular graph']
smiles = ['SMILES', 'Simplified molecular']
fp = ['fingerprint', 'molecular fingerprint', 'fingerprints']

# Define queries
queries = [[ml, mol, smiles], [ml, mol, fp], [ml, mol, gnn]]

data_dict = dict()
for query in queries:
    filename = get_filename_from_query(query)
    data_dict[filename] = dict()
    for db,_ in QUERY_FN_DICT.items():
        # Assuming the keyword search has been performed already
        with open(os.path.join(root, db, filename), 'r') as f:
            data = f.readlines()

        # Unstructured matches are aggregated into 6 bins, 1 per year
        # from 2015 to 2020. Sanity check is performed by having 
        # `filtering=True`, removing papers that don't contain all of
        # the keywords in query.
        data_dict[filename][db], filtered = aggregate_paper(
            data, 2015, bins_per_year=1, filtering=True,
            filter_keys=query, return_filtered=True
        )

# Plotting is now very simple
from paperscraper.plotting import plot_comparison

data_keys = [
    'deeplearning_molecule_fingerprint.jsonl',
    'deeplearning_molecule_smiles.jsonl', 
    'deeplearning_molecule_gcn.jsonl'
]
plot_comparison(
    data_dict,
    data_keys,
    title_text="'Deep Learning' AND 'Molecule' AND X",
    keyword_text=['Fingerprint', 'SMILES', 'Graph'],
    figname='mol_representation'
)
```

![molreps](https://github.com/PhosphorylatedRabbits/paperscraper/raw/master/assets/molreps.pdf)
