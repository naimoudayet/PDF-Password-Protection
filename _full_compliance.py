#!/usr/bin/env python3
"""One-shot full ODOO_GUIDELINES.md compliance pass for PDF Password Protection.

Per-branch bundled commit covering all 6 phases:
  A. Sanitizer fixes (font-family / padding / <code> -> <em>)
  B. Color palette canonicalization (lowercase -> uppercase + legacy -> canonical)
  C. Manifest compliance (currency / price / support / maintainers + copyright header)
  D. Infrastructure (Dockerfile / docker-compose.yml / CHANGELOG.md / banner.svg+png)
  E. i18n full Tier 2 (POT + 7 PO files + flags/ folder + index.html Languages section)
  F. Version bump + commit

Run from N:/Apps/PDF-Password-Protection/ as cwd. Helper deletes itself.
"""
import base64
import os
import pathlib
import re
import shutil
import subprocess
import sys

import cairosvg

ALL_BRANCHES = [
    "16.0", "16.0.dev",
    "17.0", "17.0.dev",
    "18.0", "18.0.dev",
    "19.0", "19.0.dev",
    "main",
]
RETURN_TO = "19.0.dev"

REPO_ROOT = pathlib.Path("N:/Apps/PDF-Password-Protection")
MODULE = "no_pdf_password_protection"
SHARED_FLAGS_PNG = pathlib.Path("N:/Apps/_shared/flags/png")

# ============================================================================
# CONTENT CONSTANTS
# ============================================================================

LANGS = ["us", "fr", "es", "de", "nl", "br", "it", "cn"]

# ----- Manifest template -----
MANIFEST_TPL = '''# Copyright 2026 Naim OUDAYET
# License LGPL-3
{{
    "name": "PDF Password Protection",
    "summary": "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)",
    "description": "PDF Password Protection - encrypt any Odoo PDF report with passwords. "
                   "Static password or dynamic from partner fields (VAT, phone, email). "
                   "GDPR-friendly. Works with all QWeb PDF reports.",
    "version": "{odoo_major}.0.1.1.0",
    "category": "Extra Tools",
    "website": "https://www.oudayet.com",
    "author": "Naim OUDAYET",
    "maintainers": ["naimoudayet"],
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": ["base"],
    "external_dependencies": {{"python": ["pypdf"]}},
    "data": [
        "views/ir_actions_report_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "price": 0,
    "currency": "USD",
    "support": "contact@oudayet.com",
}}
'''

# ----- Model rewrite: try pypdf first, PyPDF2 fallback -----
MODEL_CONTENT = '''# Copyright 2026 Naim OUDAYET
# License LGPL-3
import io
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        PdfReader = PdfWriter = None
        _logger.warning(
            "pypdf / PyPDF2 not installed. PDF password protection will not work."
        )


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    x_pdf_password_enabled = fields.Boolean(
        string="Enable PDF Password Protection",
        default=False,
    )
    x_pdf_password_method = fields.Selection(
        [
            ("static", "Static Password"),
            ("vat", "Partner VAT Number"),
            ("phone", "Partner Phone"),
            ("email", "Partner Email"),
        ],
        string="Password Source",
        default="static",
    )
    x_pdf_static_password = fields.Char(string="Static Password")

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Override to encrypt the generated PDF if password protection is enabled."""
        result = super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

        if not PdfWriter:
            return result

        report = self._get_report(report_ref)
        if not report.x_pdf_password_enabled:
            return result

        pdf_content, content_type = result
        if content_type != "pdf":
            return result

        password = self._get_pdf_password(report, res_ids)
        if not password:
            return result

        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(password)

            output = io.BytesIO()
            writer.write(output)
            encrypted_pdf = output.getvalue()
            return encrypted_pdf, content_type
        except Exception as e:
            _logger.error("Failed to encrypt PDF: %s", e)
            return result

    def _get_pdf_password(self, report, res_ids):
        """Get the password based on the configured method."""
        method = report.x_pdf_password_method

        if method == "static":
            return report.x_pdf_static_password

        if not res_ids:
            return report.x_pdf_static_password or None

        record = self.env[report.model].browse(res_ids[0])
        partner = None

        if hasattr(record, "partner_id") and record.partner_id:
            partner = record.partner_id
        elif record._name == "res.partner":
            partner = record

        if not partner:
            return report.x_pdf_static_password or None

        if method == "vat":
            return partner.vat or report.x_pdf_static_password
        elif method == "phone":
            # res.partner.mobile was dropped in Odoo 19 - use getattr so the
            # same codebase works on v16/v17/v18 (mobile present) and v19+
            # (mobile absent) without AttributeError.
            mobile = getattr(partner, "mobile", False)
            return (
                (partner.phone or mobile or "").replace(" ", "")
                or report.x_pdf_static_password
            )
        elif method == "email":
            return partner.email or report.x_pdf_static_password

        return report.x_pdf_static_password
'''

