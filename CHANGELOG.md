# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-13

First public release: a self-hostable, fully citable RAG chatbot for EU
regulatory questions over the EurLex corpus.

### Added

- **Ingestion & retrieval** — CSV loading, cleaning and structural chunking;
  OpenRouter embeddings into a local ChromaDB store; hybrid retrieval (dense
  vectors + BM25 fused with reciprocal rank fusion) followed by LLM reranking.
- **Grounded generation** — prompt assembly, citation formatting, and a
  grounding guardrail that flags unsupported CELEX citations. Answers are
  produced via an OpenAI-compatible LLM (OpenCode Go).
- **Multi-agent pipeline** — an intent router (LLM classifier with a
  deterministic rule-based fallback) dispatching to Q&A, Explore and Greeting
  agents, plus a Refiner that rewrites weak/empty responses.
- **Multi-dataset chat** — choose datasets per question and use an `@`-mention
  picker to scope retrieval to specific documents or acts (`document_ids` /
  `celex_ids`).
- **Unified dataset registry** — private per-user documents and shared
  regulatory collections in one Datasets UI, with regulatory
  **import/export bundles** (`.rcdataset.zip`, optional precomputed embeddings).
- **Personal document library** — PDF/DOCX/TXT/MD/CSV upload with tags,
  semantic search, and per-user isolation.
- **Topics** — saved topics with timelines, summaries, and refresh.
- **Accounts & admin** — JWT auth, per-user history and feedback, self-service
  username/password changes, and admin user management (create, rename, reset
  password, grant/revoke admin, hard-delete with guards).
- **UI languages** — English, French and Vietnamese for both the interface and
  the assistant's answers.
- **Packaging & ops** — Docker Compose (backend, frontend, Caddy), a Makefile,
  a prebuilt EurLex corpus shipped via Git LFS, a user guide, screenshots, and
  a CI workflow (lint + tests + frontend build).

### Notes

- The corpus is frozen at **August 2019** and is not legal advice.
- The embedded dataset is frozen; recent legislation may be missing.

[Unreleased]: https://github.com/ngohoanhkhoa/regulatory_compliance/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ngohoanhkhoa/regulatory_compliance/releases/tag/v0.1.0
