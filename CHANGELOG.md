# Changelog

This repository hosts **PDF Password Protection** as separate per-Odoo-version branches. Each version branch maintains its own detailed changelog. This file tracks repository-level changes only.

## 2026-05-12

- `main` rewritten as a multi-version landing page (module code, `Dockerfile`, and `docker-compose.yml` removed — they now live on the per-version branches only).
- Full ODOO_GUIDELINES.md compliance pass applied across all version branches:
  - **i18n** — Tier 2 set added (8 languages: EN source, FR, ES, DE, NL, PT-BR, IT, ZH-CN). POT + 7 PO files under `no_pdf_password_protection/i18n/`. Flag PNGs under `no_pdf_password_protection/static/description/flags/`.
  - **App Store description** — sanitizer hardening (`<code>` → `<em>`, monospace `<div>` → `<pre>`, banded sections use `padding: 48px 32px`). Hero gets a "8 Languages" badge. Color palette canonicalized to canonical uppercase per §1; legacy `#5a3a50` / `#017E84` / `#e6a817` mapped to `#5A3A52` / `#00A09D` / `#FF7F4F`.
  - **Manifest** — added required `maintainers`, `price`, `currency: "USD"`, `support` fields and `# Copyright 2026 Naim OUDAYET` header.
  - **Python dependency** — switched primary import from `PyPDF2` to `pypdf` (maintained successor, identical API); `PyPDF2` kept as fallback.
  - **Infra** — added `Dockerfile` (pypdf install with PEP 668 workaround), `docker-compose.yml` (port 1816), `CHANGELOG.md`, regenerated `banner.svg` per §3 canonical template.
- All version branches bumped to `X.0.1.1.0`.

## Per-version changelogs

For module-level history, see the `CHANGELOG.md` on each version branch:

| Odoo Version | Stable | Development |
|---|---|---|
| 19.0 | [`19.0/CHANGELOG.md`](../../blob/19.0/CHANGELOG.md) | [`19.0.dev/CHANGELOG.md`](../../blob/19.0.dev/CHANGELOG.md) |
| 18.0 | [`18.0/CHANGELOG.md`](../../blob/18.0/CHANGELOG.md) | [`18.0.dev/CHANGELOG.md`](../../blob/18.0.dev/CHANGELOG.md) |
| 17.0 | [`17.0/CHANGELOG.md`](../../blob/17.0/CHANGELOG.md) | [`17.0.dev/CHANGELOG.md`](../../blob/17.0.dev/CHANGELOG.md) |
| 16.0 | [`16.0/CHANGELOG.md`](../../blob/16.0/CHANGELOG.md) | [`16.0.dev/CHANGELOG.md`](../../blob/16.0.dev/CHANGELOG.md) |
