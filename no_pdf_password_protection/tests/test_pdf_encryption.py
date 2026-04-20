import io
from unittest.mock import patch

from odoo.tests.common import TransactionCase

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:  # pragma: no cover
    from pypdf import PdfReader, PdfWriter

from odoo.addons.no_pdf_password_protection.models import ir_actions_report as mod


def _blank_pdf(pages=1, width=612, height=792):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=height)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _super_class_of_override(report):
    """Find the class above our override in the report's MRO.

    Needed so we can patch the upstream `_render_qweb_pdf` (i.e. the `super()`
    target of our override) and feed the override deterministic input bytes.
    """
    mro = type(report).__mro__
    our_idx = next(
        i for i, c in enumerate(mro)
        if "no_pdf_password_protection" in (getattr(c, "__module__", "") or "")
    )
    return mro[our_idx + 1]


class TestPdfPasswordResolver(TransactionCase):
    """Cover _get_pdf_password across every dispatch path + fallback rule."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.any_report = cls.env["ir.actions.report"].search([], limit=1)
        cls.partner_report = cls.env["ir.actions.report"].search(
            [("model", "=", "res.partner")], limit=1
        )

    def _partner(self, **vals):
        vals.setdefault("name", "T")
        return self.env["res.partner"].create(vals)

    def _need_partner_report(self):
        if not self.partner_report:
            self.skipTest("no res.partner report in base install")

    # ------------------------------------------------------------------ fields

    def test_01_fields_exist_on_report_model(self):
        rec = self.any_report
        self.assertTrue(hasattr(rec, "x_pdf_password_enabled"))
        self.assertTrue(hasattr(rec, "x_pdf_password_method"))
        self.assertTrue(hasattr(rec, "x_pdf_static_password"))

    def test_02_default_values(self):
        rec = self.any_report
        # defaults are Boolean(default=False), Selection(default='static'), Char
        self.assertFalse(rec.x_pdf_password_enabled)
        self.assertIn(rec.x_pdf_password_method, ("static", False))

    def test_03_method_selection_accepts_all_four_values(self):
        rec = self.any_report
        for value in ("static", "vat", "phone", "email"):
            rec.x_pdf_password_method = value
            self.assertEqual(rec.x_pdf_password_method, value)

    # ------------------------------------------------------------------ static

    def test_04_static_password_returns_configured_value(self):
        self.any_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "abc123",
        })
        self.assertEqual(
            self.any_report._get_pdf_password(self.any_report, None), "abc123"
        )

    def test_05_static_method_with_empty_password_returns_falsy(self):
        self.any_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": False,
        })
        self.assertFalse(
            self.any_report._get_pdf_password(self.any_report, None)
        )

    def test_06_static_method_ignores_res_ids(self):
        # static doesn't need records — res_ids can be None, [], or anything
        self.any_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "same",
        })
        for res_ids in (None, [], [1], [1, 2, 3]):
            self.assertEqual(
                self.any_report._get_pdf_password(self.any_report, res_ids),
                "same",
            )

    # ------------------------------------------------------------------ VAT

    def test_07_vat_returns_partner_vat(self):
        self._need_partner_report()
        p = self._partner(vat="BE0123456789")
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "BE0123456789",
        )

    def test_08_vat_empty_falls_back_to_static(self):
        self._need_partner_report()
        p = self._partner()
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": "FBK",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "FBK",
        )

    def test_09_vat_empty_no_static_returns_falsy(self):
        self._need_partner_report()
        p = self._partner()
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": False,
        })
        # falsy value -> encryption branch in _render_qweb_pdf skips encrypt
        self.assertFalse(
            self.partner_report._get_pdf_password(self.partner_report, [p.id])
        )

    # ------------------------------------------------------------------ phone

    def test_10_phone_strips_spaces(self):
        self._need_partner_report()
        p = self._partner(phone="+216 12 345 678")
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "phone",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "+21612345678",
        )

    def test_11_phone_prefers_phone_over_mobile(self):
        # only run if the target Odoo version exposes res.partner.mobile
        if "mobile" not in self.env["res.partner"]._fields:
            self.skipTest("res.partner.mobile not present (Odoo 19+)")
        self._need_partner_report()
        p = self._partner(phone="MAINPHONE", mobile="MOBILE")
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "phone",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "MAINPHONE",
        )

    def test_12_phone_falls_back_to_mobile_when_phone_empty(self):
        if "mobile" not in self.env["res.partner"]._fields:
            self.skipTest("res.partner.mobile not present (Odoo 19+)")
        self._need_partner_report()
        p = self._partner(mobile="+1 555 1234")
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "phone",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "+15551234",
        )

    def test_13_phone_both_empty_falls_back_to_static(self):
        self._need_partner_report()
        p = self._partner()
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "phone",
            "x_pdf_static_password": "S",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "S",
        )

    def test_14_phone_on_v19_no_mobile_does_not_crash(self):
        # regression: partner.phone or partner.mobile used to AttributeError
        # on Odoo 19 because mobile was dropped. getattr fix ensures no-op.
        self._need_partner_report()
        p = self._partner()  # no phone, no mobile
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "phone",
            "x_pdf_static_password": "OK",
        })
        # must not raise
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "OK",
        )

    # ------------------------------------------------------------------ email

    def test_15_email_returned(self):
        self._need_partner_report()
        p = self._partner(email="a@b.com")
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "email",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "a@b.com",
        )

    def test_16_email_empty_falls_back_to_static(self):
        self._need_partner_report()
        p = self._partner()
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "email",
            "x_pdf_static_password": "S",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "S",
        )

    # ------------------------------------------------------------------ record handling

    def test_17_none_res_ids_on_dynamic_falls_back_to_static(self):
        self._need_partner_report()
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": "S",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, None),
            "S",
        )

    def test_18_empty_res_ids_on_dynamic_falls_back_to_static(self):
        self._need_partner_report()
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": "S",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, []),
            "S",
        )

    def test_19_none_res_ids_no_static_returns_falsy(self):
        self._need_partner_report()
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": False,
        })
        self.assertFalse(
            self.partner_report._get_pdf_password(self.partner_report, None)
        )

    def test_20_record_is_partner_itself(self):
        self._need_partner_report()
        p = self._partner(email="self@p.com")
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "email",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "self@p.com",
        )

    def test_21_model_without_partner_id_falls_back_to_static(self):
        # ir.module.module has no partner_id field -> cannot resolve partner
        module_report = self.env["ir.actions.report"].search(
            [("model", "=", "ir.module.module")], limit=1
        )
        if not module_report:
            self.skipTest("no ir.module.module report")
        module_rec = self.env["ir.module.module"].search([], limit=1)
        module_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": "FBK",
        })
        self.assertEqual(
            module_report._get_pdf_password(module_report, [module_rec.id]),
            "FBK",
        )


class TestPdfEncryption(TransactionCase):
    """Cover _render_qweb_pdf: real PDF bytes in, encrypted PDF out."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env["ir.actions.report"].search(
            [("report_type", "=", "qweb-pdf")], limit=1
        )

    def setUp(self):
        super().setUp()
        if not self.report:
            self.skipTest("no qweb-pdf report in base install")

    def _stub_super(self, content, content_type="pdf"):
        parent = _super_class_of_override(self.report)
        return patch.object(
            parent, "_render_qweb_pdf",
            return_value=(content, content_type),
        )

    # ------------------------------------------------------------------ happy path

    def test_22_enabled_static_produces_encrypted_pdf(self):
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "topsecret",
        })
        with self._stub_super(_blank_pdf()):
            result, ctype = self.report._render_qweb_pdf(self.report.id)
        self.assertEqual(ctype, "pdf")
        reader = PdfReader(io.BytesIO(result))
        self.assertTrue(reader.is_encrypted)

    def test_23_correct_password_decrypts(self):
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "correct",
        })
        with self._stub_super(_blank_pdf()):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        reader = PdfReader(io.BytesIO(result))
        # decrypt returns truthy on success (1 = user pwd, 2 = owner pwd)
        self.assertTrue(reader.decrypt("correct"))

    def test_24_wrong_password_fails_decrypt(self):
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "correct",
        })
        with self._stub_super(_blank_pdf()):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        reader = PdfReader(io.BytesIO(result))
        # 0 = decrypt failure
        self.assertEqual(reader.decrypt("wrong"), 0)

    def test_25_page_count_preserved(self):
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "pw",
        })
        with self._stub_super(_blank_pdf(pages=5)):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        reader = PdfReader(io.BytesIO(result))
        reader.decrypt("pw")
        self.assertEqual(len(reader.pages), 5)

    # ------------------------------------------------------------------ early-return paths

    def test_26_non_pdf_content_type_unchanged(self):
        payload = b"not a pdf"
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "pw",
        })
        with self._stub_super(payload, content_type="text"):
            result, ctype = self.report._render_qweb_pdf(self.report.id)
        self.assertEqual(ctype, "text")
        self.assertEqual(result, payload)

    def test_27_disabled_flag_returns_original_bytes(self):
        source = _blank_pdf()
        self.report.write({
            "x_pdf_password_enabled": False,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "pw",
        })
        with self._stub_super(source):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        self.assertEqual(result, source)
        self.assertFalse(PdfReader(io.BytesIO(result)).is_encrypted)

    def test_28_no_password_resolved_returns_original_bytes(self):
        source = _blank_pdf()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": False,  # no password resolvable
        })
        with self._stub_super(source):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        self.assertEqual(result, source)
        self.assertFalse(PdfReader(io.BytesIO(result)).is_encrypted)

    def test_29_pypdf_unavailable_no_op(self):
        source = _blank_pdf()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "pw",
        })
        with self._stub_super(source), patch.object(mod, "PdfWriter", None):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        self.assertEqual(result, source)

    def test_30_encryption_exception_falls_back_to_original(self):
        source = _blank_pdf()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "pw",
        })
        broken = mod.PdfWriter
        # wrap the real writer, make encrypt raise
        class Broken(broken):
            def encrypt(self, *a, **kw):
                raise RuntimeError("boom")
        with self._stub_super(source), \
             patch.object(mod, "PdfWriter", Broken), \
             self.assertLogs("odoo.addons.no_pdf_password_protection", level="ERROR"):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        self.assertEqual(result, source)

    def test_31_password_does_not_leak_into_error_logs(self):
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "Sensitive!2026",
        })
        # garbage bytes -> PdfReader raises -> error branch runs
        with self._stub_super(b"not-a-valid-pdf"), \
             self.assertLogs("odoo.addons.no_pdf_password_protection", level="ERROR") as cm:
            self.report._render_qweb_pdf(self.report.id)
        joined = "\n".join(cm.output)
        self.assertNotIn(
            "Sensitive!2026", joined,
            "password must never appear in log output",
        )

    def test_32_dynamic_method_uses_resolved_partner_password(self):
        # prove the resolver picks up the partner's VAT and the encryption
        # uses THAT password, not a stale static fallback
        partner_report = self.env["ir.actions.report"].search(
            [("model", "=", "res.partner"), ("report_type", "=", "qweb-pdf")],
            limit=1,
        )
        if not partner_report:
            self.skipTest("no partner qweb-pdf report")
        partner = self.env["res.partner"].create({
            "name": "VATCarrier", "vat": "PARTNER-VAT",
        })
        partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": "SHOULD-NOT-USE",
        })
        parent = _super_class_of_override(partner_report)
        source = _blank_pdf()
        with patch.object(parent, "_render_qweb_pdf",
                          return_value=(source, "pdf")):
            result, _ = partner_report._render_qweb_pdf(
                partner_report.id, res_ids=[partner.id]
            )
        reader = PdfReader(io.BytesIO(result))
        self.assertTrue(reader.is_encrypted)
        self.assertTrue(reader.decrypt("PARTNER-VAT"))
        self.assertEqual(reader.decrypt("SHOULD-NOT-USE"), 0)
