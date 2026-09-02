# Copyright 2026 Naim OUDAYET
# License LGPL-3
from odoo import api, fields, models


class AccountMoveSendWizard(models.TransientModel):
    _inherit = "account.move.send"

    x_pdf_notice_in_email = fields.Boolean(
        string="Explain the password in the email",
        default=True,
        help="Adds the notice configured on the invoice report above the "
        "message, so the customer is not left with a file that will not open. "
        "It is only added when the document really was protected.",
    )
    x_pdf_password_active = fields.Boolean(
        string="Password Protection Active",
        compute="_compute_x_pdf_password_active",
        help="Whether the selected invoice report has password protection on; "
        "used to keep the option out of the way for everyone else.",
    )

    @api.depends("move_ids")
    def _compute_x_pdf_password_active(self):
        """17.0 has no per-wizard report field: the invoice report is fixed."""
        report = self.env["ir.actions.report"]._get_report("account.account_invoices")
        active = bool(report and report.x_pdf_password_enabled)
        for wizard in self:
            wizard.x_pdf_password_active = active
