# Changelog

This repository hosts **PDF Password Protection** as separate per-Odoo-version branches. Each version branch maintains its own detailed changelog. This file tracks repository-level changes only.

## 2026-05-13 (v1.2.0 — Arabic + .po reference fix + storefront polish)

- All version branches bumped to `X.0.1.2.0`. **9 languages total** with the addition of `ar` (Arabic). New `ar.png` flag added to the shared library at `N:\Apps\_shared\flags\`.
- **Fixed broken translation pipeline** that affected every version since the initial i18n release. The original .po files used `code:addons/.../py:0` references for Python `string="..."` field declarations — wrong format for Odoo's jsonb translation merge, so none of fr/es/de/nl/pt_BR/it/zh_CN actually translated field labels, selection values, or the form-section view header. Regenerated the .pot via `odoo --i18n-export` to get the canonical reference format (`model:ir.model.fields,field_description:...` / `model:ir.model.fields.selection,name:...` / `model_terms:ir.ui.view,arch_db:...`), then ported every existing translation into the corrected structure. Validated on fresh v16/v17/v18/v19 DBs with `--load-language=fr_FR,ar_001`: all three jsonb columns (en_US/fr_FR/ar_001) now populate correctly.
- **Storefront `index.html` cleanup** — language flag grid switched from 4-per-line (`col-md-3 col-sm-4 col-6`) to 3-per-line (`col-md-4 col-sm-6 col-12`) to match the PDF-Preview-Before-Print pattern; trailing "Standard Odoo gettext PO files…" technical footnote removed (buyer-facing copy, not relevant to buyers). Cosmetic — no functional change.
- **Manual-test validation** — all 4 dev branches and all 4 store branches verified via the §13 dev preset (module + sale/contacts/account/project with demo + 9 active languages incl. en_US) on a fresh DB. Unit suite ran 32/32 green on each version (17 executed + 15 by-design skips for partner-report demo data).
- **Documentation** — `N:\Apps\ODOO_GUIDELINES.md` §12.4 rewritten with the canonical .po reference matrix and recovery procedure; new §13 captures the full dev DB provisioning preset (v16/17/18 legacy CLI + v19 subcommand CLI with `ODOO_RC`); workspace-level `N:\Apps\CLAUDE.md` added so future Claude sessions read the guidelines before touching any Odoo module.

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
