# PDF Password Protection

Encrypt every Odoo PDF report with a password — static or dynamic from partner data (VAT, phone, email). Per-report toggle, AES-128 encryption, GDPR-friendly, available in 9 languages.

## Choose Your Odoo Version

Each Odoo major version lives on its own branch. Pick the one matching your server.

| Odoo Version | Stable | Development |
|---|---|---|
| 19.0 | [`19.0`](../../tree/19.0) | [`19.0.dev`](../../tree/19.0.dev) |
| 18.0 | [`18.0`](../../tree/18.0) | [`18.0.dev`](../../tree/18.0.dev) |
| 17.0 | [`17.0`](../../tree/17.0) | [`17.0.dev`](../../tree/17.0.dev) |
| 16.0 | [`16.0`](../../tree/16.0) | [`16.0.dev`](../../tree/16.0.dev) |

The technical module name is **`no_pdf_password_protection`** on every version branch.

## What It Does

- **Static Password** — Set a fixed password for any report.
- **Dynamic from Partner VAT** — Use the partner's VAT number as the PDF password.
- **Dynamic from Partner Phone** — Use the partner's phone or mobile (spaces stripped).
- **Dynamic from Partner Email** — Use the partner's email address.
- **Per-Report Configuration** — Enable or disable on each report individually.
- **Smart Fallback** — If the dynamic field is empty, falls back to the static password.
- **Works with Every QWeb PDF Report** — Invoices, quotations, payslips, delivery slips, and any custom report.
- **Translated into 9 Languages** — English, French, Spanish, German, Dutch, Portuguese (BR), Italian, Chinese (Simplified), Arabic. Each user sees the configuration in their own Odoo language.

## Quick Install

1. Check out the branch matching your Odoo version (see table above).
2. Copy the `no_pdf_password_protection/` folder into a directory listed in your Odoo `addons_path`.
3. **Apps → Update Apps List → search "PDF Password Protection" → Install**.

Full per-version installation, configuration, and test instructions live in each branch's own README.

## Languages

Ships with translations for:

| Code     | Language                |
|----------|-------------------------|
| `en_US`  | English (source)        |
| `fr`     | French                  |
| `es`     | Spanish                 |
| `de`     | German                  |
| `nl`     | Dutch                   |
| `pt_BR`  | Portuguese (Brazil)     |
| `it`     | Italian                 |
| `zh_CN`  | Chinese (Simplified)    |
| `ar`     | Arabic                  |

Regional variants (e.g. `fr_BE`, `nl_BE`) inherit from the base language via Odoo's standard fallback. To add a new language, drop a `<code>.po` file into the branch's `i18n/` folder — the canonical template is `i18n/no_pdf_password_protection.pot`.

## GDPR & Compliance

Under GDPR Article 32, organizations must implement appropriate technical measures to secure personal data. Password-encrypting PDF reports that contain partner names, addresses, VAT numbers, and financial details helps satisfy this requirement.

## Compatibility

Works with all standard and custom QWeb PDF reports on **Odoo 16.0 through 19.0**, Community and Enterprise editions. Requires `pypdf` (or legacy `PyPDF2`) on the server where reports are rendered.

## Repository Layout

This `main` branch is a landing page only. Code lives on the per-version branches above.

## Author

**Naim OUDAYET** — Odoo developer based in Tunisia.

- Website: [oudayet.com](https://www.oudayet.com)
- Email: contact@oudayet.com
- GitHub: [@naimoudayet](https://github.com/naimoudayet)

## License

[LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html).
