# Copyright 2026 Naim OUDAYET
# License LGPL-3
import logging

from markupsafe import Markup

from odoo import _, api, models

_logger = logging.getLogger(__name__)

# PDF/A identification lives in the document's XMP metadata as pdfaid:part /
# pdfaid:conformance. ISO 19005 forbids encryption outright, so a PDF that
# declares PDF/A must not be encrypted - doing so would strip its conformance
# and, for a Factur-X invoice, make the embedded XML unreadable by the
# recipient's accounts-payable system.
PDFA_MARKER = b"pdfaid"

PDF_MAGIC = b"%PDF"


class AccountMoveSend(models.TransientModel):
    # On 17.0 account.move.send IS the wizard, a TransientModel. The 18.0 split
    # into an abstract account.move.send service plus an account.move.send.wizard
    # transient does not exist yet, so extending it as an AbstractModel here
    # would try to turn a transient model into a permanent one.
    _inherit = "account.move.send"

    # ------------------------------------------------------------------
    # Outgoing email
    # ------------------------------------------------------------------

    def _get_wizard_values(self):
        """Carry the notice choice into every move_data.

        On 17.0 there is no `_get_sending_settings` / `_get_default_sending_settings`
        pair. `_process_send_and_print` builds each move_data from this dict when a
        wizard is present, and `action_send_and_print` stores the same dict on
        `move.send_and_print_values` for the asynchronous path - so overriding here
        covers the wizard and the cron in one place.
        """
        values = super()._get_wizard_values()
        values["pdf_notice_in_email"] = self.x_pdf_notice_in_email
        return values

    def _prepare_invoice_pdf_report(self, invoice, invoice_data):
        """Render the invoice unencrypted, so core can still post-process it.

        On 17.0 the send pipeline renders through `_render_qweb_pdf`, which the
        base module encrypts. `account_edi_ubl_cii` then reopens those bytes to
        embed the Factur-X XML and raises on an encrypted file, so Send & Print
        died with a server error the moment protection was switched on.

        18.0 and 19.0 avoid this by rendering through `_pre_render_qweb_pdf`,
        which the base module leaves alone. Here the same separation is asked
        for explicitly: the stored copy stays readable and `_get_mail_params`
        encrypts what actually leaves.
        """
        return super(
            AccountMoveSend, self.with_context(no_pdf_defer_encryption=True)
        )._prepare_invoice_pdf_report(invoice, invoice_data)

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

        # 17.0 has no per-wizard report choice, so move_data carries no
        # "pdf_report"; the invoice report is always account.account_invoices.
        report = self.env["ir.actions.report"]._get_report("account.account_invoices")
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
            body=_(
                "This invoice was sent without password protection: it is a "
                "PDF/A e-invoice, and encrypting it would break PDF/A "
                "conformance and make the embedded e-invoicing XML unreadable "
                "for the recipient."
            )
        )


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_invoice_legal_documents(self):
        """Encrypt the copy the portal hands to the customer.

        17.0 returns `ir.attachment` records here, not the {filename, content}
        dicts of 18.0/19.0 - and when the invoice already has a stored PDF it
        returns that very record. Encrypting it in place would lock the copy
        kept on the invoice and force your own staff to type the customer's
        password to preview it, which is exactly what this module avoids
        everywhere else.

        So an unsaved copy carrying the encrypted bytes is returned instead.
        Core already hands an unsaved record back on its own pro-forma branch,
        so the portal controller is happy with one.
        """
        attachments = super()._get_invoice_legal_documents()
        if not attachments:
            return attachments

        report = self.env["ir.actions.report"]._get_report("account.account_invoices")
        if not report or not report.x_pdf_password_enabled:
            return attachments

        Send = self.env["account.move.send"]
        out = self.env["ir.attachment"]
        for att in attachments:
            raw = att.raw or b""
            if (
                raw.startswith(PDF_MAGIC)
                and not Send._pdf_declares_pdfa(raw)
                and not (att.mimetype or "").endswith("xml")
            ):
                encrypted = report._encrypt_pdf(raw, self.ids)
                if encrypted:
                    out |= self.env["ir.attachment"].new(
                        {
                            "raw": encrypted,
                            "name": att.name,
                            "mimetype": att.mimetype or "application/pdf",
                            "res_model": self._name,
                            "res_id": self.id,
                        }
                    )
                    continue
            out |= att
        return out
