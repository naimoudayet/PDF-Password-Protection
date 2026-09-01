# Copyright 2026 Naim OUDAYET
# License LGPL-3
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# PDF/A identification lives in the document's XMP metadata as pdfaid:part /
# pdfaid:conformance. ISO 19005 forbids encryption outright, so a PDF that
# declares PDF/A must not be encrypted - doing so would strip its conformance
# and, for a Factur-X invoice, make the embedded XML unreadable by the
# recipient's accounts-payable system.
PDFA_MARKER = b"pdfaid"


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _link_invoice_documents(self, invoices_data):
        """Encrypt each invoice PDF immediately before it becomes an attachment.

        Accounting builds the PDF it mails through `_pre_render_qweb_pdf()`,
        never through `_render_qweb_pdf()`, so the base module's override never
        runs on this path and "Send & Print" would otherwise deliver an
        unencrypted invoice while the Print button delivers an encrypted one.

        This is deliberately the *last* step of the send pipeline - after
        `_prepare_invoice_pdf_report`, after
        `_hook_invoice_document_after_pdf_report_render` (where
        account_edi_ubl_cii embeds the Factur-X XML and may convert to PDF/A),
        and after both web-service hooks. Encrypting any earlier hands those
        steps a PDF they cannot read: `odoo.tools.pdf` resolves to PyPDF2,
        which raises DependencyError("PyCryptodome is required for AES
        algorithm") the moment it opens an AES-encrypted file.

        Because we work per invoice, each document is encrypted with its own
        partner's password - something the merged print path cannot do.
        """
        for invoice, invoice_data in invoices_data.items():
            values = invoice_data.get("pdf_attachment_values")
            if not values or not values.get("raw"):
                continue

            report = invoice_data.get("pdf_report")
            if not report or not report.x_pdf_password_enabled:
                continue

            if self._pdf_declares_pdfa(values["raw"]):
                self._skip_pdfa_invoice(invoice, report)
                continue

            encrypted = report._encrypt_pdf(values["raw"], [invoice.id])
            if encrypted:
                values["raw"] = encrypted
            else:
                # _encrypt_pdf already logged the cause; make the consequence
                # explicit rather than shipping a silently unprotected invoice.
                _logger.warning(
                    "Password protection is enabled on %r but no password "
                    "could be resolved for %s; it will be sent unencrypted.",
                    report.name,
                    invoice.display_name,
                )

        return super()._link_invoice_documents(invoices_data)

    @api.model
    def _generate_invoice_fallback_documents(self, invoices_data):
        """Encrypt the proforma Odoo falls back to when the invoice PDF fails.

        `account` creates that attachment directly rather than routing it
        through `_link_invoice_documents`, so it would otherwise be the one
        document in the whole send flow that reaches the customer unprotected.
        It carries the same customer data as the invoice it stands in for.

        The values do not exist until super() has prepared them, so the
        attachment is encrypted in place once it has been created.
        """
        res = super()._generate_invoice_fallback_documents(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            attachment = invoice_data.get("proforma_pdf_attachment")
            if not attachment or not attachment.raw:
                continue

            report = invoice_data.get("pdf_report")
            if not report or not report.x_pdf_password_enabled:
                continue

            if self._pdf_declares_pdfa(attachment.raw):
                self._skip_pdfa_invoice(invoice, report)
                continue

            encrypted = report._encrypt_pdf(attachment.raw, [invoice.id])
            if encrypted:
                attachment.write({"raw": encrypted})
            else:
                _logger.warning(
                    "Password protection is enabled on %r but no password could "
                    "be resolved for the pro-forma standing in for %s; it will "
                    "be sent unencrypted.",
                    report.name,
                    invoice.display_name,
                )
        return res

    @api.model
    def _pdf_declares_pdfa(self, raw):
        """True when the rendered PDF identifies itself as PDF/A.

        Checked against the produced bytes rather than by re-deriving Odoo's
        own FR/DE + e-invoicing-format conditions, so this keeps working if
        those conditions change upstream. Note that account_edi_ubl_cii embeds
        a Factur-X XML in *every* invoice PDF but only converts to PDF/A for
        configured e-invoicing setups - so this deliberately keys on the
        conformance claim, not on the presence of the XML, which would
        otherwise disable encryption for everyone.
        """
        return PDFA_MARKER in (raw or b"")

    @api.model
    def _skip_pdfa_invoice(self, invoice, report):
        """Leave a PDF/A e-invoice alone, and say so where the user will look."""
        _logger.warning(
            "%s is a PDF/A e-invoice; skipping password protection configured "
            "on %r. Encrypting it would break PDF/A conformance and make the "
            "embedded e-invoicing XML unreadable for the recipient.",
            invoice.display_name,
            report.name,
        )
        invoice.message_post(
            body=self.env._(
                "This invoice was sent without password protection: it is a "
                "PDF/A e-invoice, and encrypting it would break PDF/A "
                "conformance and make the embedded e-invoicing XML unreadable "
                "for the recipient."
            )
        )
