# Copyright 2026 Naim OUDAYET
# License LGPL-3
import inspect
import io
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Import pypdf / PyPDF2 directly rather than through odoo.tools.pdf.
# That shim deliberately resolves PyPDF2 2.x *first* ("keep pypdf2 2.x first
# so noble uses that rather than pypdf 4.0"), and PyPDF2's encrypt() has no
# `algorithm` argument - it can only ever emit RC4-128. Preferring pypdf here
# is what makes AES available at all.
try:
    from pypdf import PdfReader, PdfWriter

    PDF_BACKEND = "pypdf"
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter

        PDF_BACKEND = "PyPDF2"
    except ImportError:
        PdfReader = PdfWriter = None
        PDF_BACKEND = None
        _logger.warning(
            "Neither pypdf nor PyPDF2 is importable. PDF password protection "
            "is inactive; reports render unencrypted."
        )

# Odoo's own dependency is satisfied by either library, so the module stays
# installable everywhere and degrades loudly instead of refusing to install.
AES_ALGORITHMS = {"aes256": "AES-256", "aes128": "AES-128"}

# ISO 32000 caps the standard security handler's password at 127 bytes.
# Longer passwords are silently truncated by readers, and different readers
# have historically truncated differently - so refuse rather than ship a file
# the recipient may not be able to open.
MAX_PASSWORD_BYTES = 127

DIGITS = "0123456789"


