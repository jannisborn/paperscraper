# Scholar Metrics Analysis

This page collects examples for paper citation counts, researcher-level
Semantic Scholar metrics, and journal impact factors.

## Paper Citation Counts

Fetch citation counts by DOI using Semantic Scholar:

```pycon
>>> from paperscraper.citations import get_citations_by_doi
>>> get_citations_by_doi("10.1021/acs.jcim.3c00132")
12  # Semantic Scholar citation count.
```

Fetch citation counts by title from Google Scholar (SearchAPI or scholarly backend) or Semantic Scholar:

```pycon
>>> from paperscraper.citations import get_citations_from_title
>>> title = "GT4SD: Generative Toolkit for Scientific Discovery"
>>> get_citations_from_title(title, backend="scholarly")
9  # Google Scholar citation count.
```

The default `backend` is `"auto"`: it tries to use Google Scholar via SearchAPI (through the env var `SEARCH_API_KEY`) then Semantic Scholar (through `SS_API_KEY`) and otherwise uses Google Scholar via `scholarly` (which has very limited throughput).
An explicit `api_key` can be passed with a specific backend. 
NOTE: Citation counts will differ between Semantic Scholar and Google Scholar.

```sh
export SEARCH_API_KEY=YOUR_API_KEY
export SS_API_KEY=YOUR_API_KEY
```

For larger runs, `SS_REQUEST_TIMEOUT`, `SS_CONCURRENCY_LIMIT`, and
`SS_RATE_LIMIT_DELAY` can be tuned through environment variables.

## Researcher Metrics

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
