# Changelog

All notable changes to **PDF Password Protection** for Odoo 16.0 are documented here.

This file follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.
Versions use Odoo's `<odoo_version>.<module_major>.<module_minor>.<module_patch>` scheme.

## [16.0.2.0.0] - 2026-09-02

### Security

- **PDF encryption now uses AES-256 by default.** Previous releases called `PdfWriter.encrypt(password)` with no `algorithm` argument, and both pypdf and PyPDF2 default that to **RC4-128** - a cipher that is cryptographically broken and deprecated in PDF 2.0. Generated files carried `/V 2 /R 3`; they now carry `/V 5 /R 6` with an `AESV3` crypt filter. Anyone relying on this module for confidential documents should regenerate previously issued PDFs.
- **Printing several customers at once no longer leaks one customer's document to another.** Odoo merges a multi-record print into a single PDF carrying one password; with a dynamic source that password came from the first record, so the file opened for one recipient and exposed every other recipient's document inside it. Such a batch is now produced **without** protection rather than with a password that only one recipient holds.
- **The archived copy can be encrypted too**, when you ask for it. Odoo writes the `ir.attachment` copy from *inside* `_render_qweb_pdf`, before the module saw the bytes, so on any report with an `attachment` expression the download was encrypted while the copy kept on the record stayed plaintext. That copy can now be encrypted with each record's own password via the new **Also Protect the Copy Kept in Odoo** setting - left **off** by default, because the module's job is protecting documents that *leave* Odoo and every route out re-encrypts anyway.
- **"Send by Post" (snailmail) is no longer broken.** It renders the report and hands the bytes to a postal printing provider, which cannot open an encrypted file. Encryption is now skipped for that render.

### Added

- **`x_pdf_encryption_algo`** on `ir.actions.report` - choose AES-256 (default), AES-128, or RC4-128. RC4-128 is retained only for very old readers and is labelled as such.
- A warning on the report form when the server's PDF library cannot produce AES, so a silent RC4 fallback is visible in the UI and not only in the log.
- 58 tests, up from the previous suite, covering the emitted cipher per algorithm, the batch guard, the archived copy and the password resolvers.

### Changed

- **Phone passwords are now digits only.** Previously only spaces were stripped, so `(216) 71-123-456` became `(216)71-123-456` and `216.71.123.456` was left untouched - a recipient had to guess the punctuation their number happened to be stored with. All formats now reduce to the same digits.
- Passwords longer than 127 bytes are refused rather than encrypted. ISO 32000 caps the standard security handler there, and readers have historically truncated over-long passwords differently, which produces a file the recipient cannot open.
- The test suite no longer skips when the database has no `res.partner` PDF report - it creates one. Ten tests covering the batch guard, the archived copy and the phone resolver were silently skipping on a normal database.
- Tests reuse existing partners instead of creating them. This module depends only on `base`, so Odoo runs its tests *before* `account` loads; the registry then lacks account's `res.partner` fields while the database still has their NOT NULL columns, making `res.partner.create()` fail on any database with Accounting installed.

### Notes for this series

- **`pypdf` remains a declared dependency on 16.0, unlike the 18.0 and 19.0 branches.** Those images ship PyPDF2 2.12, whose `PdfReader` / `PdfWriter` this module can use, so the declaration was dropped there. The official `odoo:16` image ships **PyPDF2 1.26**, which exposes only `PdfFileReader` / `PdfFileWriter` and cannot produce AES at any setting. The requirement is real here, so it is declared and Odoo refuses the install with a clear message rather than failing later on an import.
- **Emailed invoices need no second module on this series.** Core renders a mail template's report attachment through `_render_qweb_pdf`, which this module overrides, so the emailed invoice is encrypted with the customer's own password out of the box. On 18.0 and 19.0 Accounting builds that document by a separate path, which is why those branches carry the companion `no_pdf_password_protection_account`; 16.0 does not need it. Verified on a 16.0 database, not assumed.

### Upgrade notes

- **Default cipher changes on upgrade.** Reports with no explicit algorithm set (including every report configured before this release) will produce AES-256 from now on. Set **Encryption Algorithm** to *RC4-128 (legacy readers only)* on a per-report basis if you must keep serving readers older than Acrobat 9 (2008).
- **Phone-sourced passwords change.** Anyone using the Partner Phone source must tell recipients the new rule: their number, digits only. Previously issued PDFs keep their old password.
## [16.0.1.2.0] - 2026-05-13

### Added
- **Arabic translation** (`ar`) — 9 languages total. All 8 field/selection msgids covered (`Enable PDF Password Protection`, `Partner Email / Phone / VAT Number`, `Password Source`, `Static Password`) plus the form-section view label and manifest fields.
- New language card with AR flag in the "Available in 9 Languages" section of the App Store description.
- `ar` row in the Languages table in README.
- `ar.png` added under `static/description/flags/` (sourced from the shared `_shared/flags/` library).

### Changed
- **Fixed broken .po references**: every existing language (fr/es/de/nl/pt_BR/it/zh_CN) used `code:addons/.../py:0` references for Python field `string="..."` declarations — wrong format for jsonb translation merge, so none of them actually translated field labels or selection values in the UI. Regenerated all .po files via `odoo --i18n-export` to get the canonical reference format (`model:ir.model.fields,field_description:...` / `model:ir.model.fields.selection,name:...` / `model_terms:ir.ui.view,arch_db:...`), then ported existing translations into the corrected structure. Verified on a fresh DB with `--load-language=fr_FR,ar_001` that field labels, selection values, and the form-section view header all translate correctly.
- Hero "8 Languages" badge updated to "9 Languages".
- Module version bumped from `16.0.1.1.0` to `16.0.1.2.0` (semver minor for new feature + translation fix).

## [16.0.1.1.0] - 2026-05-12

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
- Module version bumped from `16.0.1.0.0` to `16.0.1.1.0`.

## [16.0.1.0.0] - Initial release

### Added
- Override `_render_qweb_pdf` on `ir.actions.report` to encrypt generated PDFs.
- Three password sources: Static, Partner VAT, Partner Phone, Partner Email.
- Smart fallback to static password when dynamic field is empty.
- Per-report toggle via `x_pdf_password_enabled` Boolean.
- AES-128 encryption via PyPDF2 / pypdf.
- Tests at `tests/test_pdf_encryption.py`.
