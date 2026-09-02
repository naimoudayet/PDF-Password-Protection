# Copyright 2026 Naim OUDAYET
# License LGPL-3
{
    "name": "PDF Password Protection",
    "summary": "Encrypt PDF reports with AES-256 - static or dynamic passwords "
    "(partner VAT, phone, email)",
    "description": "PDF Password Protection - encrypt any Odoo PDF report with passwords. "
    "AES-256 by default (AES-128 and legacy RC4-128 also selectable). "
    "Static password or dynamic from partner fields (VAT, phone, email). "
    "GDPR-friendly. Works with all QWeb PDF reports. "
    "If you also email invoices, add the free companion module "
    "'PDF Password Protection for Invoices', which extends the "
    "same settings to the copy Accounting sends out.",
    "version": "17.0.2.0.0",
    "category": "Extra Tools",
    "website": "https://www.oudayet.com",
    "author": "Naim OUDAYET",
    "maintainers": ["naimoudayet"],
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": ["base"],
    # Odoo 17 ships PyPDF2 1.26, which exposes only PdfFileReader /
    # PdfFileWriter and cannot do AES at any setting. This module needs the
    # modern pypdf API, so unlike the 18.0/19.0 branches the dependency is
    # real here and is declared: Odoo then refuses the install with a clear
    # message instead of failing later on an import.
    "external_dependencies": {"python": ["pypdf"]},
    "data": [
        "views/ir_actions_report_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "price": 0,
    "currency": "USD",
    "support": "contact@oudayet.com",
}
