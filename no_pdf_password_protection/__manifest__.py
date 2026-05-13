# Copyright 2026 Naim OUDAYET
# License LGPL-3
{
    "name": "PDF Password Protection",
    "summary": "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)",
    "description": "PDF Password Protection - encrypt any Odoo PDF report with passwords. "
                   "Static password or dynamic from partner fields (VAT, phone, email). "
                   "GDPR-friendly. Works with all QWeb PDF reports.",
    "version": "19.0.1.2.0",
    "category": "Extra Tools",
    "website": "https://www.oudayet.com",
    "author": "Naim OUDAYET",
    "maintainers": ["naimoudayet"],
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": ["base"],
    "external_dependencies": {"python": ["pypdf"]},
    "data": [
        "views/ir_actions_report_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "price": 0,
    "currency": "USD",
    "support": "contact@oudayet.com",
}