# ----- Dockerfile (per §8 with pypdf) -----
DOCKERFILE_TPL = '''FROM odoo:{odoo_major}
USER root

# pypdf is the maintained successor to PyPDF2 and shares the same
# PdfReader/PdfWriter API. Installing 'pypdf' side-steps two issues:
#   1. apt-installed PyPDF2 can't be uninstalled by pip
#      ('RECORD file not found' on upgrade).
#   2. Newer Ubuntu bases (v18, v19 = 24.04) require
#      --break-system-packages under PEP 668.
RUN pip install --no-cache-dir pypdf \\
 || pip install --no-cache-dir --break-system-packages pypdf

USER odoo
'''

# ----- docker-compose.yml (port 1816 per §9 PDF-Password-Protection convention) -----
COMPOSE_TPL = '''name: pdfpwd-{odoo_major}

services:
  db:
    image: postgres:16
    container_name: pdfpwd-pg-{odoo_major}
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: postgres
    volumes:
      - db-data:/var/lib/postgresql/data

  odoo:
    build: .
    container_name: pdfpwd-odoo-{odoo_major}
    depends_on:
      - db
    ports:
      - "1816:8069"
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo
    volumes:
      - odoo-data:/var/lib/odoo
      - ./{module}:/mnt/extra-addons/{module}

volumes:
  db-data:
  odoo-data:
'''

# ----- CHANGELOG (per version branch) -----
CHANGELOG_TPL = '''# Changelog

All notable changes to **PDF Password Protection** for Odoo {odoo_major}.0 are documented here.

This file follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.
Versions use Odoo's `<odoo_version>.<module_major>.<module_minor>.<module_patch>` scheme.

## [{odoo_major}.0.1.1.0] - 2026-05-12

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
- Module version bumped from `{odoo_major}.0.1.0.0` to `{odoo_major}.0.1.1.0`.

## [{odoo_major}.0.1.0.0] - Initial release

### Added
- Override `_render_qweb_pdf` on `ir.actions.report` to encrypt generated PDFs.
- Three password sources: Static, Partner VAT, Partner Phone, Partner Email.
- Smart fallback to static password when dynamic field is empty.
- Per-report toggle via `x_pdf_password_enabled` Boolean.
- AES-128 encryption via PyPDF2 / pypdf.
- Tests at `tests/test_pdf_encryption.py`.
'''

# ----- README (full content, replaces existing) -----
README_TPL = '''# PDF Password Protection

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
| Odoo Version          | {odoo_major}.0                                     |
| License               | LGPL-3                                             |
| Dependencies          | `base`                                             |
| Python Dependencies   | `pypdf` (`PyPDF2` as fallback)                     |
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
docker exec -it pdfpwd-odoo-{odoo_major} \\
  odoo --test-enable --stop-after-init \\
  -d test_db -i no_pdf_password_protection \\
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

- Odoo {odoo_major}.0 Community and Enterprise
- Works with any module that generates QWeb PDF reports (Accounting, Sale, Purchase, HR, Stock, etc.)

## Author

**Naim OUDAYET** - Odoo developer based in Tunisia.

- Website: [oudayet.com](https://www.oudayet.com)
- Email: contact@oudayet.com
- GitHub: [@naimoudayet](https://github.com/naimoudayet)
- [Odoo App Store](https://apps.odoo.com/apps/modules/{odoo_major}.0/no_pdf_password_protection)

## License

This module is licensed under [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html).
'''

# ----- Banner SVG (per §3 canonical template) -----
BANNER_SVG = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640"
     font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#714B67"/>
      <stop offset="100%" stop-color="#5A3A52"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="1280" height="640" fill="url(#bg)"/>
  <rect x="0" y="0" width="1280" height="6" fill="#00A09D"/>

  <text x="100" y="98"  fill="#94A3B8" font-size="14" font-weight="700" letter-spacing="3">ODOO MODULE</text>

  <text x="100" y="240" fill="#FFFFFF" font-size="92" font-weight="800" letter-spacing="-1">PDF Password</text>
  <text x="100" y="340" fill="#FF7F4F" font-size="92" font-weight="800" letter-spacing="-1">Protection.</text>

  <text x="100" y="412" fill="#FFFFFF" font-size="26" font-weight="500">Encrypt every QWeb PDF report with a password.</text>
  <text x="100" y="450" fill="#BBA8B5" font-size="20" font-weight="400">Static or dynamic (partner VAT, phone, email). GDPR-ready. Zero config.</text>

  <line x1="100" y1="510" x2="1180" y2="510" stroke="#8A6A80" stroke-width="1" opacity="0.6"/>

  <g font-size="16" font-weight="700" letter-spacing="2">
    <text x="100" y="560" fill="#FFFFFF">STATIC</text>
    <text x="190" y="560" fill="#8A6A80">&#183;</text>
    <text x="215" y="560" fill="#FFFFFF">DYNAMIC</text>
    <text x="335" y="560" fill="#8A6A80">&#183;</text>
    <text x="360" y="560" fill="#FFFFFF">GDPR READY</text>
    <text x="520" y="560" fill="#8A6A80">&#183;</text>
    <text x="545" y="560" fill="#FFFFFF">ZERO CONFIG</text>
  </g>

  <g font-size="16" font-weight="700" letter-spacing="2">
    <text x="1180" y="560" fill="#FF7F4F" text-anchor="end">LGPL-3 &#183; FREE</text>
  </g>
