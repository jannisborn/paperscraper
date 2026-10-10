# Scholar Metrics Analysis

This page covers Google Scholar workflows through [SearchApi][searchapi], researcher-level
Semantic Scholar metrics, and journal impact factors.

<div align="right" markdown="1">

[![SearchApi Google Scholar API — Get your API key](https://raw.githubusercontent.com/jannisborn/paperscraper/main/assets/searchapi.png){ width="480" }][searchapi]

Supported by [SearchApi][searchapi]

</div>

[searchapi]: https://www.searchapi.io/google-scholar?utm_source=Github&utm_medium=sponsorship&utm_campaign=google_scholar_api&utm_content=jannisborn%2Fpaperscraper

## [SearchApi][searchapi] Setup

Get a [SearchApi API key][searchapi] and set [`SEARCH_API_KEY`][searchapi] through the environment, or pass `api_key=...` to each
function explicitly:

```sh
export SEARCH_API_KEY=YOUR_API_KEY
export SS_API_KEY=YOUR_SEMANTIC_SCHOLAR_KEY  # Optional enrichment.
```

The [SearchApi][searchapi] utilities cover the following workflows:

| Task | Function | Result |
| --- | --- | --- |
| Search Scholar | [`get_scholar_papers`][paperscraper.scholar.get_scholar_papers] | Paper metadata as a DataFrame |
| Count citations | [`get_citations_from_title`][paperscraper.citations.get_citations_from_title] | Google Scholar citation count |
| Export a citation | [`get_bibtex_entry`][paperscraper.citations.get_bibtex_entry], [`get_endnote_entry`][paperscraper.citations.get_endnote_entry] | BibTeX or EndNote text |
| Find citing papers | [`get_citing_papers_from_title`][paperscraper.citations.get_citing_papers_from_title] | A list of `Paper` objects |
| Find an author's papers | [`get_scholar_author_papers`][paperscraper.scholar.get_scholar_author_papers] | Author-paper metadata as a DataFrame |

[SearchApi][searchapi] calls are retried with bounded exponential backoff. The complete
outputs below were captured from live calls on 23 September 2026. They reflect
live Google Scholar data, so paper order and citation counts can change.

## Keyword Paper Search

Search Google Scholar and return paper metadata as a DataFrame:

```pycon
>>> from paperscraper.scholar import get_scholar_papers
>>> papers = get_scholar_papers(
...     "CMonge",
...     backend="searchapi",
...     search_api_kwargs={"top_k": 1, "num_enrich": 1},
... )
>>> papers.iloc[0].to_dict()
{
    'title': 'Conditional Monge Gap enables generalizable single-cell perturbation modelling',
    'authors': ['Alice Driessen', 'Dhruva Abhijit Rajwade', 'Benedek Harsanyi', 'Marianna Rapsomaniki', 'Jannis Born'],
    'year': 2026,
    'abstract': 'Learning the response of single cells to various treatments offers great potential to enable targeted therapies. In this context, neural optimal transport has emerged as a principled methodological framework because it inherently accommodates the challenges of unpaired data induced by cell destruction during data acquisition. However, most existing optimal transport approaches are incapable of conditioning on different treatment contexts and we still lack methods that show promising generalizability to unseen treatments. Here we propose the Conditional Monge Gap (CMonge), which learns optimal transport maps conditionally on arbitrary covariates.',
    'journal': 'Nature Machine Intelligence',
    'citations': 2,
}
```

`top_k` limits the returned rows. `num_enrich` controls how many rows receive
additional author-profile requests for full author, abstract, and journal data.

## Paper Citation Counts

Retrieve a Google Scholar citation count from an exact paper title:

```pycon
>>> from paperscraper.citations import get_citations_from_title
>>> title = "Quantum theory and application of contextual optimal transport"
>>> get_citations_from_title(title, backend="searchapi")
7
```

The default `backend` is `"auto"`: it uses [SearchApi][searchapi] when [`SEARCH_API_KEY`][searchapi] is
configured, then Semantic Scholar when `SS_API_KEY` is configured, and otherwise
falls back to `scholarly`, which has limited throughput. An explicit `api_key`
can be passed with a specific backend. Citation counts can differ between
providers and between Scholar records for different versions of a paper.

## Bibliographic Export

Export a Google Scholar citation through [SearchApi][searchapi] in BibTeX or EndNote format.
Both functions accept a title or DOI; DOI inputs are first resolved through
Semantic Scholar:

```pycon
>>> from paperscraper.citations import get_bibtex_entry, get_endnote_entry
>>> title = "Quantum doubly stochastic transformers"
>>> print(get_bibtex_entry(title))
@article{born2026quantum,
  title={Quantum doubly stochastic transformers},
  author={Born, Jannis and Skogh, Filip and Rhrissorrakrai, Kahn and Utro, Filippo and Wagner, Nico and Sobczyk, Aleksandros},
  journal={Advances in Neural Information Processing Systems},
  volume={38},
  pages={70224--70254},
  year={2026}
}
>>> print(get_endnote_entry(title))
%0 Journal Article
%T Quantum doubly stochastic transformers
%A Born, Jannis
%A Skogh, Filip
%A Rhrissorrakrai, Kahn
%A Utro, Filippo
%A Wagner, Nico
%A Sobczyk, Aleksandros
%J Advances in Neural Information Processing Systems
%V 38
%P 70224-70254
%D 2026
```

## Citing Papers

List papers citing a title on Google Scholar:

```pycon
>>> from paperscraper.citations import get_citing_papers_from_title
>>> title = "Quantum theory and application of contextual optimal transport"
>>> paper = get_citing_papers_from_title(title, max_results=1, full_info=True)[0]
>>> paper.__dict__
{
    'input': 'Advancing single-cell omics and cell-based therapeutics with quantum computing',
    'authors': ['A Bose', 'K Rhrissorrakrai', 'F Utro', 'L Parida'],
    'title': 'Advancing single-cell omics and cell-based therapeutics with quantum computing',
    'doi': '10.1038/s41580-025-00918-0',
}
```

By default, citing-paper results contain titles. `full_info=True` additionally
resolves authors and available DOIs through Semantic Scholar, using
`SS_API_KEY` unless `ss_api_key=...` is passed. For larger runs,
`SS_REQUEST_TIMEOUT`, `SS_CONCURRENCY_LIMIT`, and `SS_RATE_LIMIT_DELAY` can be
tuned through environment variables.

## Google Scholar Author Papers

Return papers and associated metadata for a researcher:

```pycon
>>> from paperscraper.scholar import get_scholar_author_papers
>>> paper = get_scholar_author_papers(
...     "Jannis Born",
...     max_results=25,
...     full_info=True,
... ).iloc[23]
>>> paper.to_dict()
{
    'title': "Regress, Don't Guess--A Regression-like Loss on Number Tokens for Language Models",
    'authors': [
        'Jonas Zausinger',
        'Lars Pennig',
        'Anamarija Kozina',
        'Sean Sdahl',
        'Julian Sikora',
        'Adrian Dendorfer',
        'Timofey Kuznetsov',
        'Mohamad Hagog',
        'Nina Wiedemann',
        'Kacper Chlodny',
        'Vincent Limbach',
        'Anna Ketteler',
        'Thorben Prein',
        'Vishwa Mohan Singh',
        'Michael Morris Danziger',
        'Jannis Born',
    ],
    'publication': 'International Conference on Machine Learning, ICML 2025, 2025',
    'year': 2025,
    'citations': 18,
    'journal': '',
    'date': '2025',
    'volume': '',
    'issue': '',
    'pages': '',
    'publisher': '',
    'description': '',
}
```

`full_info=True` adds journal and publication details at the cost of one extra
request per paper. Pass `author_id` to select a specific profile when names are
ambiguous.

When no exact profile exists, the function falls back to an `author:"name"`
Scholar search and warns that namesakes may be mixed. This fallback cannot
provide `full_info`. `max_results` defaults to 30, and explicit smaller or
larger integer limits are respected.

## Semantic Scholar Author Metrics

Semantic Scholar author pages expose `paperCount`, `citationCount`, and `hIndex`.
You can query them by Semantic Scholar Author ID:

```py
from paperscraper.citations.utils import semantic_scholar_requests_get

ssaid = "2062641025"
metrics = semantic_scholar_requests_get(
    f"https://api.semanticscholar.org/graph/v1/author/{ssaid}",
    params={"fields": "name,paperCount,citationCount,hIndex"},
).json()
```

```text
{
    "authorId": "2062641025",
    "name": "Jannis Born",
    "paperCount": 63,
    "citationCount": 1910,
    "hIndex": 21,
}
```

Resolve the same author by name:

```pycon
>>> from paperscraper.citations.utils import author_name_to_ssaid
>>> author_name_to_ssaid("Jannis Born")
("2062641025", "Jannis Born")
```

Or resolve through ORCID first:

```pycon
>>> from paperscraper.citations.orcid import orcid_to_author_name
>>> from paperscraper.citations.utils import author_name_to_ssaid
>>> name = orcid_to_author_name("0000-0001-8307-5670")
>>> author_name_to_ssaid(name)
("2062641025", "Jannis Born")
```

If you need the actual Semantic Scholar paper IDs for an author, use
`get_papers_for_author`:

```pycon
>>> from paperscraper.citations.utils import get_papers_for_author
>>> paper_ids = get_papers_for_author("2062641025")
>>> len(paper_ids)
63  # Number of papers linked to this Semantic Scholar author record.
>>> paper_ids[0]
'6c245545fcb88df49cf921ba0871b40818665b92'
```

Citation and paper counts can change as Semantic Scholar updates author records.

## Journal Impact Factors

Use `Impactor` to search journal names, abbreviations, E-ISSNs, or NLM IDs.

```pycon
>>> from paperscraper.impact import Impactor
>>> impactor = Impactor()
>>> impactor.search("Nat Comms", threshold=85, sort_by="impact")
[
    {"journal": "Nature Computational Science", "factor": 18.3, "score": 88},
    {"journal": "Nature Communications", "factor": 15.7, "score": 94},
    {"journal": "Natural Computing", "factor": 1.6, "score": 88},
]
```

`threshold` defaults to `100`, which behaves like an exact search. Lower values
allow fuzzier matches. `sort_by` can be `"impact"`, `"journal"`, or `"score"`.

Search by abbreviation, NLM ID, or E-ISSN:

```pycon
>>> impactor.search("Nat Rev Earth Environ")
[{"journal": "Nature Reviews Earth & Environment", "factor": 71.5, "score": 100}]
>>> impactor.search("101771060")
[{"journal": "Nature Reviews Earth & Environment", "factor": 71.5, "score": 100}]
>>> impactor.search("2662-138X")
[{"journal": "Nature Reviews Earth & Environment", "factor": 71.5, "score": 100}]
```

Filter by impact factor range:

```pycon
>>> impactor.search("Neural network", threshold=85, min_impact=1.5, max_impact=20)
[
    {"journal": "IEEE Transactions on Neural Networks and Learning Systems", "factor": 8.9, "score": 93},
    {"journal": "NEURAL NETWORKS", "factor": 6.3, "score": 91},
    {"journal": "Network", "factor": 3.1, "score": 92},
    {"journal": "NETWORK-COMPUTATION IN NEURAL SYSTEMS", "factor": 1.6, "score": 92},
    {"journal": "WORK-A Journal of Prevention Assessment & Rehabilitation", "factor": 1.5, "score": 86},
]
```

Return all available fields:

```pycon
>>> impactor.search("quantum information", threshold=90, return_all=True)
[
    {
        "factor": 8.3,
        "jcr": "Q1",
        "nlm_id": "101722857",
        "journal": "npj Quantum Information",
        "issn": ".",
        "zky": ".",
        "journal_abbr": "npj Quantum Inf",
        "eissn": "2056-6387",
        "score": 92,
    },
    {
        "factor": 2.9,
        "jcr": "Q2",
        "nlm_id": "101703749",
        "journal": "Information",
        "issn": ".",
        "zky": ".",
        "journal_abbr": "Information (Basel)",
        "eissn": "2078-2489",
        "score": 95,
    },
    {
        "factor": 1.3,
        "jcr": "Q2",
        "nlm_id": "9877123",
        "journal": "NATION",
        "issn": "0027-8378",
        "zky": ".",
        "journal_abbr": "Nation",
        "eissn": "0027-8378",
        "score": 91,
    },
    {
        "factor": 1.1,
        "jcr": ".",
        "nlm_id": "138060",
        "journal": "Reformation",
        "issn": "1357-4175",
        "zky": ".",
        "journal_abbr": "Reformation",
        "eissn": "1752-0738",
        "score": 90,
    },
]
```
