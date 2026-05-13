# Changelog

All notable changes to **PDF Password Protection** for Odoo 19.0 are documented here.

This file follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.
Versions use Odoo's `<odoo_version>.<module_major>.<module_minor>.<module_patch>` scheme.

## [19.0.1.2.0] - 2026-05-13

### Added
- **Arabic translation** (`ar`) — 9 languages total. All 8 field/selection msgids covered (`Enable PDF Password Protection`, `Partner Email / Phone / VAT Number`, `Password Source`, `Static Password`) plus the form-section view label and manifest fields.
- New language card with AR flag in the "Available in 9 Languages" section of the App Store description.
- `ar` row in the Languages table in README.
- `ar.png` added under `static/description/flags/` (sourced from the shared `_shared/flags/` library).

### Changed
- **Fixed broken .po references**: every existing language (fr/es/de/nl/pt_BR/it/zh_CN) used `code:addons/.../py:0` references for Python field `string="..."` declarations — wrong format for jsonb translation merge, so none of them actually translated field labels or selection values in the UI. Regenerated all .po files via `odoo --i18n-export` to get the canonical reference format (`model:ir.model.fields,field_description:...` / `model:ir.model.fields.selection,name:...` / `model_terms:ir.ui.view,arch_db:...`), then ported existing translations into the corrected structure. Verified on a fresh DB with `--load-language=fr_FR,ar_001` that field labels, selection values, and the form-section view header all translate correctly.
- Hero "8 Languages" badge updated to "9 Languages".
- Module version bumped from `19.0.1.1.0` to `19.0.1.2.0` (semver minor for new feature + translation fix).

## [19.0.1.1.0] - 2026-05-12

### Added
- **Internationalization (i18n) support** with 8 languages: English (source), French, Spanish, German, Dutch, Portuguese (Brazil), Italian, Chinese (Simplified).
- POT template + 7 PO files under `no_pdf_password_protection/i18n/`.
- `static/description/flags/` folder with 8 PNG flags (referenced relatively from `index.html`).
- **"Available in 8 Languages"** section in App Store description.
- **"8 Languages"** badge in App Store hero banner.
- `Languages` section + table in `README.md`.
- `CHANGELOG.md` at repo root.
- `Dockerfile` and `docker-compose.yml` for dev stack (port 1816).
- `banner.svg` source (renders to `banner.png` via cairosvg).
- Copyright header in `__manifest__.py` and `models/ir_actions_report.py`.

### Changed
- `external_dependencies.python` updated from `PyPDF2` to `pypdf` (maintained successor; identical API). Python import order in `models/ir_actions_report.py` tries `pypdf` first, falls back to `PyPDF2`.
- Manifest: added required portfolio fields `maintainers`, `price`, `currency`, `support` (per ODOO_GUIDELINES.md section 4).
- `index.html` sanitizer hardening:
  - Banded sections now use `padding: 48px 32px` (was `48px 0`).
  - Inline `<code>` replaced with `<em>` (Odoo stylesheet otherwise restyles `<code>` red).
  - Monospace `<div>` code block replaced with `<pre>` (no `font-family` declaration).
- `index.html` color palette canonicalized to uppercase `#714B67` / `#5A3A52` / `#00A09D` / `#FF7F4F` / `#475569` / `#94A3B8` / `#E8DDE5` / `#F8F5F7` (per section 1).
- Legacy badge colors `#5a3a50` -> `#5A3A52`, `#017E84` -> `#00A09D`, `#e6a817` (yellow) -> `#FF7F4F` (orange, NO yellow rule).
- Module version bumped from `19.0.1.0.0` to `19.0.1.1.0`.

## [19.0.1.0.0] - Initial release

### Added
- Override `_render_qweb_pdf` on `ir.actions.report` to encrypt generated PDFs.
- Three password sources: Static, Partner VAT, Partner Phone, Partner Email.
- Smart fallback to static password when dynamic field is empty.
- Per-report toggle via `x_pdf_password_enabled` Boolean.
- AES-128 encryption via PyPDF2 / pypdf.
- Tests at `tests/test_pdf_encryption.py`.
