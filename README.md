# PDF Password Protection

Encrypt Odoo PDF reports with passwords. Choose a static password or generate one dynamically from partner data (VAT number, phone, email).

## Features

- **Static Password** -- Set a fixed password for any report.
- **Dynamic from Partner VAT** -- Automatically use the partner's VAT number as the PDF password.
- **Dynamic from Partner Phone** -- Use the partner's phone or mobile number (spaces stripped) as the password.
- **Dynamic from Partner Email** -- Use the partner's email address as the password.
- **Per-Report Configuration** -- Enable or disable password protection on each report individually.
- **Smart Fallback** -- If a dynamic field is empty, the module falls back to the static password.
- **Works with All QWeb PDF Reports** -- Invoices, quotations, payslips, delivery slips, and any custom report.
- **Translated into 8 Languages** -- English, French, Spanish, German, Dutch, Portuguese (BR), Italian, Chinese (Simplified). Each user sees the dialog in their own Odoo language.

## How It Works

1. Go to **Settings > Technical > Actions > Reports** and select any QWeb PDF report.
2. Enable **"PDF Password Protection"** and choose the password source.
3. Generate the report. The output PDF is encrypted with the chosen password.

The module overrides `_render_qweb_pdf` on `ir.actions.report` to encrypt the generated PDF using pypdf (or PyPDF2 as a fallback) after Odoo renders it.

## Technical Details

| Item                  | Value                                              |
|-----------------------|----------------------------------------------------|
| Odoo Version          | 18.0                                     |
| License               | LGPL-3                                             |
| Dependencies          | `base`                                             |
| Python Dependencies   | Bundled with Odoo (PyPDF2 / pypdf)                 |
| Custom Fields Prefix  | `x_` (upgrade-safe)                                |
| Encryption Standard   | AES-128 (pypdf default)                            |
| Performance Impact    | Minimal (< 100ms per report)                       |
| Languages             | EN, FR, ES, DE, NL, PT-BR, IT, ZH-CN               |

## Fields Added to `ir.actions.report`

| Field                      | Type      | Description                              |
|----------------------------|-----------|------------------------------------------|
| `x_pdf_password_enabled`   | Boolean   | Enable PDF password protection           |
| `x_pdf_password_method`    | Selection | Password source (static/vat/phone/email) |
| `x_pdf_static_password`    | Char      | Static password value                    |

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
docker exec -it pdfpwd-odoo-18 \
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

Each user sees the dialog in the language set in **Preferences -> Language**. Regional variants (e.g. `fr_BE`, `nl_BE`) inherit from the base language via Odoo's standard fallback. To add a new language, drop a `<code>.po` file into `i18n/` - the canonical template is `i18n/no_pdf_password_protection.pot`.

## GDPR & Compliance

Under GDPR Article 32, organizations must implement appropriate technical measures to secure personal data. Password-encrypting PDF reports that contain partner names, addresses, VAT numbers, and financial details helps satisfy this requirement.

## Compatibility

- Odoo 18.0 Community and Enterprise
- Works with any module that generates QWeb PDF reports (Accounting, Sale, Purchase, HR, Stock, etc.)

## Author

**Naim OUDAYET** - Odoo developer based in Tunisia.

- Website: [oudayet.com](https://www.oudayet.com)
- Email: contact@oudayet.com
- GitHub: [@naimoudayet](https://github.com/naimoudayet)
- [Odoo App Store](https://apps.odoo.com/apps/modules/18.0/no_pdf_password_protection)

## License

This module is licensed under [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html).
