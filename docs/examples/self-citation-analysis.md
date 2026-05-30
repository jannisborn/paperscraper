# Self-Citation Analysis

The citations submodule uses Semantic Scholar paper, citation, and reference
metadata to estimate how often authors cite or reference their own work. Set
`SS_API_KEY` to increase throughput:

```sh
export SS_API_KEY=YOUR_API_KEY
```

Citation and reference counts can change as Semantic Scholar updates its records.

## Paper-Level Self-Links

Estimate self-citations and self-references for a paper:

```pycon
>>> from paperscraper.citations import self_citations_paper, self_references_paper
>>> doi = "10.1038/s41586-023-06600-9"
>>> self_citations = self_citations_paper(doi)
>>> self_citations.num_citations
141  # Total citations.
>>> self_citations.citation_score
3.192  # Mean self-citation percentage across paper authors.
>>> self_references = self_references_paper(doi)
>>> self_references.num_references
33  # Total references.
>>> self_references.reference_score
5.05  # Mean self-reference percentage across paper authors.
```

Both functions accept either one DOI/Semantic Scholar paper ID or a list. A
single input returns one result object; a list returns a list of result objects.

## Author Breakdown

Print the per-author self-link percentages:

```pycon
>>> self_citations.self_citations
{
    "Abhishek Sharma": 3.55,
    "Dániel Czégel": 0.71,
    "Michael Lachmann": 1.42,
    "C. Kempes": 3.55,
    "S. I. Walker": 4.96,
    "Leroy Cronin": 4.96,
}  # Percentage of citations that include each paper author.
>>> self_references.self_references
{
    "Abhishek Sharma": 3.03,
    "Dániel Czégel": 0.0,
    "Michael Lachmann": 0.0,
    "C. Kempes": 0.0,
    "S. I. Walker": 6.06,
    "Leroy Cronin": 21.21,
}  # Percentage of references that include each paper author.
```

## Author-Level Summary

For an author-level summary, use `Researcher`. Full author analyses can take
longer for large publication lists, so this example limits the run to one paper.

```pycon
>>> from paperscraper.citations.entity import Researcher
>>> researcher = Researcher("2289839817")
>>> researcher.ssids = ["2c1edb95c07643a834c9d4f8f2acedfecfe894de"]
>>> _ = researcher.self_citations()
>>> result = researcher.self_references()
>>> result.name
"K. Wijk"
>>> result.self_citation_ratio
0.0  # Mean self-citation percentage across the selected papers.
>>> result.self_reference_ratio
4.65  # Mean self-reference percentage across the selected papers.
>>> result.num_citations
10
>>> result.num_references
43
>>> result.self_references
{"Diff-SPORT: Diffusion-based Sensor Placement Optimization and Reconstruction of Turbulent flows in urban environments": 4.65}
```

## Unified Paper Interface

Use `SelfLinkClient` when you want self-citations and self-references through one
paper-level object. Paper inputs can be DOIs, Semantic Scholar paper IDs, or
titles; use `mode` when you want to disambiguate.

```pycon
>>> from paperscraper.citations import SelfLinkClient
>>> client = SelfLinkClient("10.1038/s41586-023-06600-9", mode="paper")
>>> client.extract()
>>> result = client.get_result()
>>> result.title
"Assembly theory explains and quantifies selection and evolution"
>>> result.citation_score
3.192  # Mean self-citation percentage across paper authors.
>>> result.reference_score
5.05  # Mean self-reference percentage across paper authors.
```

`SelfLinkClient(..., mode="author")` is also available for author-level runs.
Use `Researcher` directly when you want to limit the paper list before running,
as shown in the author-level example above.
