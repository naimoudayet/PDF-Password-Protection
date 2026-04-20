import io
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        PdfReader = PdfWriter = None
        _logger.warning(
            "PyPDF2/pypdf not installed. PDF password protection will not work."
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

        # Try to get partner from the first record
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
            return (
                (partner.phone or partner.mobile or "").replace(" ", "")
                or report.x_pdf_static_password
            )
        elif method == "email":
            return partner.email or report.x_pdf_static_password

        return report.x_pdf_static_password
