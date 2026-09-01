# Copyright 2026 Naim OUDAYET
# License LGPL-3
from odoo import fields, models


class AccountMoveSendWizard(models.TransientModel):
    _inherit = "account.move.send.wizard"

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

    def _compute_x_pdf_password_active(self):
        for wizard in self:
            report = wizard.pdf_report_id or wizard._get_default_pdf_report_id(
                wizard.move_id
            )
            wizard.x_pdf_password_active = bool(
                report and report.x_pdf_password_enabled
            )

    def _get_sending_settings(self):
        """Carry the choice through account's own custom-settings channel.

        `_get_default_sending_settings` merges whatever the wizard puts here,
        so this needs no hook of its own - and the batch and cron paths, which
        have no wizard, fall back to the default in that method.
        """
        settings = super()._get_sending_settings()
        settings["pdf_notice_in_email"] = self.x_pdf_notice_in_email
        return settings

