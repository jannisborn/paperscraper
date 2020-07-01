# paper_scraper

## Overview

Package to scrape paper from arxiv, PubMed, bio/medRxiv based on keywords.

Install:

```sh
pip install .
```

### development

Install in editable mode for development:

```sh
pip install -e .
```

### examples

Dump papers metadata from medRxiv in JSONL format:

```console
dump-medrxiv /tmp/medrxiv-$(date +"%Y-%m-%d").jsonl
```
