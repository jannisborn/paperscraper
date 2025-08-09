# API Reference

This section documents the public API of **paperscraper**.

Below you’ll find links to the documentation for each module:

- [`paperscraper`](paperscraper/index.md) — Main package entry point.
- [`paperscraper.arxiv`](arxiv.md) — ArXiv scraping & keyword search
- [`paperscraper.citations`](citations.md) — Get (self-)citations & (self-)reference of papers and authors
- [`paperscraper.get_dumps`](get_dumps.md) — Utilities to download bioRxiv, medRxiv & chemRxiv metadata
- [`paperscraper.pdf`](pdf.md) — Download publications as pdfs
- [`paperscraper.pubmed`](pubmed.md) — Pubmed keyword search
- [`paperscraper.scholar`](scholar.md) — Google Scholar endpoints
- [`paperscraper.xrxiv`](xrxiv.md) — Shared utilities for {bio,med,chem}Rxiv 


## Citation
If you use `paperscraper`, please cite a paper that motivated our development of this tool.


<normal>
```bibtex
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
</normal> 
---

## Top-level API

::: paperscraper
    options:
        show_if_no_docstring: false
        show_submodules: false
        filters:
            - "!^_[^_]"
