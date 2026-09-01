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
    "version": "19.0.2.0.0",
    "category": "Extra Tools",
    "website": "https://www.oudayet.com",
    "author": "Naim OUDAYET",
    "maintainers": ["naimoudayet"],
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": ["base"],
    # No external_dependencies on purpose: Odoo already ships one of
    # pypdf / PyPDF2 (odoo.tools.pdf requires it), so declaring 'pypdf' here
    # made the module refuse to install on any deployment that only has
    # PyPDF2 - which is the default on the official odoo:19 image. The code
    # detects the backend at runtime and warns if AES is unavailable.
    "data": [
        "views/ir_actions_report_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "price": 0,
    "currency": "USD",
    "support": "contact@oudayet.com",
}
