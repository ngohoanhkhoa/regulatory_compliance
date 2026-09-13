# Contributing

Thanks for your interest in improving the EU Regulatory Compliance RAG Chatbot!
This document explains how to set up a development environment, the conventions
we follow, and how to submit changes.

## Code of conduct

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

Prerequisites: Python 3.11–3.12, [uv](https://astral.sh/uv), Node.js 18+.

```bash
git clone <your-fork-url>
cd regulatory_compliance
uv sync --extra dev
(cd frontend && npm install)
cp .env.example .env        # then fill in the API keys
```

The backend test suite mocks all network calls, so you can run it without API
keys:

```bash
uv run python -m pytest -q
uv run ruff check src tests
uv run ruff format --check src tests   # optional formatting check
```

Frontend:

```bash
cd frontend
npm run build
```

## Large files & data

Large binary artifacts are stored with [Git LFS](https://git-lfs.com):

- Install it once (`git lfs install`) before cloning/pushing so
  `data/processed/chunks.parquet` (the processed CEPS EurLex corpus) resolves to
  the real file instead of a pointer.
- Never commit the raw CSV (`data/raw/`), the metadata database
  (`data/processed/metadata.db`), user uploads, or `.vector_store/` — they are
  gitignored and may contain large or sensitive data.
- New large artifacts should be added to `.gitattributes` (LFS) rather than
  committed directly to Git.

## Project layout

| Path | Contents |
|---|---|
| `src/ingestion/` | CSV loading, cleaning, chunking, embedding, indexing |
| `src/retrieval/` | Vector store, BM25, hybrid fusion, reranking, multi-dataset retrieval |
| `src/generation/` | LLM client, prompt builder, citation formatter, orchestrator |
| `src/agents/` | Intent routing and specialized agents (Q&A, explore, greeting) |
| `src/auth/` | Users, JWT security, dependencies |
| `src/datasets/` | Dataset registry + import/export bundles |
| `src/documents/` | Per-user document library (extract, chunk, store) |
| `src/topics/` | Saved topics + timelines |
| `src/corpus/` | Read-only regulatory corpus views |
| `src/api/` | FastAPI app and routers |
| `frontend/` | React + Vite SPA |
| `tests/` | Pytest unit + integration tests |

## Guidelines

- **Keep dependencies minimal.** Prefer the standard library and what is already
  in `pyproject.toml`.
- **No network calls in tests.** Inject fakes/monkeypatch the clients (see
  `tests/` for the established patterns).
- **Types & lint.** Code must pass `ruff check src tests` (line length 100).
- **Tests.** Add or update tests for every behaviour change. Bug fixes should
  come with a regression test.
- **Commits.** Use clear, imperative messages (e.g. `fix(chat): handle empty
  retrieval`). Keep changes focused.
- **Secrets.** Never commit keys. `.env` is gitignored; add new variables to
  `.env.example` with safe placeholders and document them.

## Submitting a pull request

1. Fork the repository and create a branch from `main`.
2. Make your change, add tests, and run the full suite + lint.
3. Fill in the pull request template, describing the motivation and behaviour.
4. Keep the PR scoped; large changes are easier to review when split.

## Reporting bugs & requesting features

Use the GitHub issue templates. For security issues, follow
[SECURITY.md](SECURITY.md) instead of opening a public issue.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
