# Copyright 2026 Naim OUDAYET
# License LGPL-3
import logging

from markupsafe import Markup

from odoo import api, models

_logger = logging.getLogger(__name__)

# PDF/A identification lives in the document's XMP metadata as pdfaid:part /
# pdfaid:conformance. ISO 19005 forbids encryption outright, so a PDF that
# declares PDF/A must not be encrypted - doing so would strip its conformance
# and, for a Factur-X invoice, make the embedded XML unreadable by the
# recipient's accounts-payable system.
PDFA_MARKER = b"pdfaid"

PDF_MAGIC = b"%PDF"


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    # ------------------------------------------------------------------
    # Outgoing email
    # ------------------------------------------------------------------

    def _get_default_sending_settings(self, move, from_cron=False, **custom_settings):
        """Default the notice on for the paths that never show a wizard.

        The single-invoice wizard passes its checkbox through account's own
        custom-settings channel; batch sends and the cron have no wizard, so
        they fall back to on here.
        """
        settings = super()._get_default_sending_settings(
            move, from_cron=from_cron, **custom_settings
        )
        if "pdf_notice_in_email" in custom_settings:
            settings["pdf_notice_in_email"] = custom_settings["pdf_notice_in_email"]
        else:
            settings.setdefault("pdf_notice_in_email", True)
        return settings

    @api.model
    def _get_mail_params(self, move, move_data):
        """Encrypt the invoice on its way into the customer's email.

        Accounting builds the PDF it mails through `_pre_render_qweb_pdf()`,
        never `_render_qweb_pdf()`, so the base module's override never runs on
        this path and the customer would otherwise receive an unprotected
        invoice while the Print button produced a protected one.

        This hook is chosen deliberately over encrypting the attachment as it
        is stored. Core builds the mail's attachments here as ``(name, bytes)``
        tuples - a *copy* of the stored file - so protecting them here leaves
        `invoice_pdf_report_id` itself readable. Your own people can then open
        a sent invoice from the record without hunting down the customer's VAT
        number, while what actually left the building is locked.
        """
        params = super()._get_mail_params(move, move_data)

        report = move_data.get("pdf_report")
        if not report or not report.x_pdf_password_enabled:
            return params

        attachments = params.get("attachments") or []
        if not attachments:
            return params

        protected = []
        any_encrypted = False
        for name, raw in attachments:
            out = self._protect_outgoing(move, report, name, raw)
            any_encrypted = any_encrypted or out is not raw
            protected.append((name, out))
        params["attachments"] = protected

        # Only once something actually came out locked. A PDF/A e-invoice is
        # skipped and an unresolved password passes through, and a notice on
        # either would promise the reader a protection they did not get.
        if any_encrypted and move_data.get("pdf_notice_in_email", True):
            params["body"] = self._prefix_password_notice(params.get("body"), report)
        return params

    @api.model
    def _prefix_password_notice(self, body, report):
        """Put the report's own notice above the email body.

        The wording lives on the report as an editable, translatable field, so
        this never composes a sentence of its own - and in particular never
        writes a password into the message carrying the document.
        """
        notice = report._pdf_email_notice_html()
        if not notice:
            return body
        # Both halves are already HTML. Concatenating them as plain strings
        # produces a str, which Odoo then escapes on the way into the message -
        # the customer would see the markup instead of the sentence.
        return Markup(notice) + Markup(body or "")

    @api.model
    def _protect_outgoing(self, move, report, name, raw):
        """Return `raw` encrypted, or unchanged when it must not be."""
        if not raw or not raw.startswith(PDF_MAGIC):
            # The electronic-invoicing XML travels alongside the PDF; it is not
            # ours to touch and the recipient's software must be able to read it.
            return raw

        if self._pdf_declares_pdfa(raw):
            self._skip_pdfa_invoice(move, report)
            return raw

        encrypted = report._encrypt_pdf(raw, [move.id])
        if encrypted:
            return encrypted

        _logger.warning(
            "Password protection is enabled on %r but no password could be "
            "resolved for %s; %s is being emailed unencrypted.",
            report.name,
            move.display_name,
            name,
        )
        return raw

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @api.model
    def _pdf_declares_pdfa(self, raw):
        """True when the PDF identifies itself as PDF/A.

        Checked against the produced bytes rather than by re-deriving Odoo's
        own FR/DE + e-invoicing-format conditions, so this keeps working if
        those conditions change upstream. Note that account_edi_ubl_cii embeds
        a Factur-X XML in *every* invoice PDF but only converts to PDF/A for
        configured e-invoicing setups - so this deliberately keys on the
        conformance claim, not on the presence of the XML, which would
        otherwise disable protection for everyone.
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


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_invoice_legal_documents(self, filetype, allow_fallback=False):
        """Encrypt the invoice the portal hands to the customer.

        The portal's Download button and the backend zip export both read the
        stored file through here rather than re-rendering it, so this is where
        that copy crosses the boundary. Encrypting at this point rather than at
        rest is what lets your own staff preview the same invoice without a
        password.
        """
        doc = super()._get_invoice_legal_documents(
            filetype, allow_fallback=allow_fallback
        )
        return self._protect_legal_document(doc)

    def _get_invoice_legal_documents_all(self, allow_fallback=False):
        docs = super()._get_invoice_legal_documents_all(allow_fallback=allow_fallback)
        return [self._protect_legal_document(d) for d in (docs or [])]

    def _protect_legal_document(self, doc):
        """Encrypt one {'filename', 'content', ...} entry on its way out."""
        self.ensure_one()
        if not doc or not doc.get("content"):
            return doc

        report = self.env["ir.actions.report"]._get_report("account.account_invoices")
        if not report or not report.x_pdf_password_enabled:
            return doc

        raw = doc["content"]
        if not raw.startswith(PDF_MAGIC):
            return doc
        if self.env["account.move.send"]._pdf_declares_pdfa(raw):
            return doc

        encrypted = report._encrypt_pdf(raw, [self.id])
        if encrypted:
            doc = dict(doc, content=encrypted)
        return doc
