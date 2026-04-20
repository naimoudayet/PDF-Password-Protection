{
    "name": "PDF Password Protection",
    "version": "18.0.1.0.0",
    "category": "Extra Tools",
    "summary": "Encrypt PDF reports with passwords - static or dynamic (partner VAT, phone, email)",
    "description": """PDF Password Protection - encrypt any Odoo PDF report with passwords.
Static password or dynamic from partner fields (VAT, phone, email).
GDPR-friendly. Works with all QWeb PDF reports.""",
    "author": "Naim OUDAYET",
    "website": "https://www.oudayet.com",
    "license": "LGPL-3",
    "depends": ["base"],
    "external_dependencies": {"python": ["PyPDF2"]},
    "data": [
        "views/ir_actions_report_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
