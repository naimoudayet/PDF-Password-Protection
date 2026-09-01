import io
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase

from odoo.addons.no_pdf_password_protection_account.models import (
    account_move_send as mod,
)

# Mirror the base module's import order (pypdf first): it emits AES-256 by
# default and PyPDF2 2.x cannot verify a /V 5 encryption dictionary.
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover
    from PyPDF2 import PdfReader, PdfWriter


def _blank_pdf(pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _super_target(record, method):
    """The class our override's super() call resolves to."""
    mro = type(record).__mro__
    idx = next(
        i for i, c in enumerate(mro)
        if "no_pdf_password_protection_account" in (getattr(c, "__module__", "") or "")
    )
    return next(c for c in mro[idx + 1:] if method in c.__dict__)


class TestOutgoingInvoice(TransactionCase):
    """The invoice is protected on its way out, not while it sits on the record.

    Core hands the mailer `(name, bytes)` tuples - a copy of the stored file -
    so encrypting there leaves invoice_pdf_report_id readable. That is what
    lets an accountant open a sent invoice without looking up a VAT number.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("account.account_invoices")
        cls.Send = cls.env["account.move.send"]

    def setUp(self):
        super().setUp()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "Secret123",
            "x_pdf_encryption_algo": "aes256",
        })

    def _move_for(self, name, vat=False):
        partner = self.env["res.partner"].create({"name": name, "vat": vat})
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
        })

    def _mail_params(self, move, attachments):
        parent = _super_target(self.Send, "_get_mail_params")
        with patch.object(parent, "_get_mail_params",
                          return_value={"attachments": list(attachments)}):
            return self.Send._get_mail_params(move, {"pdf_report": self.report})

    # ------------------------------------------------------------ the email

    def test_01_emailed_invoice_is_encrypted(self):
        """The regression this module exists for."""
        move = self._move_for("Acme", "ACME-VAT")
        source = _blank_pdf()
        out = self._mail_params(move, [("INV.pdf", source)])["attachments"]
        self.assertNotEqual(out[0][1], source, "the customer was emailed a plain PDF")
        self.assertTrue(PdfReader(io.BytesIO(out[0][1])).is_encrypted)

    def test_02_emailed_invoice_opens_with_the_configured_password(self):
        move = self._move_for("Acme", "ACME-VAT")
        out = self._mail_params(move, [("INV.pdf", _blank_pdf())])["attachments"]
        self.assertTrue(PdfReader(io.BytesIO(out[0][1])).decrypt("Secret123"))

    def test_03_each_invoice_uses_its_own_partner_password(self):
        self.report.x_pdf_password_method = "vat"
        a = self._move_for("Alpha", "VAT-ALPHA")
        b = self._move_for("Beta", "VAT-BETA")
        raw_a = self._mail_params(a, [("a.pdf", _blank_pdf())])["attachments"][0][1]
        raw_b = self._mail_params(b, [("b.pdf", _blank_pdf())])["attachments"][0][1]
        self.assertTrue(PdfReader(io.BytesIO(raw_a)).decrypt("VAT-ALPHA"))
        self.assertTrue(PdfReader(io.BytesIO(raw_b)).decrypt("VAT-BETA"))
        self.assertEqual(PdfReader(io.BytesIO(raw_a)).decrypt("VAT-BETA"), 0)

    def test_04_filename_is_preserved(self):
        move = self._move_for("Acme", "ACME-VAT")
        out = self._mail_params(move, [("INV_2026_0001.pdf", _blank_pdf())])["attachments"]
        self.assertEqual(out[0][0], "INV_2026_0001.pdf")

    def test_05_the_einvoicing_xml_is_not_touched(self):
        """It travels beside the PDF and the recipient's software must read it."""
        move = self._move_for("Acme", "ACME-VAT")
        xml = b"<?xml version='1.0'?><Invoice/>"
        out = self._mail_params(move, [("factur-x.xml", xml)])["attachments"]
        self.assertEqual(out[0][1], xml)

    def test_06_disabled_report_sends_plain(self):
        self.report.x_pdf_password_enabled = False
        move = self._move_for("Acme", "ACME-VAT")
        source = _blank_pdf()
        out = self._mail_params(move, [("INV.pdf", source)])["attachments"]
        self.assertEqual(out[0][1], source)

    def test_07_unresolvable_password_sends_the_file_intact(self):
        """Never corrupt a document we could not protect."""
        self.report.write({"x_pdf_password_method": "vat",
                           "x_pdf_static_password": False})
        move = self._move_for("NoVat", False)
        source = _blank_pdf()
        out = self._mail_params(move, [("INV.pdf", source)])["attachments"]
        self.assertEqual(out[0][1], source)

    def test_08_no_attachments_does_not_crash(self):
        move = self._move_for("Acme", "ACME-VAT")
        self.assertEqual(self._mail_params(move, [])["attachments"], [])

    def test_09_page_count_preserved(self):
        move = self._move_for("Acme", "ACME-VAT")
        out = self._mail_params(move, [("INV.pdf", _blank_pdf(pages=3))])["attachments"]
        reader = PdfReader(io.BytesIO(out[0][1]))
        reader.decrypt("Secret123")
        self.assertEqual(len(reader.pages), 3)

    # ------------------------------------------------- the copy that stays

    def test_10_the_stored_copy_is_left_readable(self):
        """The whole point: staff open a sent invoice without a password.

        The mailer receives a copy of the bytes, so protecting the outgoing
        attachment must not reach back and lock the record's own file.
        """
        move = self._move_for("Acme", "ACME-VAT")
        source = _blank_pdf()
        attachment = self.env["ir.attachment"].create({
            "name": "INV.pdf", "raw": source, "mimetype": "application/pdf",
            "res_model": "account.move", "res_id": move.id,
        })
        self._mail_params(move, [(attachment.name, attachment.raw)])
        attachment.invalidate_recordset()
        self.assertEqual(attachment.raw, source, "the archived copy was locked")

    # ---------------------------------------------------- the portal / zip

    def test_11_portal_download_is_encrypted(self):
        move = self._move_for("Acme", "ACME-VAT")
        source = _blank_pdf()
        doc = move._protect_legal_document(
            {"filename": "INV.pdf", "filetype": "pdf", "content": source}
        )
        self.assertNotEqual(doc["content"], source)
        self.assertTrue(PdfReader(io.BytesIO(doc["content"])).decrypt("Secret123"))

    def test_12_portal_download_of_a_non_pdf_is_untouched(self):
        move = self._move_for("Acme", "ACME-VAT")
        xml = b"<?xml version='1.0'?><Invoice/>"
        doc = move._protect_legal_document(
            {"filename": "f.xml", "filetype": "xml", "content": xml}
        )
        self.assertEqual(doc["content"], xml)

    def test_13_portal_download_when_disabled(self):
        self.report.x_pdf_password_enabled = False
        move = self._move_for("Acme", "ACME-VAT")
        source = _blank_pdf()
        doc = move._protect_legal_document(
            {"filename": "INV.pdf", "filetype": "pdf", "content": source}
        )
        self.assertEqual(doc["content"], source)

    # ------------------------------------------------------------- PDF/A

    def test_14_pdfa_einvoice_is_left_readable(self):
        """ISO 19005 forbids encryption; locking one breaks the e-invoice."""
        move = self._move_for("FrenchCo", "FR-VAT")
        source = _blank_pdf() + b"<?xpacket><pdfaid:part>3</pdfaid:part></xpacket>"
        out = self._mail_params(move, [("INV.pdf", source)])["attachments"]
        self.assertEqual(out[0][1], source)

    def test_15_pdfa_skip_is_announced_in_the_chatter(self):
        move = self._move_for("FrenchCo", "FR-VAT")
        source = _blank_pdf() + b"<pdfaid:conformance>A</pdfaid:conformance>"
        before = len(move.message_ids)
        self._mail_params(move, [("INV.pdf", source)])
        self.assertGreater(len(move.message_ids), before)
        self.assertIn("PDF/A", move.message_ids[0].body)

    def test_16_pdfa_marker_matches_odoo_own_metadata(self):
        """Tie PDFA_MARKER to Odoo's PDF/A metadata rather than to a guess."""
        template = "account_edi_ubl_cii.account_invoice_pdfa_3_facturx_metadata"
        if not self.env.ref(template, raise_if_not_found=False):
            self.skipTest("account_edi_ubl_cii not installed")
        rendered = self.env["ir.qweb"]._render(
            template, {"title": "T", "date": fields.Date.context_today(self.env.user)}
        )
        self.assertIn(mod.PDFA_MARKER.decode(), rendered)

    def test_17_marker_is_absent_from_an_ordinary_pdf(self):
        self.assertFalse(self.Send._pdf_declares_pdfa(_blank_pdf()))
        self.assertFalse(self.Send._pdf_declares_pdfa(b""))
        self.assertFalse(self.Send._pdf_declares_pdfa(None))