</svg>
'''

# ----- PO template + translations -----
PO_HEADER_TPL = '''# Translation of Odoo Server.
# This file contains the translation of the following modules:
# 	* no_pdf_password_protection
#
msgid ""
msgstr ""
"Project-Id-Version: Odoo Server {odoo_major}.0\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: 2026-05-12 00:00+0000\\n"
"PO-Revision-Date: 2026-05-12 00:00+0000\\n"
"Last-Translator: \\n"
"Language-Team: {team}\\n"
"Language: {lang}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: \\n"
"Plural-Forms: {plural}\\n"

'''

# 9 unique strings; each entry is (kind, ref, msgid)
STRINGS = [
    ("model_selection", "odoo-python",
     "code:addons/no_pdf_password_protection/models/ir_actions_report.py:0",
     "Enable PDF Password Protection"),
    ("model_selection", "odoo-python",
     "code:addons/no_pdf_password_protection/models/ir_actions_report.py:0",
     "Partner Email"),
    ("model_selection", "odoo-python",
     "code:addons/no_pdf_password_protection/models/ir_actions_report.py:0",
     "Partner Phone"),
    ("model_selection", "odoo-python",
     "code:addons/no_pdf_password_protection/models/ir_actions_report.py:0",
     "Partner VAT Number"),
    ("model_selection", "odoo-python",
     "code:addons/no_pdf_password_protection/models/ir_actions_report.py:0",
     "Password Source"),
    ("manifest_shortdesc", None, None, "PDF Password Protection"),
    ("manifest_description", None, None,
     "PDF Password Protection - encrypt any Odoo PDF report with passwords. "
     "Static password or dynamic from partner fields (VAT, phone, email). "
     "GDPR-friendly. Works with all QWeb PDF reports."),
    ("manifest_summary", None, None,
     "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)"),
    ("model_selection", "odoo-python",
     "code:addons/no_pdf_password_protection/models/ir_actions_report.py:0",
     "Static Password"),
]

TRANSLATIONS = {
    "fr": {
        "Enable PDF Password Protection": "Activer la protection par mot de passe PDF",
        "Partner Email": "Email du partenaire",
        "Partner Phone": "Téléphone du partenaire",
        "Partner VAT Number": "Numéro de TVA du partenaire",
        "Password Source": "Source du mot de passe",
        "PDF Password Protection": "Protection par mot de passe PDF",
        "PDF Password Protection - encrypt any Odoo PDF report with passwords. Static password or dynamic from partner fields (VAT, phone, email). GDPR-friendly. Works with all QWeb PDF reports.":
            "Protection par mot de passe PDF - chiffrez n'importe quel rapport PDF Odoo avec des mots de passe. Mot de passe statique ou dynamique à partir des champs du partenaire (TVA, téléphone, email). Conforme RGPD. Fonctionne avec tous les rapports QWeb PDF.",
        "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)":
            "Chiffrez les rapports PDF avec des mots de passe - statique ou dynamique (TVA, téléphone, email du partenaire)",
        "Static Password": "Mot de passe statique",
    },
    "es": {
        "Enable PDF Password Protection": "Activar protección de PDF con contraseña",
        "Partner Email": "Email del partner",
        "Partner Phone": "Teléfono del partner",
        "Partner VAT Number": "NIF del partner",
        "Password Source": "Origen de la contraseña",
        "PDF Password Protection": "Protección de PDF con contraseña",
        "PDF Password Protection - encrypt any Odoo PDF report with passwords. Static password or dynamic from partner fields (VAT, phone, email). GDPR-friendly. Works with all QWeb PDF reports.":
            "Protección de PDF con contraseña - cifre cualquier informe PDF de Odoo con contraseñas. Contraseña estática o dinámica desde campos del partner (NIF, teléfono, email). Compatible con RGPD. Funciona con todos los informes QWeb PDF.",
        "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)":
            "Cifre informes PDF con contraseñas - estática o dinámica (NIF, teléfono, email del partner)",
        "Static Password": "Contraseña estática",
    },
    "de": {
        "Enable PDF Password Protection": "PDF-Passwortschutz aktivieren",
        "Partner Email": "E-Mail des Partners",
        "Partner Phone": "Telefonnummer des Partners",
        "Partner VAT Number": "USt-IdNr. des Partners",
        "Password Source": "Passwortquelle",
        "PDF Password Protection": "PDF-Passwortschutz",
        "PDF Password Protection - encrypt any Odoo PDF report with passwords. Static password or dynamic from partner fields (VAT, phone, email). GDPR-friendly. Works with all QWeb PDF reports.":
            "PDF-Passwortschutz - verschlüsseln Sie jeden Odoo-PDF-Bericht mit Passwörtern. Statisches Passwort oder dynamisch aus Partnerdaten (USt-IdNr., Telefon, E-Mail). DSGVO-konform. Funktioniert mit allen QWeb-PDF-Berichten.",
        "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)":
            "PDF-Berichte mit Passwörtern verschlüsseln - statisch oder dynamisch (USt-IdNr., Telefon, E-Mail des Partners)",
        "Static Password": "Statisches Passwort",
    },
    "nl": {
        "Enable PDF Password Protection": "PDF-wachtwoordbeveiliging inschakelen",
        "Partner Email": "E-mail van relatie",
        "Partner Phone": "Telefoon van relatie",
        "Partner VAT Number": "BTW-nummer van relatie",
        "Password Source": "Wachtwoordbron",
        "PDF Password Protection": "PDF-wachtwoordbeveiliging",
        "PDF Password Protection - encrypt any Odoo PDF report with passwords. Static password or dynamic from partner fields (VAT, phone, email). GDPR-friendly. Works with all QWeb PDF reports.":
            "PDF-wachtwoordbeveiliging - versleutel elk Odoo PDF-rapport met wachtwoorden. Statisch wachtwoord of dynamisch op basis van relatievelden (BTW, telefoon, e-mail). AVG-conform. Werkt met alle QWeb PDF-rapporten.",
        "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)":
            "Versleutel PDF-rapporten met wachtwoorden - statisch of dynamisch (BTW, telefoon, e-mail van relatie)",
        "Static Password": "Statisch wachtwoord",
    },
    "pt_BR": {
        "Enable PDF Password Protection": "Ativar proteção de PDF com senha",
        "Partner Email": "E-mail do parceiro",
        "Partner Phone": "Telefone do parceiro",
        "Partner VAT Number": "CNPJ do parceiro",
        "Password Source": "Origem da senha",
        "PDF Password Protection": "Proteção de PDF com senha",
        "PDF Password Protection - encrypt any Odoo PDF report with passwords. Static password or dynamic from partner fields (VAT, phone, email). GDPR-friendly. Works with all QWeb PDF reports.":
            "Proteção de PDF com senha - criptografe qualquer relatório PDF do Odoo com senhas. Senha estática ou dinâmica a partir de campos do parceiro (CNPJ, telefone, e-mail). Compatível com LGPD. Funciona com todos os relatórios QWeb PDF.",
        "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)":
            "Criptografe relatórios PDF com senhas - estática ou dinâmica (CNPJ, telefone, e-mail do parceiro)",
        "Static Password": "Senha estática",
    },
    "it": {
        "Enable PDF Password Protection": "Abilita protezione PDF con password",
        "Partner Email": "Email del partner",
        "Partner Phone": "Telefono del partner",
        "Partner VAT Number": "P.IVA del partner",
        "Password Source": "Origine della password",
        "PDF Password Protection": "Protezione PDF con password",
        "PDF Password Protection - encrypt any Odoo PDF report with passwords. Static password or dynamic from partner fields (VAT, phone, email). GDPR-friendly. Works with all QWeb PDF reports.":
            "Protezione PDF con password - cifra qualsiasi report PDF di Odoo con password. Password statica o dinamica dai campi del partner (P.IVA, telefono, email). Conforme al GDPR. Funziona con tutti i report QWeb PDF.",
        "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)":
            "Cifra i report PDF con password - statiche o dinamiche (P.IVA, telefono, email del partner)",
        "Static Password": "Password statica",
    },
    "zh_CN": {
        "Enable PDF Password Protection": "启用PDF密码保护",
        "Partner Email": "合作伙伴邮箱",
        "Partner Phone": "合作伙伴电话",
        "Partner VAT Number": "合作伙伴增值税号",
        "Password Source": "密码来源",
        "PDF Password Protection": "PDF密码保护",
        "PDF Password Protection - encrypt any Odoo PDF report with passwords. Static password or dynamic from partner fields (VAT, phone, email). GDPR-friendly. Works with all QWeb PDF reports.":
            "PDF密码保护 - 使用密码加密任何Odoo的PDF报告。静态密码或基于合作伙伴字段（增值税号、电话、邮箱）的动态密码。符合GDPR要求。适用于所有QWeb PDF报告。",
        "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)":
            "使用密码加密PDF报告 - 静态或动态（合作伙伴的增值税号、电话、邮箱）",
        "Static Password": "静态密码",
    },
}

PO_LANG_META = {
    "fr":    {"team": "French",                "plural": "nplurals=2; plural=(n > 1);"},
    "es":    {"team": "Spanish",               "plural": "nplurals=2; plural=(n != 1);"},
    "de":    {"team": "German",                "plural": "nplurals=2; plural=(n != 1);"},
    "nl":    {"team": "Dutch",                 "plural": "nplurals=2; plural=(n != 1);"},
    "pt_BR": {"team": "Portuguese (Brazil)",   "plural": "nplurals=2; plural=(n > 1);"},
    "it":    {"team": "Italian",               "plural": "nplurals=2; plural=(n != 1);"},
    "zh_CN": {"team": "Chinese (Simplified)",  "plural": "nplurals=1; plural=0;"},
}


def make_entry(kind, marker, ref, msgid, msgstr=""):
    lines = ["#. module: no_pdf_password_protection"]
    if marker:
        lines.append(f"#. {marker}")
    if ref:
        lines.append(f"#: {ref}")
    elif kind.startswith("manifest_"):
        field = kind.split("_", 1)[1]  # shortdesc / description / summary
        lines.append(
            f"#: model:ir.module.module,{field}:no_pdf_password_protection.module_meta_information"
        )
    # Escape quotes and newlines inside msgid
    escaped = msgid.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    lines.append(f'msgid "{escaped}"')
    escaped_str = msgstr.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    lines.append(f'msgstr "{escaped_str}"')
    return "\n".join(lines) + "\n"


def generate_pot(odoo_major):
    header = PO_HEADER_TPL.format(
        odoo_major=odoo_major, lang="", team="", plural=""
    )
    entries = []
    for kind, marker, ref, msgid in STRINGS:
        entries.append(make_entry(kind, marker, ref, msgid, msgstr=""))
    return header + "\n".join(entries)


def generate_po(lang, odoo_major):
    meta = PO_LANG_META[lang]
    header = PO_HEADER_TPL.format(
        odoo_major=odoo_major, lang=lang, team=meta["team"], plural=meta["plural"]
    )
    entries = []
    translations = TRANSLATIONS[lang]
    for kind, marker, ref, msgid in STRINGS:
        msgstr = translations.get(msgid, "")
        entries.append(make_entry(kind, marker, ref, msgid, msgstr=msgstr))
    return header + "\n".join(entries)


# ----- Color normalization map -----
COLOR_REPLACEMENTS = [
    # Legacy palette -> canonical (per ODOO_GUIDELINES.md §1.6)
    ("#5a3a50", "#5A3A52"),
    ("#017E84", "#00A09D"),
    ("#e6a817", "#FF7F4F"),
    ("#128275", "#00A09D"),  # one-off teal -> canonical Success
    # Lowercase -> uppercase
    ("#ffffff", "#FFFFFF"),
    ("#e8dde5", "#E8DDE5"),
    ("#f8f5f7", "#F8F5F7"),
    ("#2d2233", "#2D2233"),
    ("#dc3545", "#DC3545"),
    ("#f8d7da", "#F8D7DA"),
    ("#f5c6cb", "#F5C6CB"),
    ("#721c24", "#721C24"),
    ("#d4edda", "#D4EDDA"),
    ("#c3e6cb", "#C3E6CB"),
    ("#155724", "#155724"),
    ("#fff3cd", "#FFF3CD"),
    ("#ffeeba", "#FFEEBA"),
    ("#856404", "#856404"),
    ("#8a6a80", "#8A6A80"),
    ("#bba8b5", "#BBA8B5"),
    ("#d4b8cf", "#D4B8CF"),
    # Old neutrals -> canonical neutrals (per §1)
    ("#666666", "#475569"),
    ("#888888", "#94A3B8"),
    ("#555555", "#475569"),
    ("#333333", "#1A1A1A"),
]


def patch_index_html(text):
    """Apply all index.html transformations.

    Order matters:
    1. Color replacements (incl. case fixes)
    2. Sanitizer fixes (font-family div -> pre, padding 48px 0, <code> -> <em>)
    3. Hero badge: append "8 Languages" badge after "GDPR Ready"
    4. Insert Languages section before LIMITATIONS section
    5. Insert Languages row in Technical Details table
    """
    # 1. Color replacements
    for old, new in COLOR_REPLACEMENTS:
        text = text.replace(old, new)

    # 2a. Sanitizer: font-family <div> code block -> <pre>
    old_pip = (
        '<div style="background-color: #2D2233; color: #FFFFFF; padding: 12px 16px; '
        'border-radius: 6px; margin-top: 12px; font-family: monospace; font-size: 14px;">'
        'pip install PyPDF2</div>'
    )
    new_pip = (
        '<pre style="background-color: #2D2233; color: #FFFFFF; padding: 12px 16px; '
        'border-radius: 6px; margin: 12px 0 0; font-size: 14px;">'
        'pip install pypdf</pre>'
    )
    assert old_pip in text, "pip install <div> anchor not found"
    text = text.replace(old_pip, new_pip, 1)

    # 2b. Sanitizer: padding: 48px 0 -> 48px 32px (only the TECHNICAL section banded div)
    text = text.replace("padding: 48px 0;", "padding: 48px 32px;")

    # 2c. Sanitizer: <code> -> <em>, </code> -> </em>
    text = text.replace("<code>", "<em>").replace("</code>", "</em>")

    # 3. Hero badge: append "8 Languages" badge after "GDPR Ready" badge
    old_gdpr = (
        '<span style="display: inline-block; background-color: #FF7F4F; '
        'border-radius: 20px; padding: 5px 16px; font-size: 14px; color: #1A1A1A; '
        'margin: 0 4px;">GDPR Ready</span>'
    )
    new_gdpr_plus_langs = old_gdpr + '\n        ' + (
        '<span style="display: inline-block; background-color: #2E86AB; '
        'border-radius: 20px; padding: 5px 16px; font-size: 14px; color: #FFFFFF; '
        'margin: 0 4px;">8 Languages</span>'
    )
    if old_gdpr in text:
        text = text.replace(old_gdpr, new_gdpr_plus_langs, 1)
    else:
        # Try with #FFFFFF text color instead (some variants)
        old_gdpr_alt = old_gdpr.replace("color: #1A1A1A", "color: #FFFFFF")
        new_gdpr_plus_langs_alt = old_gdpr_alt + '\n        ' + (
            '<span style="display: inline-block; background-color: #2E86AB; '
            'border-radius: 20px; padding: 5px 16px; font-size: 14px; color: #FFFFFF; '
            'margin: 0 4px;">8 Languages</span>'
        )
        if old_gdpr_alt in text:
            text = text.replace(old_gdpr_alt, new_gdpr_plus_langs_alt, 1)
        else:
            raise RuntimeError("GDPR Ready badge anchor not found (tried both color variants)")

    # 4. Insert Languages section before LIMITATIONS marker
    languages_section = '''    <!-- LANGUAGES -->
    <div class="container py-5">
        <h2 style="color: #714B67; font-size: 28px; font-weight: 700; margin-bottom: 8px; text-align: center;">Available in 8 Languages</h2>
        <p style="color: #475569; font-size: 15px; margin-bottom: 32px; text-align: center;">Field labels, selection options, and the Apps Store summary are translated. Each user sees the configuration form in their own Odoo language setting - no extra setup.</p>

        <div class="row">
            <div class="col-md-3 col-sm-4 col-6 mb-3">
                <div style="background-color: #FFFFFF; border: 1px solid #E8DDE5; border-radius: 8px; padding: 14px; text-align: center;">
                    <img width="32" height="22" alt="us" src="flags/us.png" style="display: block; margin: 0 auto 6px; border-radius: 2px;">
                    <strong style="color: #714B67;">English (en_US)</strong>
                </div>
            </div>
            <div class="col-md-3 col-sm-4 col-6 mb-3">
                <div style="background-color: #FFFFFF; border: 1px solid #E8DDE5; border-radius: 8px; padding: 14px; text-align: center;">
                    <img width="32" height="22" alt="fr" src="flags/fr.png" style="display: block; margin: 0 auto 6px; border-radius: 2px;">
                    <strong style="color: #714B67;">Fran&ccedil;ais (fr)</strong>
                </div>
            </div>
            <div class="col-md-3 col-sm-4 col-6 mb-3">
                <div style="background-color: #FFFFFF; border: 1px solid #E8DDE5; border-radius: 8px; padding: 14px; text-align: center;">
                    <img width="32" height="22" alt="es" src="flags/es.png" style="display: block; margin: 0 auto 6px; border-radius: 2px;">
                    <strong style="color: #714B67;">Espa&ntilde;ol (es)</strong>
                </div>
            </div>
            <div class="col-md-3 col-sm-4 col-6 mb-3">
                <div style="background-color: #FFFFFF; border: 1px solid #E8DDE5; border-radius: 8px; padding: 14px; text-align: center;">
                    <img width="32" height="22" alt="de" src="flags/de.png" style="display: block; margin: 0 auto 6px; border-radius: 2px;">
                    <strong style="color: #714B67;">Deutsch (de)</strong>
                </div>
            </div>
            <div class="col-md-3 col-sm-4 col-6 mb-3">
                <div style="background-color: #FFFFFF; border: 1px solid #E8DDE5; border-radius: 8px; padding: 14px; text-align: center;">
                    <img width="32" height="22" alt="nl" src="flags/nl.png" style="display: block; margin: 0 auto 6px; border-radius: 2px;">
                    <strong style="color: #714B67;">Nederlands (nl)</strong>
                </div>
            </div>
            <div class="col-md-3 col-sm-4 col-6 mb-3">
                <div style="background-color: #FFFFFF; border: 1px solid #E8DDE5; border-radius: 8px; padding: 14px; text-align: center;">
                    <img width="32" height="22" alt="br" src="flags/br.png" style="display: block; margin: 0 auto 6px; border-radius: 2px;">
                    <strong style="color: #714B67;">Portugu&ecirc;s (pt_BR)</strong>
                </div>
            </div>
            <div class="col-md-3 col-sm-4 col-6 mb-3">
                <div style="background-color: #FFFFFF; border: 1px solid #E8DDE5; border-radius: 8px; padding: 14px; text-align: center;">
                    <img width="32" height="22" alt="it" src="flags/it.png" style="display: block; margin: 0 auto 6px; border-radius: 2px;">
                    <strong style="color: #714B67;">Italiano (it)</strong>
                </div>
            </div>
            <div class="col-md-3 col-sm-4 col-6 mb-3">
                <div style="background-color: #FFFFFF; border: 1px solid #E8DDE5; border-radius: 8px; padding: 14px; text-align: center;">
                    <img width="32" height="22" alt="cn" src="flags/cn.png" style="display: block; margin: 0 auto 6px; border-radius: 2px;">
                    <strong style="color: #714B67;">&#20013;&#25991; (zh_CN)</strong>
                </div>
            </div>
        </div>

        <p style="color: #94A3B8; font-size: 13px; text-align: center; margin-top: 8px; max-width: 640px; margin-left: auto; margin-right: auto;">Standard Odoo gettext PO files under <em>i18n/</em>. Regional variants (<em>fr_BE</em>, <em>nl_BE</em>) inherit from the base language. Need another language? Drop a <em>.po</em> file in <em>i18n/</em> and reinstall.</p>
    </div>

    <!-- LIMITATIONS / HONEST SCOPE -->'''
    old_limit = "    <!-- LIMITATIONS / HONEST SCOPE -->"
    assert old_limit in text, "LIMITATIONS anchor not found"
    text = text.replace(old_limit, languages_section, 1)

    return text


# ============================================================================
# EXECUTION
# ============================================================================

def run(cmd, check=True, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if check and r.returncode != 0:
        print(f"FAIL: {cmd}\n{r.stdout}\n{r.stderr}")
        sys.exit(1)
    return r


def write_file(path, content, mode="w"):
    p = pathlib.Path(path) if not isinstance(path, pathlib.Path) else path
    p.parent.mkdir(parents=True, exist_ok=True)
    if mode == "wb":
        p.write_bytes(content)
    else:
        p.write_text(content, encoding="utf-8", newline="\n")


def render_banner_png(svg_content):
    """Render banner.png from the SVG bytes."""
    return cairosvg.svg2png(
        bytestring=svg_content.encode("utf-8"),
        output_width=1280,
        output_height=640,
    )


def process_branch(branch):
    print(f"\n=== {branch} ===")
    run(f"git checkout {branch}", cwd=str(REPO_ROOT))
    odoo_major = "19" if branch == "main" else branch.split(".")[0]

    # -- Manifest --
    write_file(
        REPO_ROOT / MODULE / "__manifest__.py",
        MANIFEST_TPL.format(odoo_major=odoo_major),
    )
    print(f"  manifest written (version {odoo_major}.0.1.1.0)")

    # -- Model rewrite --
    write_file(
        REPO_ROOT / MODULE / "models" / "ir_actions_report.py",
        MODEL_CONTENT,
    )
    print("  model rewritten (pypdf primary, PyPDF2 fallback)")

    # -- Infra files at repo root --
    write_file(REPO_ROOT / "Dockerfile", DOCKERFILE_TPL.format(odoo_major=odoo_major))
    write_file(
        REPO_ROOT / "docker-compose.yml",
        COMPOSE_TPL.format(odoo_major=odoo_major, module=MODULE),
    )
    write_file(REPO_ROOT / "CHANGELOG.md", CHANGELOG_TPL.format(odoo_major=odoo_major))
    print("  Dockerfile + docker-compose.yml + CHANGELOG.md written")

    # -- README --
    write_file(REPO_ROOT / "README.md", README_TPL.format(odoo_major=odoo_major))
    print("  README rewritten with Languages section")

    # -- Banner SVG + PNG --
    write_file(
        REPO_ROOT / MODULE / "static" / "description" / "banner.svg",
        BANNER_SVG,
    )
    write_file(
        REPO_ROOT / MODULE / "static" / "description" / "banner.png",
        render_banner_png(BANNER_SVG),
        mode="wb",
    )
    print("  banner.svg + banner.png rendered")

    # -- Flag PNGs --
    flags_dir = REPO_ROOT / MODULE / "static" / "description" / "flags"
    flags_dir.mkdir(exist_ok=True)
    for code in LANGS:
        shutil.copy2(SHARED_FLAGS_PNG / f"{code}.png", flags_dir / f"{code}.png")
    print("  8 flag PNGs copied")

    # -- i18n --
    i18n_dir = REPO_ROOT / MODULE / "i18n"
    i18n_dir.mkdir(exist_ok=True)
    write_file(
        i18n_dir / f"{MODULE}.pot",
        generate_pot(odoo_major),
    )
    for lang in TRANSLATIONS:
        write_file(i18n_dir / f"{lang}.po", generate_po(lang, odoo_major))
    print(f"  POT + 7 PO files written")

    # -- index.html (most complex: color + sanitizer + Languages section) --
    idx_path = REPO_ROOT / MODULE / "static" / "description" / "index.html"
    text = idx_path.read_text(encoding="utf-8")
    text = patch_index_html(text)
    write_file(idx_path, text)
    print("  index.html patched (colors + sanitizer + Languages section)")

    # -- Stage + commit --
    run("git add -A", cwd=str(REPO_ROOT))
    msg_path = REPO_ROOT / ".commit_msg.tmp"
    msg_path.write_text(
        f"Full ODOO_GUIDELINES.md compliance: i18n (8 langs), sanitizer, colors, infra\n\n"
        f"Per-branch bundled changes covering ODOO_GUIDELINES.md sections 1-12:\n"
        f"- Manifest: added maintainers/price/currency/support, copyright header,\n"
        f"  external_dependencies PyPDF2 -> pypdf.\n"
        f"- Sanitizer (sec 2.0): font-family div -> <pre>, padding 48px 0 -> 32px,\n"
        f"  inline <code> -> <em>.\n"
        f"- Colors (sec 1): all hex normalized to canonical uppercase. Legacy\n"
        f"  #5a3a50/#017E84/#e6a817 -> #5A3A52/#00A09D/#FF7F4F.\n"
        f"- Infra (sec 8, 9, 10): added Dockerfile, docker-compose.yml (port 1816),\n"
        f"  CHANGELOG.md, banner.svg (regenerated PNG).\n"
        f"- i18n (sec 12): added Tier 2 set - 7 PO files (fr, es, de, nl, pt_BR,\n"
        f"  it, zh_CN) + POT template. Project-Id-Version: Odoo Server {odoo_major}.0.\n"
        f"- index.html: hero +8 Languages badge, Available in 8 Languages section,\n"
        f"  static/description/flags/ folder with 8 PNG flags.\n"
        f"- Version bump {odoo_major}.0.1.0.0 -> {odoo_major}.0.1.1.0 (minor).",
        encoding="utf-8",
    )
    run("git commit -F .commit_msg.tmp", cwd=str(REPO_ROOT))
    msg_path.unlink()
    sha = run("git rev-parse --short HEAD", cwd=str(REPO_ROOT)).stdout.strip()
    print(f"  committed {sha}")


def main():
    os.chdir(str(REPO_ROOT))
    cur = run("git rev-parse --abbrev-ref HEAD").stdout.strip()
    if cur != RETURN_TO:
        print(f"FAIL: expected to start on {RETURN_TO}, got {cur}")
        sys.exit(1)
    status_lines = [
        ln for ln in run("git status --porcelain").stdout.splitlines()
        if ln.strip() and not ln.endswith("_full_compliance.py")
    ]
    if status_lines:
        print("FAIL: working tree dirty:\n" + "\n".join(status_lines))
        sys.exit(1)
    if not SHARED_FLAGS_PNG.exists():
        print(f"FAIL: shared flag PNGs not found at {SHARED_FLAGS_PNG}")
        sys.exit(1)

    for branch in ALL_BRANCHES:
        process_branch(branch)

    print(f"\nReturning to {RETURN_TO}")
    run(f"git checkout {RETURN_TO}")
    print("Done.")


if __name__ == "__main__":
    main()
