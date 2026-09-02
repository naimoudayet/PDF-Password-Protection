# Copyright 2026 Naim OUDAYET
# License LGPL-3
from odoo import _, fields, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    x_pdf_email_notice = fields.Html(
        string="Password Notice for Emails",
        translate=True,
        # 17.0 has no 'email_outgoing' sanitize profile; the default is fine
        # for a short notice paragraph.
        sanitize=True,
        help="Put above the message when a protected invoice is emailed, so "
        "the customer is not left with a file that will not open. Leave it "
        "empty to use the standard sentence, which is already translated into "
        "every language this module supports. Write your own here to replace "
        "it - and never put the password itself in this text if you use a "
        "fixed password, since it would travel in the same message.",
    )

    def _pdf_email_notice_html(self):
        """The wording to prepend, falling back to the translated default."""
        self.ensure_one()
        notice = self.x_pdf_email_notice
        if notice and notice.strip():
            return notice
        # The literal has to sit inside the _() call: gettext extraction reads
        # the source, so a module-level constant passed in as a variable would
        # never reach the .pot and would stay English in every language.
        #
        # Resolved here rather than as a field default for the same family of
        # reason - a default on a translatable field is written once, in the
        # language the record happened to be created in.
        return _(
            "<p>The attached document is password protected. Please open it "
            "with the password we have shared with you.</p>"
        )
