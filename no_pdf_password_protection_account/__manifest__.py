# Copyright 2026 Naim OUDAYET
# License LGPL-3
{
    "name": "PDF Password Protection for Invoices",
    "summary": "Extend PDF password protection to the accounting Send & Print flow",
    "description": "Bridge between PDF Password Protection and Accounting. "
                   "Odoo builds the invoice PDF it emails through a different "
                   "code path than the Print button, which would otherwise "
                   "deliver an unencrypted invoice to the customer. This module "
                   "closes that gap and gives every document its own recipient's "
                   "password. Requires the free module 'PDF Password "
                   "Protection', which is where the password source and "
                   "encryption strength are configured; install that one first "
                   "and this add-on installs itself automatically once "
                   "Accounting is present. It has no settings of its own.",
    "version": "19.0.1.0.0",
    "category": "Extra Tools",
    "website": "https://www.oudayet.com",
    "author": "Naim OUDAYET",
    "maintainers": ["naimoudayet"],
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "auto_install": True,
    "depends": ["no_pdf_password_protection", "account"],
    "data": [
        "views/ir_actions_report_views.xml",
        "views/account_move_send_wizard_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "price": 0,
    "currency": "USD",
    "support": "contact@oudayet.com",
}
