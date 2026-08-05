# Governance

`paperscraper` is maintained as an open-source research software project. Its
scope is to provide practical tools for scholarly metadata collection,
publication search, full-text retrieval where access is available, citation
analysis, and related reproducible examples.

## Maintainers

The project maintainers are responsible for reviewing contributions, deciding on
API changes, publishing releases, and keeping the package aligned with its
research-software scope. The current maintainers are the package authors listed
in `pyproject.toml` and on PyPI.

## Decision Making

Small fixes can be reviewed and merged by a maintainer when tests and
documentation are adequate. Larger changes, new dependencies, new data sources,
or compatibility-breaking changes should be discussed in an issue before a pull
request is opened.

Maintainers aim for consensus. If consensus is not possible, final decisions are
made by the active maintainers based on project scope, maintenance burden,
backward compatibility, testability, and benefit to users.

## Contribution Review

Pull requests are evaluated for:

- Correctness and reproducibility.
- Compatibility with existing public APIs.
- Test coverage appropriate to the change.
- Documentation for user-facing behavior.
- Respect for source platform terms, publisher restrictions, and credential
  safety.

Maintainers may request changes, split large pull requests, or decline changes
that would add substantial maintenance cost without clear benefit to the core
use cases.

## Releases

Releases are made by maintainers when a set of changes is ready for users. The
project uses versioned Git tags and publishes packages to PyPI. Release notes are
provided through GitHub releases and PyPI release history rather than a separate
changelog file.

## Project Direction

Priorities are guided by user reports, contributor interest, upstream API
changes, documentation quality, and the needs of reproducible literature and
bibliometric analyses. The project favors reliable, well-documented workflows
over broad but weakly maintained source coverage.
