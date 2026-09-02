# PDF Password Protection

![License](https://img.shields.io/badge/license-LGPL--3-blue)
![Odoo](https://img.shields.io/badge/Odoo-16.0-blueviolet)
![Languages](https://img.shields.io/badge/languages-9-orange)
![Version](https://img.shields.io/badge/version-16.0.2.0.0-informational)

Encrypt Odoo PDF reports with passwords. Choose a static password or generate one dynamically from partner data (VAT number, phone, email).

## One Module on This Series

On Odoo 16 this module is all you need. Odoo builds the PDF it attaches to an
email template through the same `_render_qweb_pdf` call the Print button uses, so
turning protection on covers **both** routes: the report you print and the invoice
you email.

On Odoo 18 and 19 that is no longer true - Accounting there builds the emailed
invoice by a separate path - so those branches carry a second module,
`no_pdf_password_protection_account`, to cover it. This branch does not need one.

## Features

- **AES-256 Encryption** -- Modern, standards-based encryption by default. AES-128 and legacy RC4-128 remain selectable per report for very old readers.
- **Static Password** -- Set a fixed password for any report.
- **Dynamic from Partner VAT** -- Automatically use the partner's VAT number as the PDF password.
- **Dynamic from Partner Phone** -- Use the partner's phone or mobile number as the password, reduced to digits only so the recipient always knows what to type.
- **Dynamic from Partner Email** -- Use the partner's email address as the password.
- **Per-Report Configuration** -- Enable or disable password protection on each report individually.
- **Smart Fallback** -- If a dynamic field is empty, the module falls back to the static password.
- **Works with All QWeb PDF Reports** -- Invoices, quotations, payslips, delivery slips, and any custom report.
- **Translated into 9 Languages** -- English, French, Spanish, German, Dutch, Portuguese (BR), Italian, Chinese (Simplified), Arabic. Each user sees the dialog in their own Odoo language.

## How It Works

1. Go to **Settings > Technical > Actions > Reports** and select any QWeb PDF report.
2. Enable **"PDF Password Protection"** and choose the password source.
3. Generate the report. The output PDF is encrypted with the chosen password.

The module overrides `_render_qweb_pdf` on `ir.actions.report` to encrypt the generated PDF using pypdf (or PyPDF2 as a fallback) after Odoo renders it.

Encryption strength is set per report via **Encryption Algorithm**. AES-256 is the default and is readable by Acrobat 9+ and every modern PDF viewer. AES requires `pypdf`; on a deployment that only ships PyPDF2 the module logs a warning and falls back to RC4-128 rather than failing.

## Technical Details

| Item                  | Value                                              |
|-----------------------|----------------------------------------------------|
| Odoo Version          | 16.0                                               |
| Module Version        | 16.0.2.0.0                                         |
| License               | LGPL-3                                             |
| Dependencies          | `base`                                             |
| Python Dependencies   | `pypdf` (declared) -- Odoo 16 bundles PyPDF2 1.26, which has no AES and a different API |
| Custom Fields Prefix  | `x_` (upgrade-safe)                                |
| Encryption Standard   | AES-256 default; AES-128 and RC4-128 selectable    |
| Performance Impact    | Minimal (< 100ms per report)                       |
| Languages             | EN, FR, ES, DE, NL, PT-BR, IT, ZH-CN, AR           |

## Fields Added to `ir.actions.report`

| Field                      | Type      | Description                              |
|----------------------------|-----------|------------------------------------------|
| `x_pdf_password_enabled`   | Boolean   | Enable PDF password protection           |
| `x_pdf_password_method`    | Selection | Password source (static/vat/phone/email) |
| `x_pdf_static_password`    | Char      | Static password value                    |
| `x_pdf_encryption_algo`    | Selection | Cipher: `aes256` (default), `aes128`, `rc4_128` |
| `x_pdf_protect_stored_copy`| Boolean   | Encrypt the archived copy too (default off, see above) |
| `x_pdf_aes_unavailable`    | Boolean   | Computed; true when the server's PDF library cannot do AES |

## Invoice Emails

Emailed invoices are protected by this module on Odoo 16, with nothing extra to
install. Core renders a mail template's report attachment through
`_render_qweb_pdf`, which this module overrides, so the customer receives the same
encrypted document the Print button produces - and because the render happens one
record at a time, each customer's copy carries that customer's own password.

**PDF/A e-invoices are a deliberate exception.** ISO 19005 forbids encryption, so a
Factur-X or ZUGFeRD invoice must go out readable or it stops being a valid
e-invoice. If you generate those, leave protection off for that report.

## Behaviour You Should Know About

**A mixed batch print comes back unlocked.** Odoo merges a multi-record print into one PDF, and a PDF carries a single password. When the selected records do not share one, the merged copy is produced *without* protection -- an ordinary bulk print is never interrupted, and it is recorded in the log rather than on every record, since printing many documents at once is a list action. Print a record on its own, or use Send & Print, to get a protected copy. Batches that resolve to the same password -- one customer, or a static password -- are protected as usual.

**The email can explain the password.** The Send dialog carries an option, on by default and shown only when that invoice report has protection enabled, which puts a short notice above your message so the customer is not left with a file that will not open. The wording is a translatable field on the report: edit it in the UI, in your own words, per language. It is added only when the document really was protected -- never after a PDF/A skip or an unresolved password. The batch send has no such option; it always includes the notice.

**Your own staff are not asked for a password.** The module protects documents that *leave* Odoo -- what you print, email, or publish on the portal. The copy Odoo archives on the record stays readable, so a colleague previewing an invoice from the chatter is not blocked by a password for a record they can already open; Odoo's access rights already govern who sees it. Every route out re-encrypts on the way, so nothing delivered is weakened by this.

Turn on **Also Protect the Copy Kept in Odoo** if you want encryption at rest as well.

**Emailed invoices follow the same rule.** The copy that leaves is encrypted; the copy stored on the record stays readable unless you switch on *Also Protect the Copy Kept in Odoo*, so your own team can open a sent invoice without the customer's password.

**"Send by Post" is left unencrypted on purpose.** Snailmail hands the PDF to a postal printing provider that cannot open an encrypted file, so encryption is skipped for that render and noted in the log.

**PDF/A e-invoices are left unencrypted on purpose.** See the Send & Print section above.

**Portal downloads are encrypted.** A customer opening their invoice from the portal needs the password, even though they are already signed in. That is the point -- the file stays protected after it leaves Odoo -- but tell your customers, or they will call you.

**Passwords are capped at 127 bytes**, the limit in the PDF specification. Anything longer is refused rather than encrypted, because readers truncate over-long passwords differently and the recipient may end up unable to open the file.

**The static password is stored in the clear** and is readable by anyone who can read report definitions (typically Settings users) through the API, even though the form masks it. Treat it as a shared secret, not a credential.

**Multi-company:** the static password is a single value on the report, not per company. Companies sharing a report share its password.

**After uninstalling**, PDFs that were already encrypted stay encrypted -- the module is not needed to open them, but nothing can recover a password derived from partner data that has since changed.

## Screenshots

| | |
|---|---|
| ![Password protection settings on an invoice report](no_pdf_password_protection/static/description/screenshots/screenshot_1.png) | ![The four password sources](no_pdf_password_protection/static/description/screenshots/screenshot_2.png) |
| Turn it on per report, pick the cipher, pick where the password comes from. | Static, or a different password per recipient from their VAT number, phone or email. |
| ![Two customers selected for one print job, refused](no_pdf_password_protection/static/description/screenshots/screenshot_3.png) | ![The recipient opening the document](no_pdf_password_protection/static/description/screenshots/screenshot_4.png) |
| A merged file carries one password, so a mixed batch is stopped and explained. | The delivered file asks for the password in any modern PDF reader. |

## Installation

1. Place the `no_pdf_password_protection` folder in your Odoo addons directory.
2. Restart the Odoo server.
3. Go to **Apps**, remove the "Apps" filter, search for **"PDF Password Protection"**, and click **Install**.

## Configuration

1. Navigate to **Settings > Technical > Actions > Reports**.
2. Select the report you want to protect (e.g., "Invoices").
3. In the **PDF Password Protection** section:
   - Check **Enable PDF Password Protection**.
   - Choose the **Password Source**: Static Password, Partner VAT, Partner Phone, or Partner Email.
   - If using Static Password, enter the password value.
4. Save. All future PDF generations for that report will be encrypted.

## Docker Setup (Development)

```bash
docker-compose up -d
```

- Odoo: http://localhost:1816
- PostgreSQL: internal `db` service (no exposed port by default)

## Running Tests

```bash
docker exec -it pdfpwd-odoo-19 \
  odoo --test-enable --stop-after-init \
  -d test_db -i no_pdf_password_protection \
  --test-tags no_pdf_password_protection
```

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

Each user sees the dialog in the language set in **Preferences -> Language**. Regional variants (e.g. `fr_BE`, `nl_BE`) inherit from the base language via Odoo's standard fallback. To add a new language, drop a `<code>.po` file into `i18n/` - the canonical template is `i18n/no_pdf_password_protection.pot`.

## GDPR & Compliance

Under GDPR Article 32, organizations must implement appropriate technical measures to secure personal data. Password-encrypting PDF reports that contain partner names, addresses, VAT numbers, and financial details helps satisfy this requirement.

## Compatibility

- Odoo 16.0 Community and Enterprise
- Works with any module that generates QWeb PDF reports (Accounting, Sale, Purchase, HR, Stock, etc.)

## Author

**Naim OUDAYET** - Odoo developer based in Tunisia.

- Website: [oudayet.com](https://www.oudayet.com)
- Email: contact@oudayet.com
- GitHub: [@naimoudayet](https://github.com/naimoudayet)
- [Odoo App Store](https://apps.odoo.com/apps/modules/16.0/no_pdf_password_protection)

## License

This module is licensed under [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html).
