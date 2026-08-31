import io

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


class TestAccountSendEncryption(TransactionCase):
    """Cover _link_invoice_documents - the last step of the send pipeline.

    Driving this method directly (rather than _generate_and_send_invoices) is
    deliberate: in test mode `_pre_render_qweb_pdf` falls back to HTML, so a
    full send would never produce a PDF to encrypt. Feeding the pipeline its
    own data structure exercises exactly the code that runs in production.
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

    def _payload(self, invoice, pdf):
        return {
            invoice: {
                "pdf_report": self.report,
                "pdf_attachment_values": {
                    "name": "%s.pdf" % invoice.id,
                    "raw": pdf,
                    "mimetype": "application/pdf",
                    "res_model": "account.move",
                    "res_id": invoice.id,
                    "res_field": "invoice_pdf_report_file",
                },
            }
        }

    def test_01_mailed_pdf_is_encrypted(self):
        """The regression this module exists for."""
        source = _blank_pdf()
        move = self._move_for("Acme", "ACME-VAT")
        data = self._payload(move, source)
        self.Send._link_invoice_documents(data)
        raw = data[move]["pdf_attachment_values"]["raw"]
        self.assertNotEqual(raw, source, "Send and Print delivered a plaintext PDF")
        self.assertTrue(PdfReader(io.BytesIO(raw)).is_encrypted)

    def test_02_stored_attachment_carries_the_encrypted_bytes(self):
        """What is persisted - and therefore mailed - must be the ciphertext."""
        move = self._move_for("Acme", "ACME-VAT")
        self.Send._link_invoice_documents(self._payload(move, _blank_pdf()))
        move.invalidate_recordset()
        attachment = move.invoice_pdf_report_id
        self.assertTrue(attachment, "no attachment was created")
        reader = PdfReader(io.BytesIO(attachment.raw))
        self.assertTrue(reader.is_encrypted)
        self.assertTrue(reader.decrypt("Secret123"))

    def test_03_each_invoice_uses_its_own_partner_password(self):
        """The reason this hook beats the merged print path."""
        self.report.x_pdf_password_method = "vat"
        a = self._move_for("Alpha", "VAT-ALPHA")
        b = self._move_for("Beta", "VAT-BETA")
        data = {}
        data.update(self._payload(a, _blank_pdf()))
        data.update(self._payload(b, _blank_pdf()))
        self.Send._link_invoice_documents(data)
        raw_a = data[a]["pdf_attachment_values"]["raw"]
        raw_b = data[b]["pdf_attachment_values"]["raw"]
        self.assertTrue(PdfReader(io.BytesIO(raw_a)).decrypt("VAT-ALPHA"))
        self.assertTrue(PdfReader(io.BytesIO(raw_b)).decrypt("VAT-BETA"))
        self.assertEqual(PdfReader(io.BytesIO(raw_a)).decrypt("VAT-BETA"), 0)
        self.assertEqual(PdfReader(io.BytesIO(raw_b)).decrypt("VAT-ALPHA"), 0)

    def test_04_respects_the_configured_algorithm(self):
        self.report.x_pdf_encryption_algo = "rc4_128"
        move = self._move_for("Acme", "ACME-VAT")
        data = self._payload(move, _blank_pdf())
        self.Send._link_invoice_documents(data)
        raw = data[move]["pdf_attachment_values"]["raw"]
        self.assertIn(b"/Encrypt", raw)
        self.assertNotIn(b"AESV3", raw)

    def test_05_disabled_report_passes_through_untouched(self):
        self.report.x_pdf_password_enabled = False
        source = _blank_pdf()
        move = self._move_for("Acme", "ACME-VAT")
        data = self._payload(move, source)
        self.Send._link_invoice_documents(data)
        self.assertEqual(data[move]["pdf_attachment_values"]["raw"], source)

    def test_06_unresolvable_password_leaves_bytes_intact(self):
        """Never corrupt a PDF we could not encrypt - send it as-is."""
        self.report.write({
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": False,
        })
        source = _blank_pdf()
        move = self._move_for("NoVat", False)
        data = self._payload(move, source)
        self.Send._link_invoice_documents(data)
        self.assertEqual(data[move]["pdf_attachment_values"]["raw"], source)

    def test_07_missing_pdf_report_key_does_not_crash(self):
        source = _blank_pdf()
        move = self._move_for("Acme", "ACME-VAT")
        data = self._payload(move, source)
        del data[move]["pdf_report"]
        self.Send._link_invoice_documents(data)
        self.assertEqual(data[move]["pdf_attachment_values"]["raw"], source)

    def test_08_missing_attachment_values_does_not_crash(self):
        move = self._move_for("Acme", "ACME-VAT")
        data = {move: {"pdf_report": self.report}}
        self.Send._link_invoice_documents(data)  # must not raise

    def test_09_page_count_preserved(self):
        move = self._move_for("Acme", "ACME-VAT")
        data = self._payload(move, _blank_pdf(pages=3))
        self.Send._link_invoice_documents(data)
        reader = PdfReader(io.BytesIO(data[move]["pdf_attachment_values"]["raw"]))
        reader.decrypt("Secret123")
        self.assertEqual(len(reader.pages), 3)

    def test_10_post_processing_hooks_still_see_plaintext(self):
        """Guard the ordering bug that broke the first implementation.

        account_edi_ubl_cii embeds the Factur-X XML in
        `_hook_invoice_document_after_pdf_report_render`, reading the PDF via
        odoo.tools.pdf (PyPDF2), which cannot open an AES file. Encrypting in
        `_link_invoice_documents` guarantees that hook already ran, so the
        bytes it received must still be plaintext.
        """
        move = self._move_for("Acme", "ACME-VAT")
        data = self._payload(move, _blank_pdf())

        # Whatever the EDI hook sees must be readable.
        values = data[move]["pdf_attachment_values"]
        self.assertNotIn(b"/Encrypt", values["raw"])
        self.Send._hook_invoice_document_after_pdf_report_render(move, data[move])
        self.assertNotIn(
            b"/Encrypt",
            data[move]["pdf_attachment_values"]["raw"],
            "post-processing hooks must still see plaintext",
        )

        # ...and only the final link step turns it into ciphertext.
        self.Send._link_invoice_documents(data)
        self.assertIn(b"/Encrypt", data[move]["pdf_attachment_values"]["raw"])

    def test_11_pdfa_einvoice_is_left_unencrypted(self):
        """ISO 19005 forbids encryption; a Factur-X PDF/A must pass through.

        Encrypting one would strip its conformance and hide the embedded
        e-invoicing XML from the recipient's AP system.
        """
        source = _blank_pdf() + b"<?xpacket><pdfaid:part>3</pdfaid:part></xpacket>"
        move = self._move_for("FrenchCo", "FR-VAT")
        data = self._payload(move, source)
        self.Send._link_invoice_documents(data)
        self.assertEqual(
            data[move]["pdf_attachment_values"]["raw"],
            source,
            "a PDF/A e-invoice must not be encrypted",
        )

    def test_12_pdfa_skip_is_announced_in_the_chatter(self):
        """Silently not protecting a document would be the worst outcome."""
        source = _blank_pdf() + b"<pdfaid:conformance>A</pdfaid:conformance>"
        move = self._move_for("FrenchCo", "FR-VAT")
        before = len(move.message_ids)
        self.Send._link_invoice_documents(self._payload(move, source))
        self.assertGreater(len(move.message_ids), before, "no chatter note posted")
        self.assertIn("PDF/A", move.message_ids[0].body)

    def test_13_ordinary_invoice_with_embedded_xml_is_still_encrypted(self):
        """account_edi_ubl_cii embeds factur-x.xml in *every* invoice.

        Keying the skip on the XML rather than the PDF/A claim would therefore
        disable the module entirely; guard against that regression.
        """
        source = _blank_pdf() + b"factur-x.xml"
        move = self._move_for("Acme", "ACME-VAT")
        data = self._payload(move, source)
        self.Send._link_invoice_documents(data)
        self.assertIn(b"/Encrypt", data[move]["pdf_attachment_values"]["raw"])


    def test_14_pdfa_marker_matches_odoo_own_metadata(self):
        """Tie PDFA_MARKER to Odoo's PDF/A metadata rather than to a guess.

        The guard keys on the conformance claim in the document's XMP. That
        claim is written by account_edi_ubl_cii from the QWeb template below,
        so if Odoo ever changes its shape this test fails and tells us the
        detector needs updating - instead of the module silently starting to
        encrypt e-invoices again.

        Verified once by hand against a real document: rendering an invoice,
        embedding factur-x.xml and running Odoo's own convert_to_pdfa() +
        add_file_metadata() produced a 44 KB PDF/A-3 that this guard detected,
        left byte-identical, and announced in the chatter.
        """
        template = "account_edi_ubl_cii.account_invoice_pdfa_3_facturx_metadata"
        if not self.env.ref(template, raise_if_not_found=False):
            self.skipTest("account_edi_ubl_cii not installed")
        rendered = self.env["ir.qweb"]._render(
            template, {"title": "T", "date": fields.Date.context_today(self.env.user)}
        )
        self.assertIn(
            mod.PDFA_MARKER.decode(),
            rendered,
            "Odoo's PDF/A metadata no longer carries the marker this guard "
            "looks for; PDF/A e-invoices would start being encrypted.",
        )

    def test_15_marker_is_absent_from_an_ordinary_pdf(self):
        """Guard against a marker so generic it matches every document."""
        self.assertFalse(self.Send._pdf_declares_pdfa(_blank_pdf()))
        self.assertFalse(self.Send._pdf_declares_pdfa(b""))
        self.assertFalse(self.Send._pdf_declares_pdfa(None))