def backend_supports_aes():
    """True when the installed backend accepts ``encrypt(algorithm=...)``.

    pypdf gained the ``algorithm`` keyword in 3.1. PyPDF2 never had it and is
    therefore permanently limited to RC4-128.
    """
    if PdfWriter is None:
        return False
    try:
        return "algorithm" in inspect.signature(PdfWriter.encrypt).parameters
    except (TypeError, ValueError):
        return False


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
    x_pdf_encryption_algo = fields.Selection(
        [
            ("aes256", "AES-256 (recommended)"),
            ("aes128", "AES-128"),
            ("rc4_128", "RC4-128 (legacy readers only)"),
        ],
        string="Encryption Algorithm",
        default="aes256",
        help="AES-256 is the current standard and is readable by Acrobat 9+ "
        "and every modern PDF viewer. RC4-128 is retained only for very old "
        "readers; it is cryptographically broken and should not be used for "
        "confidential documents.",
    )
    x_pdf_protect_stored_copy = fields.Boolean(
        string="Also Protect the Copy Kept in Odoo",
        default=False,
        help="By default only documents that leave Odoo are encrypted - what "
        "you print, email, or publish on the portal. The copy Odoo archives on "
        "the record stays readable so your own staff can preview it without "
        "typing a password; it is already covered by Odoo's access rights. "
        "Turn this on to encrypt that archived copy too. "
        "Emailed invoices are an exception: Odoo sends the very file it "
        "stores, so that copy is always encrypted whatever this is set to.",
    )
    x_pdf_aes_unavailable = fields.Boolean(
        string="AES Unavailable On This Server",
        compute="_compute_x_pdf_aes_unavailable",
        help="True when the installed PDF library cannot produce AES, so "
        "encryption silently falls back to RC4-128.",
    )

    def _compute_x_pdf_aes_unavailable(self):
        # Server capability, not record data - same answer for every row.
        unavailable = not backend_supports_aes()
        for report in self:
            report.x_pdf_aes_unavailable = unavailable

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Encrypt the generated PDF when password protection is enabled."""
        report = self._get_report(report_ref)

        # Checked before rendering so a mistaken batch fails instantly rather
        # than after wkhtmltopdf has done the expensive work.
        if report.x_pdf_password_enabled and not self._pdf_encryption_suppressed():
            report._check_batch_shares_one_password(res_ids)

        result = super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

        if PdfWriter is None or not report.x_pdf_password_enabled:
            return result
        if self._pdf_encryption_suppressed():
            return result

        pdf_content, content_type = result
        if content_type != "pdf":
            return result

        encrypted = report._encrypt_pdf(pdf_content, res_ids)
        return (encrypted, content_type) if encrypted else result

    def _prepare_pdf_report_attachment_vals_list(self, report, streams):
        """Encrypt the copy Odoo archives on the record.

        Core writes this attachment *inside* `_render_qweb_pdf`, before our
        override sees the merged bytes, so without this the download would be
        encrypted while the archived copy - the one the chatter shows and mail
        templates attach - stayed plaintext.

        The vals are keyed per res_id, so each archived document gets its own
        partner's password rather than the first record's.

        Off by default: see x_pdf_protect_stored_copy.
        """
        vals_list = super()._prepare_pdf_report_attachment_vals_list(report, streams)

        if PdfWriter is None or not report.x_pdf_password_enabled:
            return vals_list
        if not report.x_pdf_protect_stored_copy:
            # The archived copy is what staff preview from the chatter. Every
            # route that leaves Odoo re-encrypts on the way out, so leaving it
            # readable costs nothing in delivered protection and saves an
            # authorised colleague from typing a password to look at a document
            # they can already open the record for.
            return vals_list
        if self._pdf_encryption_suppressed():
            return vals_list

        for vals in vals_list:
            encrypted = report._encrypt_pdf(vals.get("raw"), [vals.get("res_id")])
            if encrypted:
                vals["raw"] = encrypted
        return vals_list

    @api.model
    def _pdf_encryption_suppressed(self):
        """True when the caller needs a PDF it can still process itself.

        `snailmail` renders the report and hands the bytes to a postal
        printing provider, which cannot open an encrypted file - the letter
        would fail or arrive blank. It always sets `snailmail_layout` in the
        context (the value is a layout flag, so test for the key), which makes
        it a reliable signal.
        """
        if "snailmail_layout" in self.env.context:
            _logger.info(
                "Skipping PDF password protection: rendering for snailmail, "
                "which must hand a readable file to the postal provider."
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------

    def _check_batch_shares_one_password(self, res_ids):
        """Refuse to merge records that would resolve to different passwords.

        Core merges a multi-record print into a single PDF, which can carry
        only one password. With a dynamic source that password comes from the
        first record - so the file would open for one customer and expose
        every other customer's document inside it, while those customers could
        not open it at all.
        """
        self.ensure_one()
        if self.x_pdf_password_method == "static":
            return
        if not res_ids or len(res_ids) < 2:
            return

        passwords = {self._get_pdf_password(self, [res_id]) for res_id in res_ids}
        if len(passwords) > 1:
            raise UserError(
                self.env._(
                    "These records do not share the same password.\n\n"
                    "Printing them together would merge them into a single "
                    "file that can carry only one password - it would open "
                    "for one recipient and expose the other documents to "
                    "them, while the others could not open it at all.\n\n"
                    "Print them one at a time, or use Send & Print, which "
                    "encrypts each document separately."
                )
            )

    def _encrypt_pdf(self, pdf_content, res_ids=None):
        """Return ``pdf_content`` encrypted, or None when it must pass through.

        Kept separate from the render override so any other code path that
        produces a PDF for this report can reuse the exact same password and
        algorithm resolution.
        """
        self.ensure_one()
        if PdfWriter is None or not pdf_content:
            return None

        password = self._get_pdf_password(self, res_ids)
        if not password:
            return None

        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            _logger.error(
                "Report %r resolved a password longer than %d bytes, which "
                "exceeds the PDF specification. The document is left "
                "unencrypted rather than shipped with a password readers may "
                "truncate inconsistently.",
                self.name,
                MAX_PASSWORD_BYTES,
            )
            return None

        algorithm = self._resolve_pdf_algorithm()
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            if algorithm:
                writer.encrypt(password, algorithm=algorithm)
            else:
                writer.encrypt(password)

            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except Exception as e:
            _logger.error("Failed to encrypt PDF for report %s: %s", self.name, e)
            return None

    def _resolve_pdf_algorithm(self):
        """Map the configured algorithm onto the backend's ``encrypt`` kwarg.

        Returns None when the call must omit ``algorithm`` entirely, which
        means RC4-128 - either because that was asked for, or because the
        installed backend cannot do anything else.
        """
        self.ensure_one()
        choice = self.x_pdf_encryption_algo or "aes256"
        if choice == "rc4_128":
            return None
        if not backend_supports_aes():
            _logger.warning(
                "Report %r requests %s but the installed PDF backend (%s) only "
                "supports RC4-128. Falling back to RC4-128. Install a modern "
                "pypdf ('pip install pypdf') to enable AES.",
                self.name,
                choice,
                PDF_BACKEND,
            )
            return None
        return AES_ALGORITHMS[choice]

    # ------------------------------------------------------------------
    # Password resolution
    # ------------------------------------------------------------------

    def _get_pdf_password(self, report, res_ids):
        """Get the password based on the configured method."""
        method = report.x_pdf_password_method

        if method == "static":
            return report.x_pdf_static_password

        if not res_ids:
            return report.x_pdf_static_password or None

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
            # res.partner.mobile was dropped in Odoo 19 - use getattr so the
            # same codebase works on v16/v17/v18 (mobile present) and v19+
            # (mobile absent) without AttributeError.
            #
            # Reduced to digits only: a recipient cannot be expected to guess
            # whether their number was stored as "+216 71 123 456",
            # "(216) 71-123-456" or "216.71.123.456". Digits-only is the one
            # form we can state plainly in the documentation.
            raw = partner.phone or getattr(partner, "mobile", False) or ""
            digits = "".join(ch for ch in raw if ch in DIGITS)
            return digits or report.x_pdf_static_password
        elif method == "email":
            return partner.email or report.x_pdf_static_password

        return report.x_pdf_static_password
