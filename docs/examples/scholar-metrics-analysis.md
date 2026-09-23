# Scholar Metrics Analysis

This page covers Google Scholar workflows through SearchAPI, researcher-level
Semantic Scholar metrics, and journal impact factors.

## SearchAPI Setup

Set the API key once through the environment, or pass `api_key=...` to each
function explicitly:

```sh
export SEARCH_API_KEY=YOUR_SEARCHAPI_KEY
export SS_API_KEY=YOUR_SEMANTIC_SCHOLAR_KEY  # Optional enrichment.
```

The SearchAPI-backed utilities cover the following workflows:

| Task | Function | Result |
| --- | --- | --- |
| Search Scholar | `get_scholar_papers` | Paper metadata as a DataFrame |
| Count citations | `get_citations_from_title` | Google Scholar citation count |
| Export a citation | `get_bibtex_entry`, `get_endnote_entry` | BibTeX or EndNote text |
| Find citing papers | `get_citing_papers_from_title` | A list of `Paper` objects |
| Find an author's papers | `get_scholar_author_papers` | Author-paper metadata as a DataFrame |

SearchAPI calls are retried with bounded exponential backoff. The complete
outputs below were captured from live calls on 23 September 2026. They reflect
live Google Scholar data, so paper order and citation counts can change.

## Keyword Paper Search

Search Google Scholar and return paper metadata as a DataFrame:

```pycon
>>> from paperscraper.scholar import get_scholar_papers
>>> papers = get_scholar_papers(
...     "GT4SD",
...     backend="searchapi",
...     search_api_kwargs={"top_k": 1, "num_enrich": 1},
... )
>>> papers.iloc[0].to_dict()
{
    'title': 'Accelerating material design with the generative toolkit for scientific discovery',
    'authors': [
        'Matteo Manica',
        'Jannis Born',
        'Joris Cadow',
        'Dimitrios Christofidellis',
        'Ashish Dave',
        'Dean Clarke',
        'Yves Gaetan Nana Teukam',
        'Giorgio Giannone',
        'Samuel C Hoffman',
        'Matthew Buchan',
        'Vijil Chenthamarakshan',
        'Timothy Donovan',
        'Hsiang Han Hsu',
        'Federico Zipoli',
        'Oliver Schilter',
        'Akihiro Kishimoto',
        'Lisa Hamada',
        'Inkit Padhi',
        'Karl Wehden',
        'Lauren McHugh',
        'Alexy Khrabrov',
        'Payel Das',
        'Seiji Takeda',
        'John R Smith',
    ],
    'year': 2023,
    'abstract': 'With the growing availability of data within various scientific domains, generative models hold enormous potential to accelerate scientific discovery. They harness powerful representations learned from datasets to speed up the formulation of novel hypotheses with the potential to impact material discovery broadly. We present the Generative Toolkit for Scientific Discovery (GT4SD). This extensible open-source library enables scientists, developers, and researchers to train and use state-of-the-art generative models to accelerate scientific discovery focused on organic material design.',
    'journal': 'NPJ Computational Materials',
    'citations': 58,
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

The default `backend` is `"auto"`: it uses SearchAPI when `SEARCH_API_KEY` is
configured, then Semantic Scholar when `SS_API_KEY` is configured, and otherwise
falls back to `scholarly`, which has limited throughput. An explicit `api_key`
can be passed with a specific backend. Citation counts can differ between
providers and between Scholar records for different versions of a paper.

## Bibliographic Export

Export a Google Scholar citation through SearchAPI in BibTeX or EndNote format.
Both functions accept a title or DOI; DOI inputs are first resolved through
Semantic Scholar:

```pycon
>>> from paperscraper.citations import get_bibtex_entry, get_endnote_entry
>>> title = "Quantum theory and application of contextual optimal transport"
>>> print(get_bibtex_entry(title))
@inproceedings{mariella2024quantum,
  title={Quantum theory and application of contextual optimal transport},
  author={Mariella, Nicola and Akhriev, Albert and Tacchino, Francesco and Zoufal, Christa and Gonzalez-Espitia, Juan Carlos and Harsanyi, Benedek and Koskin, Eugene and Tavernelli, Ivano and Woerner, Stefan and Rapsomaniki, Marianna and Zhuk, Sergiy and Born, Jannis},
  booktitle={International Conference on Machine Learning},
  pages={34822--34845},
  year={2024},
  organization={PMLR}
}
>>> print(get_endnote_entry(title))
%0 Journal Article
%T Quantum theory and application of contextual optimal transport
%A Mariella, Nicola
%A Akhriev, Albert
%A Tacchino, Francesco
%A Zoufal, Christa
%A Gonzalez-Espitia, Juan Carlos
%A Harsanyi, Benedek
%A Koskin, Eugene
%A Tavernelli, Ivano
%A Woerner, Stefan
%A Rapsomaniki, Marianna
%J arXiv preprint arXiv:2402.14991
%D 2024
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
...     max_results=5,
...     full_info=True,
... ).iloc[4]
>>> paper.to_dict()
{
    'title': 'Unifying Molecular and Textual Representations via Multi-task Language Modelling',
    'authors': [
        'Dimitrios Christofidellis*',
        'Giorgio Giannone*',
        'Jannis Born',
        'Ole Winther',
        'Teodoro Laino',
        'Matteo Manica',
    ],
    'publication': 'International Conference on Machine Learning, ICML 2023, 2023',
    'year': 2023,
    'citations': 201,
    'journal': 'International Conference on Machine Learning, ICML 2023',
    'date': '2023/1/29',
    'volume': '',
    'issue': '',
    'pages': '',
    'publisher': '',
    'description': 'The recent advances in neural language models have also been successfully applied to the field of chemistry, offering generative solutions for classical problems in molecular design and synthesis planning. These new methods have the potential to fuel a new era of data-driven automation in scientific discovery. However, specialized models are still typically required for each task, leading to the need for problem-specific fine-tuning and neglecting task interrelations. The main obstacle in this field is the lack of a unified representation between natural language and chemical representations, complicating and limiting human-machine interaction. Here, we propose the first multi-domain, multi-task language model that can solve a wide range of tasks in both the chemical and natural language domains. Our model can handle chemical and natural language concurrently, without requiring expensive pre-training on single domains or task-specific models. Interestingly, sharing weights across domains remarkably improves our model when benchmarked against state-of-the-art baselines on single-domain and cross-domain tasks. In particular, sharing information across domains and tasks gives rise to large improvements in cross-domain tasks, the magnitude of which increase with scale, as measured by more than a dozen of relevant metrics. Our work suggests that such models can robustly and efficiently accelerate discovery in physical sciences by superseding problem-specific fine-tuning and enhancing human-model interactions.',
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
