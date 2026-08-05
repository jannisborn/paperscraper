# Contributing

Thanks for considering a contribution to `paperscraper`. Contributions are
welcome when they improve reliability, documentation, tests, supported scholarly
metadata sources, or the ergonomics of existing workflows.

## Ways to Contribute

- Report bugs with a minimal reproducible example.
- Improve documentation, examples, or error messages.
- Add tests for existing behavior.
- Fix source-specific API breakage.
- Propose new metadata sources or retrieval fallbacks.

For larger changes, please open an issue first so the design, maintenance cost,
and API surface can be discussed before implementation.

## Development Setup

The project uses `uv` for local development:

```sh
uv sync --group dev
uv run python -c "import paperscraper"
```

Run formatting, linting, and tests before opening a pull request:

```sh
uv run ruff format paperscraper
uv run ruff check paperscraper
uv run isort paperscraper
uv run pytest paperscraper
```

Some tests exercise external scholarly services and can be slow or sensitive to
rate limits. The GitHub Actions test suite is the source of truth for release
readiness; it can take a long time because it verifies source and wheel installs
against the supported workflows.

## Pull Request Expectations

- Keep changes focused and avoid unrelated refactors.
- Add or update tests when changing behavior.
- Update documentation and examples when changing user-facing APIs.
- Do not commit API keys, credentials, downloaded server dumps, PDFs, or other
  large generated artifacts.
- Preserve backward compatibility unless a breaking change has been discussed.

## Release Notes

This project does not maintain a separate `CHANGELOG.md`. Release notes are kept
with versioned GitHub releases and PyPI release history. Maintainers summarize
notable changes there when publishing a new package version.

## Conduct

Please keep issues and pull requests respectful, technical, and actionable. The
maintainers may close or moderate interactions that are abusive, off-topic, or
not aligned with the project scope.
