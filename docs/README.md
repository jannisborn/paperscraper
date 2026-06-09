[![build](https://github.com/jannisborn/paperscraper/actions/workflows/test_tip.yml/badge.svg?branch=main)](https://github.com/jannisborn/paperscraper/actions/workflows/test_tip.yml?query=branch%3Amain)
[![build](https://github.com/jannisborn/paperscraper/actions/workflows/test_pypi.yml/badge.svg?branch=main)](https://github.com/jannisborn/paperscraper/actions/workflows/test_pypi.yml?query=branch%3Amain)
[![build](https://github.com/jannisborn/paperscraper/actions/workflows/docs.yml/badge.svg?branch=main)](https://jannisborn.github.io/paperscraper/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/paperscraper.svg)](https://badge.fury.io/py/paperscraper)
[![Downloads](https://static.pepy.tech/badge/paperscraper)](https://pepy.tech/project/paperscraper)
[![codecov](https://codecov.io/github/jannisborn/paperscraper/branch/main/graph/badge.svg?token=Clwi0pu61a)](https://codecov.io/github/jannisborn/paperscraper)

# paperscraper

`paperscraper` is a Python package for reproducible searches over scholarly
metadata, accessible full-text retrieval, citation lookup, and small
bibliometric workflows across PubMed, arXiv, bioRxiv, medRxiv, and ChemRxiv.

```sh
pip install paperscraper
```

or:

```sh
uv add paperscraper
```

## What It Does

<div class="grid cards" markdown>

-   **Search scholarly metadata**

    Query PubMed and arXiv directly, or search local JSONL dumps from arXiv,
    bioRxiv, medRxiv, and ChemRxiv with one nested keyword convention.

    [:octicons-arrow-right-24: Paper keyword analysis](examples/paper-keyword-analysis.md)

-   **Build local preprint dumps**

    Download local xRxiv snapshots once, then run reproducible repeated searches
    without depending on live search results for every query.

    [:octicons-arrow-right-24: Getting started](examples/getting-started.md)

-   **Retrieve accessible full text**

    Save PDFs or XML from DOI metadata using direct links and supported fallback
    paths when access is available.

    [:octicons-arrow-right-24: PDF retrieval](examples/pdf-retrieval.md)

-   **Inspect citation behavior**

    Query citation counts, author metrics, journal impact factors, and
    paper-level or researcher-level self-citation and self-reference rates.

    [:octicons-arrow-right-24: Scholar metrics](examples/scholar-metrics-analysis.md)

    [:octicons-arrow-right-24: Self-citation analysis](examples/self-citation-analysis.md)

</div>

## Quick Example

```py
from paperscraper import dump_queries

ai = ["Artificial intelligence", "Machine learning"]
qc = ["Quantum computing", "Quantum information", "Quantum algorithm"]
chemistry = ["Chemistry", "Chemical", "Molecule", "Materials science"]

dump_queries([[ai, qc, chemistry]], ".")
```

Nested lists encode Boolean logic: outer lists are combined with `AND`, while
inner lists define synonyms combined with `OR`.

## Where To Go Next

- Start with [Getting Started](examples/getting-started.md) for installation and
  local dump setup.
- Use [Paper Keyword Analysis](examples/paper-keyword-analysis.md) for
  multi-source literature trend workflows.
- Use [PDF Retrieval](examples/pdf-retrieval.md) for full-text download options
  and supported fallbacks.
- Use [Scholar Metrics Analysis](examples/scholar-metrics-analysis.md) for
  citation counts, author metrics, and journal metrics.
- Use [Self-Citation Analysis](examples/self-citation-analysis.md) for
  self-citation and self-reference workflows.

API details are available under [API Documentation](api/index.md).
