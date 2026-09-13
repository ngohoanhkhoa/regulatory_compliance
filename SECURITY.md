# Security Policy

## Supported versions

This project is pre-1.0; security fixes are applied to the `main` branch.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities. Instead,
use the repository's **Security → Report a vulnerability** (private advisory)
feature, or email the maintainers listed in `pyproject.toml`. Include:

- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- affected component and version/commit.

We aim to acknowledge reports within a few days and will coordinate a fix and
disclosure timeline with you.

## Handling secrets

- **Never commit API keys or tokens.** `.env` is gitignored; only
  `.env.example` (placeholders) is committed.
- `JWT_SECRET` in `.env.example` is a placeholder — set a strong random value in
  production (`openssl rand -hex 32`).
- The default development admin account (`admin` / `0000`) is created on first
  start for convenience. **Change its password immediately** in any shared or
  production deployment, or set `DEFAULT_ADMIN_PASSWORD` before first run.

## Deployment notes

- The application is designed to run on a trusted network. Put it behind
  HTTPS (the bundled Caddy config does this) and restrict who can reach it.
- User-uploaded documents and the metadata database may contain sensitive
  content. Back up `data/` and `.vector_store/` securely and restrict access.
