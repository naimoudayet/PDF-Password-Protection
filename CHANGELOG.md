# Changelog

All notable changes to **PDF Password Protection** for Odoo 19.0 are documented here.

This file follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.
Versions use Odoo's `<odoo_version>.<module_major>.<module_minor>.<module_patch>` scheme.

## [19.0.2.0.0] - 2026-08-31

### Security

- **PDF encryption now uses AES-256 by default.** Previous releases called `PdfWriter.encrypt(password)` without an `algorithm` argument, and both pypdf and PyPDF2 default that to **RC4-128** - a cipher that is cryptographically broken and deprecated in PDF 2.0. Generated files carried `/V 2 /R 3`; they now carry `/V 5 /R 6` with an `AESV3` crypt filter. Anyone relying on this module for confidential documents should regenerate previously issued PDFs.
- **"Send & Print" no longer emails an unencrypted invoice.** `account.move.send` builds its PDF through `_pre_render_qweb_pdf()`, never `_render_qweb_pdf()`, so the encryption override was never reached on that path: the Print button produced an encrypted file while the customer received a plaintext one. Fixed by the new companion module (below).
- **Printing several customers at once no longer leaks one customer's document to another.** Odoo merges a multi-record print into a single PDF, which can carry only one password; with a dynamic source that password came from the first record, so the file opened for one recipient and exposed every other recipient's document inside it, while those recipients could not open it at all. Such a batch is now refused with an explanatory error pointing at Send & Print, which encrypts each document separately. Batches that resolve to one password (same customer, or a static password) are unaffected.
- **The archived copy is encrypted too**, when you ask for it. Odoo writes the `ir.attachment` copy from *inside* `_render_qweb_pdf`, before the module saw the bytes, so on any report with an `attachment` expression the download was encrypted while the copy kept on the record stayed plaintext. That copy can now be encrypted with each record's own password via the new **Also Protect the Copy Kept in Odoo** setting - left **off** by default, because the module's job is protecting documents that *leave* Odoo and every route out re-encrypts anyway: encrypting at rest would only make your own staff type a password to preview a record they can already open. Emailed invoices are unavoidably the exception, since Odoo sends the exact file it stores.
- **The fallback pro-forma is protected too.** When the invoice PDF fails to render, Odoo falls back to sending a pro-forma and creates that attachment directly rather than through the step the companion module hooks - so it was the one document in the whole send flow that would have reached the customer in the clear, carrying the same customer data as the invoice it stood in for.
- **"Send by Post" (snailmail) is no longer broken.** It renders the report and hands the bytes to a postal printing provider, which cannot open an encrypted file. Encryption is now skipped for that render.

### Added

- **`x_pdf_encryption_algo`** on `ir.actions.report` - choose AES-256 (default), AES-128, or RC4-128. RC4-128 is retained only for very old readers and is labelled as such.
- **`no_pdf_password_protection_account`** - companion module bridging this module and Accounting. `auto_install`, LGPL-3, ships in this repository. It encrypts the invoice at the final step of the send pipeline (`_link_invoice_documents`), after Odoo's own post-processing has run, so each invoice is encrypted with **its own customer's** password rather than the first record's.
- PDF/A e-invoices are detected and deliberately left unencrypted, with an explanatory note posted to the invoice chatter. ISO 19005 forbids encryption; encrypting a Factur-X or ZUGFeRD invoice would break conformance and hide the embedded e-invoicing XML from the recipient's AP system.
- 8 new tests covering the emitted cipher per algorithm, and 13 covering the accounting send path (53 total across both modules).

### Fixed

- **The module could not be installed on a stock Odoo.** The manifest declared `external_dependencies: {"python": ["pypdf"]}`, which Odoo enforces at install time, but the official `odoo:19` image ships **PyPDF2 2.12.1 and no pypdf** - so installation failed with `MissingDependency` even though the code already had a working PyPDF2 fallback. The declaration is removed; the backend is detected at runtime instead.
- When only PyPDF2 is available, AES is impossible (its `encrypt()` has no `algorithm` parameter). The module now logs a clear warning naming `pip install pypdf` and falls back to RC4-128 rather than raising.

### Changed

- **Phone passwords are now digits only.** Previously only spaces were stripped, so `(216) 71-123-456` became `(216)71-123-456` and `216.71.123.456` was left untouched - a recipient had to guess the punctuation their number happened to be stored with. All formats now reduce to the same digits.
- Passwords longer than 127 bytes are refused rather than encrypted. ISO 32000 caps the standard security handler there, and readers have historically truncated over-long passwords differently, which produces a file the recipient cannot open.
- A warning is shown on the report form when the server's PDF library cannot produce AES, so a silent RC4 fallback is visible in the UI and not only in the log.
- The test suite no longer skips when the database has no `res.partner` PDF report - it creates one. Ten tests covering the batch guard, the archived copy and the phone resolver were silently skipping on a normal database.
- Tests reuse existing partners instead of creating them. This module depends only on `base`, so Odoo runs its tests *before* `account` loads; the registry then lacks account's `res.partner` fields while the database still has their NOT NULL columns, making `res.partner.create()` fail on any database with Accounting installed.
- The test suite imports `pypdf` before `PyPDF2`, matching the module. PyPDF2 2.x cannot verify a `/V 5` encryption dictionary, so reading AES-256 output back with it failed on the library, not the module.
- Translations regenerated for all 9 languages via `odoo i18n export`. The `model:ir.module.module,summary|shortdesc|description` entries carried by earlier `.po` files were dropped: `module_meta_information` no longer exists anywhere in Odoo 19, so those entries translated nothing.

### Storefront

- **Screenshots added for the first time.** The listing had none: the App Store does not auto-discover files under `static/description/`, they must be referenced from `index.html`, and none were. Four now show the settings screen, the password sources, the refused mixed batch, and the delivered document asking for its password. The companion module gets its own two.
- The companion module gets a full listing page and banner of its own and is published as a **separate free app**, not bundled into this one. Each listing now points at the other: this module explains when you would want the companion, and the companion states plainly that it needs this module and has no settings of its own. Both manifests and the README carry the same relationship, so it is clear from any entry point that the base module stands alone and the add-on does not.
- **Banner corrected**: it advertised `AES-128`, which was never what the module produced (it was RC4-128, and is now AES-256).
- Buyer-facing copy de-leaked: internal method and library names removed from the description page in favour of what the module actually does for the reader.

### Upgrade notes

- **Default cipher changes on upgrade.** Reports with no explicit algorithm set (including every report configured before this release) will produce AES-256 from now on. Set **Encryption Algorithm** to *RC4-128 (legacy readers only)* on a per-report basis if you must keep serving readers older than Acrobat 9 (2008).
- **`auto_install` does not apply retroactively.** Odoo only marks an auto-install module when one of its dependencies is being installed in the same operation. If you already run this module alongside Accounting, install `no_pdf_password_protection_account` once from the Apps list; new installations pick it up automatically.
- **Phone-sourced passwords change.** Anyone using the Partner Phone source must tell recipients the new rule: their number, digits only. Previously issued PDFs keep their old password.
- AES requires `pypdf`. If your deployment only has PyPDF2, run `pip install pypdf` to enable AES; otherwise the module keeps working at RC4-128 and says so in the log.

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
