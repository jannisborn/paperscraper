[![build](https://github.com/jannisborn/paperscraper/actions/workflows/test_tip.yml/badge.svg?branch=main)](https://github.com/jannisborn/paperscraper/actions/workflows/test_tip.yml?query=branch%3Amain)
[![build](https://github.com/jannisborn/paperscraper/actions/workflows/test_pypi.yml/badge.svg?branch=main)](https://github.com/jannisborn/paperscraper/actions/workflows/test_pypi.yml?query=branch%3Amain)
[![License:
MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/paperscraper.svg)](https://badge.fury.io/py/paperscraper)
[![Downloads](https://static.pepy.tech/badge/paperscraper)](https://pepy.tech/project/paperscraper)
[![Downloads](https://static.pepy.tech/badge/paperscraper/month)](https://pepy.tech/project/paperscraper)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![codecov](https://codecov.io/github/jannisborn/paperscraper/branch/main/graph/badge.svg?token=Clwi0pu61a)](https://codecov.io/github/jannisborn/paperscraper)
# paperscraper

`paperscraper` is a `python` package for scraping publication metadata or full text files (PDF or XML) from
**PubMed** or preprint servers such as **arXiv**, **medRxiv**, **bioRxiv** and **chemRxiv**.
It provides a streamlined interface to scrape metadata, allows to retrieve citation counts
from Google Scholar, impact factors from journals and comes with simple postprocessing functions
and plotting routines for meta-analysis.

## Table of Contents

1. [Getting Started](#getting-started)
   - [Download X-rxiv Dumps](#download-x-rxiv-dumps)
   - [Arxiv Local Dump](#arxiv-local-dump)
2. [Examples](#examples)
   - [Publication Keyword Search](#publication-keyword-search)
   - [Full-Text Retrieval (PDFs & XMLs)](#full-text-retrieval-pdfs--xmls)
   - [Citation Search](#citation-search)
   - [Journal Impact Factor](#journal-impact-factor)
3. [Plotting](#plotting)
   - [Barplots](#barplots)
   - [Venn Diagrams](#venn-diagrams)
4. [Citation](#citation)
5. [Contributions](#contributions)

## Getting started

```console
pip install paperscraper
```

This is enough to query **PubMed**, **arXiv** or Google Scholar.

#### Download X-rxiv Dumps

However, to scrape publication data from the preprint servers [biorxiv](https://www.biorxiv.org), [medrxiv](https://www.medrxiv.org) and [chemrxiv](https://www.chemrxiv.org), the setup is different. The entire dump is downloaded and stored in the `server_dumps` folder in a `.jsonl` format (one paper per line).

```py
from paperscraper.get_dumps import biorxiv, medrxiv, chemrxiv
medrxiv()  #  Takes ~30min and should result in ~35 MB file
biorxiv()  # Takes ~1h and should result in ~350 MB file
chemrxiv()  #  Takes ~45min and should result in ~20 MB file
```
*NOTE*: Once the dumps are stored, please make sure to restart the python interpreter so that the changes take effect. 
*NOTE*: If you experience API connection issues (`ConnectionError`), since v0.2.12 there are automatic retries which you can even control and raise from the default of 10, as in `biorxiv(max_retries=20)`.

Since v0.2.5 `paperscraper` also allows to scrape {med/bio/chem}rxiv for specific dates.
```py
medrxiv(start_date="2023-04-01", end_date="2023-04-08")
```
But watch out. The resulting `.jsonl` file will be labelled according to the current date and all your subsequent searches will be based on this file **only**. If you use this option you might want to keep an eye on the source files (`paperscraper/server_dumps/*jsonl`) to ensure they contain the paper metadata for all papers you're interested in.

#### Arxiv local dump
If you prefer local search rather than using the arxiv API:

```py
from paperscraper.get_dumps import arxiv
arxiv(start_date='2024-01-01', end_date=None) # scrapes all metadata from 2024 until today.
```

Afterwards you can search the local arxiv dump just like the other x-rxiv dumps.
The direct endpoint is `paperscraper.arxiv.get_arxiv_papers_local`. You can also specify the
backend directly in the `get_and_dump_arxiv_papers` function:
```py
from paperscraper.arxiv import get_and_dump_arxiv_papers
get_and_dump_arxiv_papers(..., backend='local')
```

## Examples

`paperscraper` is build on top of the packages [arxiv](https://pypi.org/project/arxiv/), [pymed](https://pypi.org/project/pymed-paperscraper/), and [scholarly](https://pypi.org/project/scholarly/). 

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
from paperscraper.arxiv import get_and_dump_arxiv_papers

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
dump_queries(queries, '.')
```

Or use the harmonized interface of `QUERY_FN_DICT` to query multiple databases of your choice:
```py
from paperscraper.load_dumps import QUERY_FN_DICT
print(QUERY_FN_DICT.keys())

QUERY_FN_DICT['biorxiv'](query, output_filepath='biorxiv_covid_ai_imaging.jsonl')
QUERY_FN_DICT['medrxiv'](query, output_filepath='medrxiv_covid_ai_imaging.jsonl')
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
*NOTE*: The scholar endpoint does not require authentication but since it regularly prompts with captchas, it's difficult to apply large scale.

### Full-Text Retrieval (PDFs & XMLs)

`paperscraper` allows you to download full text of publications using DOIs. The basic functionality works reliably for preprint servers (arXiv, bioRxiv, medRxiv, chemRxiv), but retrieving papers from PubMed dumps is more challenging due to publisher restrictions and paywalls.

#### Standard Usage

The main download functions work for all paper types with automatic fallbacks:

```py
from paperscraper.pdf import save_pdf
paper_data = {'doi': "10.48550/arXiv.2207.03928"}
save_pdf(paper_data, filepath='gt4sd_paper.pdf')
```

To batch download full texts from your metadata search results:

```py
from paperscraper.pdf import save_pdf_from_dump

# Save PDFs/XMLs in current folder and name the files by their DOI
save_pdf_from_dump('medrxiv_covid_ai_imaging.jsonl', pdf_path='.', key_to_save='doi')
```

#### Automatic Fallback Mechanisms

When the standard text retrieval fails, `paperscraper` automatically tries these fallbacks:

- **BioC-PMC**: For biomedical papers in [PubMed Central](https://pmc.ncbi.nlm.nih.gov/) (open-access repository), it retrieves open-access full-text XML from the [BioC-PMC API](https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/).
- **eLife Papers**: For [eLife](https://elifesciences.org/) journal papers, it fetches XML files from eLife's open [GitHub repository](https://github.com/elifesciences/elife-article-xml).

These fallbacks are tried automatically without requiring any additional configuration.

#### Enhanced Retrieval with Publisher APIs

For more comprehensive access to papers from major publishers, you can provide API keys for:

- **Wiley TDM API**: Enables access to [Wiley](https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining) publications (2,000+ journals).
- **Elsevier TDM API**: Enables access to [Elsevier](https://www.elsevier.com/about/policies-and-standards/text-and-data-mining) publications (The Lancet, Cell, ...).

To use publisher APIs:

1. Create a file with your API keys:
```
WILEY_TDM_API_TOKEN=your_wiley_token_here
ELSEVIER_TDM_API_KEY=your_elsevier_key_here
```

2. Pass the file path when calling retrieval functions:

```py
from paperscraper.pdf import save_pdf_from_dump

save_pdf_from_dump(
    'pubmed_query_results.jsonl',
    pdf_path='./papers',
    key_to_save='doi',
    api_keys='path/to/your/api_keys.txt'
)
```

For obtaining API keys:
- Wiley TDM API: Visit [Wiley Text and Data Mining](https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining) (free for academic users with institutional subscription)
- Elsevier TDM API: Visit [Elsevier's Text and Data Mining](https://www.elsevier.com/about/policies-and-standards/text-and-data-mining) (free for academic users with institutional subscription)

*NOTE*: While these fallback mechanisms improve retrieval success rates, they cannot guarantee access to all papers due to various access restrictions.


### Citation search

You can fetch the number of citations of a paper from its title or DOI

```py
from paperscraper.citations import get_citations_from_title, get_citations_by_doi
title = 'Über formal unentscheidbare Sätze der Principia Mathematica und verwandter Systeme I.'
print(get_citations_from_title(title))

doi = '10.1021/acs.jcim.3c00132'
get_citations_by_doi(doi)
```

### Journal impact factor

You can also retrieve the impact factor for all journals:
```py
>>>from paperscraper.impact import Impactor
>>>i = Impactor()
>>>i.search("Nat Comms", threshold=85, sort_by='impact') 
[
    {'journal': 'Nature Communications', 'factor': 17.694, 'score': 94}, 
    {'journal': 'Natural Computing', 'factor': 1.504, 'score': 88}
]
```
This performs a fuzzy search with a threshold of 85. `threshold` defaults to 100 in which case an exact search
is performed. You can also search by journal abbreviation, [E-ISSN](https://portal.issn.org) or [NLM ID](https://portal.issn.org).
```py
i.search("Nat Rev Earth Environ") # [{'journal': 'Nature Reviews Earth & Environment', 'factor': 37.214, 'score': 100}]
i.search("101771060") # [{'journal': 'Nature Reviews Earth & Environment', 'factor': 37.214, 'score': 100}]
i.search('2662-138X') # [{'journal': 'Nature Reviews Earth & Environment', 'factor': 37.214, 'score': 100}]

# Filter results by impact factor
i.search("Neural network", threshold=85, min_impact=1.5, max_impact=20)
# [
#   {'journal': 'IEEE Transactions on Neural Networks and Learning Systems', 'factor': 14.255, 'score': 93}, 
#   {'journal': 'NEURAL NETWORKS', 'factor': 9.657, 'score': 91},
#   {'journal': 'WORK-A Journal of Prevention Assessment & Rehabilitation', 'factor': 1.803, 'score': 86}, 
#   {'journal': 'NETWORK-COMPUTATION IN NEURAL SYSTEMS', 'factor': 1.5, 'score': 92}
# ]

# Show all fields
i.search("quantum information", threshold=90, return_all=True)
# [
#   {'factor': 10.758, 'jcr': 'Q1', 'journal_abbr': 'npj Quantum Inf', 'eissn': '2056-6387', 'journal': 'npj Quantum Information', 'nlm_id': '101722857', 'issn': '', 'score': 92},
#   {'factor': 1.577, 'jcr': 'Q3', 'journal_abbr': 'Nation', 'eissn': '0027-8378', 'journal': 'NATION', 'nlm_id': '9877123', 'issn': '0027-8378', 'score': 91}
# ]
```


## Plotting

When multiple query searches are performed, two types of plots can be generated
automatically: Venn diagrams and bar plots.

### Barplots

Compare the temporal evolution of different queries across different servers.

```py
from paperscraper import QUERY_FN_DICT
from paperscraper.postprocessing import aggregate_paper
from paperscraper.utils import get_filename_from_query, load_jsonl

# Define search terms and their synonyms
ml = ['Deep learning', 'Neural Network', 'Machine learning']
mol = ['molecule', 'molecular', 'drug', 'ligand', 'compound']
gnn = ['gcn', 'gnn', 'graph neural', 'graph convolutional', 'molecular graph']
smiles = ['SMILES', 'Simplified molecular']
fp = ['fingerprint', 'molecular fingerprint', 'fingerprints']

# Define queries
queries = [[ml, mol, smiles], [ml, mol, fp], [ml, mol, gnn]]

root = '../keyword_dumps'

data_dict = dict()
for query in queries:
    filename = get_filename_from_query(query)
    data_dict[filename] = dict()
    for db,_ in QUERY_FN_DICT.items():
        # Assuming the keyword search has been performed already
        data = load_jsonl(os.path.join(root, db, filename))

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
    figpath='mol_representation'
)
```

![molreps](https://github.com/jannisborn/paperscraper/blob/main/assets/molreps.png?raw=true "MolReps")


### Venn Diagrams

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

![2019](https://github.com/jannisborn/paperscraper/blob/main/assets/ai_imaging.png?raw=true "2019")


```py
plot_venn_three(
    sizes_2020, labels_2020, title='2020', figname='ai_imaging_covid'
)
```

![2020](https://github.com/jannisborn/paperscraper/blob/main/assets/ai_imaging_covid.png?raw=true "2020")

Or plot both together:

```py
plot_multiple_venn(
    [sizes_2019, sizes_2020], [labels_2019, labels_2020], 
    titles=['2019', '2020'], suptitle='Keyword search comparison', 
    gridspec_kw={'width_ratios': [1, 2]}, figsize=(10, 6),
    figname='both'
)
```

![both](https://github.com/jannisborn/paperscraper/blob/main/assets/both.png?raw=true "Both")



## Citation
If you use `paperscraper`, please cite a paper that motivated our development of this tool.

```bib
@article{born2021trends,
  title={Trends in Deep Learning for Property-driven Drug Design},
  author={Born, Jannis and Manica, Matteo},
  journal={Current Medicinal Chemistry},
  volume={28},
  number={38},
  pages={7862--7886},
  year={2021},
  publisher={Bentham Science Publishers}
}
```

## Contributions
Thanks to the following contributors:
- [@mathinic](https://github.com/mathinic): Since `v0.3.0` improved PubMed full text retrieval with additional fallback mechanisms (BioC-PMC, eLife and optional Wiley/Elsevier APIs).
- [@memray](https://github.com/memray): Since `v0.2.12` there are automatic retries when downloading the {med/bio/chem}rxiv dumps.
- [@achouhan93](https://github.com/achouhan93): Since `v0.2.5` {med/bio/chem}rxiv can be scraped for specific dates!
- [@daenuprobst](https://github.com/daenuprobst): Since  `v0.2.4` PDF files can be scraped directly (`paperscraper.pdf.save_pdf`)
- [@oppih](https://github.com/oppih): Since `v0.2.3` chemRxiv API also provides DOI and URL if available
- [@lukasschwab](https://github.com/lukasschwab): Bumped `arxiv` dependency to >`1.4.2` in paperscraper `v0.1.0`.
- [@juliusbierk](https://github.com/juliusbierk): Bugfixes
