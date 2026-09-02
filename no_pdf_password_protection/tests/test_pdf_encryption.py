# Copyright 2026 Naim OUDAYET
# License LGPL-3
import io
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

# Mirror the module's own import order (pypdf first). The module emits
# AES-256 by default, and PyPDF2 2.x cannot verify a /V 5 encryption
# dictionary - reading back with it would fail on the library, not the module.
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover
    from PyPDF2 import PdfReader, PdfWriter

from odoo.addons.no_pdf_password_protection.models import ir_actions_report as mod


def _blank_pdf(pages=1, width=612, height=792):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=height)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _partners(env, count=1):
    """Return `count` partners to experiment on, without creating any.

    This module depends only on `base`, so Odoo loads it - and runs these
    tests - *before* `account`. At that point the registry has none of
    account's res.partner fields, yet the database still carries their NOT
    NULL columns (autopost_bills and friends). `res.partner.create()` therefore
    raises NotNullViolation on any database where Accounting is installed,
    which is most of them. Reusing existing records sidesteps it; the
    surrounding TransactionCase rolls the writes back.
    """
    # parent_id=False only: vat/phone/email are commercial fields, so writing
    # them on a child syncs the whole commercial entity - picking a parent and
    # its own child would silently give two "different" partners one password.
    partners = env["res.partner"].search([("parent_id", "=", False)], limit=count)
    missing = count - len(partners)
    if missing > 0:
        # A base-only database has nothing installed that would break create().
        partners |= env["res.partner"].create(
            [{"name": "PwdTest %d" % i} for i in range(missing)]
        )
    return partners


def _scrub(partner, **vals):
    """Point a partner at known values, clearing the other password sources."""
    base = {"vat": False, "phone": False, "email": False}
    # res.partner.mobile exists on v16-v18 and was dropped in v19. These
    # fixtures reuse existing records, which on a demo database often carry a
    # mobile number; the phone resolver falls back to it, so leaving it set
    # would give a deliberately "no phone" partner a password anyway.
    if "mobile" in partner._fields:
        base["mobile"] = False
    partner.write(dict(base, **vals))
    return partner


def _make_report(env, model="res.partner"):
    """Create a throwaway qweb-pdf report for `model`.

    These tests used to search for an existing res.partner PDF report and skip
    when the database had none - which silently disabled coverage of the batch
    guard, the archived-attachment path and the phone resolver on a plain
    install. Creating the record keeps every assertion running on any database
    and any Odoo series.
    """
    return env["ir.actions.report"].create({
        "name": "Test PDF Password Report",
        "model": model,
        "report_type": "qweb-pdf",
        "report_name": "no_pdf_password_protection.test_report",
    })


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
        cls.partner_report = _make_report(cls.env)

    def _partner(self, **vals):
        vals.setdefault("name", "T")
        return _scrub(_partners(self.env), **vals)

    def _need_partner_report(self):
        # kept as a no-op: the report is created in setUpClass, so the former
        # "skip when the database has none" branch would hide real failures.
        return

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

    def test_10_phone_reduces_to_digits(self):
        # 18.0.2.0.0 changed this from "strip spaces" to "digits only": a
        # recipient cannot be expected to guess whether their number was
        # stored with a +, brackets, dots or dashes.
        self._need_partner_report()
        p = self._partner(phone="+216 12 345 678")
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "phone",
        })
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "21612345678",
        )

    def test_11_phone_prefers_phone_over_mobile(self):
        # only run if the target Odoo version exposes res.partner.mobile
        if "mobile" not in self.env["res.partner"]._fields:
            self.skipTest("res.partner.mobile not present (Odoo 19+)")
        self._need_partner_report()
        p = self._partner(phone="+216 11 111 111", mobile="+216 22 222 222")
        self.partner_report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "phone",
        })
        # phone wins over mobile, and the winner is reduced to digits
        self.assertEqual(
            self.partner_report._get_pdf_password(self.partner_report, [p.id]),
            "21611111111",
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
            "15551234",
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
        partner_report = _make_report(self.env)
        partner = _scrub(_partners(self.env), name="VATCarrier",
                         vat="PARTNER-VAT")
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


class TestPdfEncryptionAlgorithm(TransactionCase):
    """Cover x_pdf_encryption_algo: the emitted cipher must match the choice.

    Assertions are made on the raw PDF bytes rather than through a reader, so
    they hold regardless of which backend the test runner happens to import.
    A PDF encrypted with AES carries an /AESV2 (AES-128) or /AESV3 (AES-256)
    crypt filter; RC4 carries neither and sits at /V 2.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env["ir.actions.report"].search(
            [("report_type", "=", "qweb-pdf")], limit=1
        )

    def setUp(self):
        super().setUp()
        if not self.report:
            self.skipTest("no qweb-pdf report available")
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "Secret123",
        })

    def _render_with(self, algo):
        if algo is not None:
            self.report.x_pdf_encryption_algo = algo
        parent = _super_class_of_override(self.report)
        source = _blank_pdf()
        with patch.object(parent, "_render_qweb_pdf", return_value=(source, "pdf")):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        return result

    def _require_aes(self):
        if not mod.backend_supports_aes():
            self.skipTest(
                f"backend {mod.PDF_BACKEND} has no encrypt(algorithm=...)"
            )

    def test_33_default_is_aes256(self):
        fresh = self.env["ir.actions.report"].new({})
        self.assertEqual(fresh.x_pdf_encryption_algo, "aes256")

    def test_34_aes256_emits_aesv3(self):
        self._require_aes()
        result = self._render_with("aes256")
        self.assertIn(b"AESV3", result)
        self.assertNotIn(b"AESV2", result)

    def test_35_aes128_emits_aesv2(self):
        self._require_aes()
        result = self._render_with("aes128")
        self.assertIn(b"AESV2", result)
        self.assertNotIn(b"AESV3", result)

    def test_36_rc4_emits_no_aes(self):
        result = self._render_with("rc4_128")
        self.assertIn(b"/Encrypt", result)
        self.assertNotIn(b"AESV2", result)
        self.assertNotIn(b"AESV3", result)

    def test_37_unset_algo_still_defaults_to_aes256(self):
        """Rows written before this field existed read back NULL on upgrade."""
        self._require_aes()
        self.report.x_pdf_encryption_algo = False
        result = self._render_with(None)
        self.assertIn(b"AESV3", result)

    def test_38_backend_without_aes_falls_back_to_rc4(self):
        """A PyPDF2-only deployment must still encrypt, just with RC4."""
        with patch.object(mod, "backend_supports_aes", return_value=False):
            result = self._render_with("aes256")
        self.assertIn(b"/Encrypt", result)
        self.assertNotIn(b"AESV3", result)

    def test_39_aes256_opens_with_the_configured_password(self):
        self._require_aes()
        result = self._render_with("aes256")
        reader = mod.PdfReader(io.BytesIO(result))
        self.assertTrue(reader.is_encrypted)
        self.assertTrue(reader.decrypt("Secret123"))

    def test_40_wrong_password_rejected_under_aes256(self):
        self._require_aes()
        result = self._render_with("aes256")
        reader = mod.PdfReader(io.BytesIO(result))
        self.assertEqual(reader.decrypt("NotThePassword"), 0)


class TestMixedBatchPrint(TransactionCase):
    """A merged print of records with different passwords.

    Blocking an ordinary bulk print would be worse than the problem: staff
    print batches all day. The document comes back unlocked, and each record
    is told why, so nobody believes they have a protected file when they do not.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = _make_report(cls.env)

    def setUp(self):
        super().setUp()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": False,
        })
        pair = _partners(self.env, 2)
        self.a = _scrub(pair[0], name="A", vat="VAT-A")
        self.b = _scrub(pair[1], name="B", vat="VAT-B")

    def _render(self, res_ids):
        parent = _super_class_of_override(self.report)
        with patch.object(parent, "_render_qweb_pdf",
                          return_value=(_blank_pdf(), "pdf")):
            return self.report._render_qweb_pdf(self.report.id, res_ids=res_ids)[0]

    def test_41_mixed_batch_is_not_blocked(self):
        self.assertFalse(
            self.report._batch_shares_one_password([self.a.id, self.b.id])
        )
        result = self._render([self.a.id, self.b.id])
        self.assertNotIn(b"/Encrypt", result, "a mixed batch must come back unlocked")

    def test_42_uniform_batch_is_still_protected(self):
        same = _scrub(_partners(self.env, 3)[2], name="A2", vat="VAT-A")
        self.assertTrue(
            self.report._batch_shares_one_password([self.a.id, same.id])
        )
        self.assertIn(b"/Encrypt", self._render([self.a.id, same.id]))

    def test_43_single_record_is_still_protected(self):
        self.assertIn(b"/Encrypt", self._render([self.a.id]))

    def test_44_static_password_batches_are_unaffected(self):
        self.report.write({"x_pdf_password_method": "static",
                           "x_pdf_static_password": "Shared"})
        self.assertIn(b"/Encrypt", self._render([self.a.id, self.b.id]))

    def test_45_logging_the_unlocked_batch_never_breaks_the_print(self):
        """Log only - a bulk print is a list action, notes on every record
        would bury the chatter for something done deliberately."""
        self.report._log_unencrypted_batch([self.a.id, self.b.id])  # must not raise
        before = len(self.a.message_ids) if hasattr(self.a, "message_ids") else 0
        self._render([self.a.id, self.b.id])
        if hasattr(self.a, "message_ids"):
            self.a.invalidate_recordset()
            self.assertEqual(len(self.a.message_ids), before,
                             "the batch path must not post to the chatter")


class TestPhoneNormalisation(TransactionCase):
    """A recipient cannot guess the punctuation their number was stored with."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = _make_report(cls.env)

    def setUp(self):
        super().setUp()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "phone",
            "x_pdf_static_password": False,
        })

    def _password_for(self, phone):
        partner = _scrub(_partners(self.env), name="P", phone=phone)
        return self.report._get_pdf_password(self.report, [partner.id])

    def test_46_every_punctuation_style_yields_the_same_digits(self):
        for raw in ["+216 71 123 456", "(216) 71-123-456",
                    "216.71.123.456", "216 71 123 456"]:
            self.assertEqual(
                self._password_for(raw), "21671123456",
                "phone %r did not normalise to digits" % raw,
            )

    def test_47_phone_without_digits_falls_back_to_static(self):
        self.report.x_pdf_static_password = "Fallback"
        self.assertEqual(self._password_for("no number"), "Fallback")


class TestEncryptionSuppression(TransactionCase):
    """Some callers need a PDF they can still process themselves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env["ir.actions.report"].search(
            [("report_type", "=", "qweb-pdf")], limit=1
        )

    def setUp(self):
        super().setUp()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "Secret123",
        })

    def test_48_snailmail_context_suppresses_encryption(self):
        """The postal provider cannot print an encrypted file."""
        source = _blank_pdf()
        parent = _super_class_of_override(self.report)
        report = self.report.with_context(snailmail_layout=True)
        with patch.object(parent, "_render_qweb_pdf", return_value=(source, "pdf")):
            result, _ = report._render_qweb_pdf(report.id)
        self.assertEqual(result, source, "snailmail must receive a readable PDF")

    def test_49_suppression_tests_the_key_not_its_value(self):
        """snailmail passes snailmail_layout=not self.cover, so it can be False."""
        source = _blank_pdf()
        parent = _super_class_of_override(self.report)
        report = self.report.with_context(snailmail_layout=False)
        with patch.object(parent, "_render_qweb_pdf", return_value=(source, "pdf")):
            result, _ = report._render_qweb_pdf(report.id)
        self.assertEqual(result, source)

    def test_50_normal_render_is_still_encrypted(self):
        source = _blank_pdf()
        parent = _super_class_of_override(self.report)
        with patch.object(parent, "_render_qweb_pdf", return_value=(source, "pdf")):
            result, _ = self.report._render_qweb_pdf(self.report.id)
        self.assertIn(b"/Encrypt", result)


class TestArchivedAttachment(TransactionCase):
    """Cover _prepare_pdf_report_attachment_vals_list.

    Core archives the PDF on the record from inside _render_qweb_pdf, before
    the merged bytes reach our override. Without this hook the download would
    be encrypted while the archived copy - what the chatter shows and what
    mail templates attach - stayed plaintext.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = _make_report(cls.env)

    def setUp(self):
        super().setUp()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
            "x_pdf_static_password": "Secret123",
            "attachment": "'archived.pdf'",
            "x_pdf_protect_stored_copy": True,
        })

    def _streams_for(self, partners):
        return {
            p.id: {"stream": io.BytesIO(_blank_pdf()), "attachment": False}
            for p in partners
        }

    def test_51_archived_copy_is_encrypted(self):
        p = _scrub(_partners(self.env), name="Archived", vat="V1")
        vals = self.report._prepare_pdf_report_attachment_vals_list(
            self.report, self._streams_for(p)
        )
        self.assertTrue(vals, "core produced no attachment vals")
        for v in vals:
            self.assertIn(b"/Encrypt", v["raw"], "archived copy is plaintext")

    def test_52_each_archived_copy_uses_its_own_partner_password(self):
        self.report.write({
            "x_pdf_password_method": "vat",
            "x_pdf_static_password": False,
        })
        pair = _partners(self.env, 2)
        a = _scrub(pair[0], name="A", vat="VAT-A")
        b = _scrub(pair[1], name="B", vat="VAT-B")
        vals = {
            v["res_id"]: v["raw"]
            for v in self.report._prepare_pdf_report_attachment_vals_list(
                self.report, self._streams_for(a | b)
            )
        }
        self.assertTrue(PdfReader(io.BytesIO(vals[a.id])).decrypt("VAT-A"))
        self.assertTrue(PdfReader(io.BytesIO(vals[b.id])).decrypt("VAT-B"))
        self.assertEqual(PdfReader(io.BytesIO(vals[a.id])).decrypt("VAT-B"), 0)

    def test_53_disabled_report_archives_plaintext(self):
        self.report.x_pdf_password_enabled = False
        p = _scrub(_partners(self.env), name="Plain", vat="V2")
        vals = self.report._prepare_pdf_report_attachment_vals_list(
            self.report, self._streams_for(p)
        )
        for v in vals:
            self.assertNotIn(b"/Encrypt", v["raw"])

    def test_57_archive_is_readable_by_default(self):
        """Staff preview the archived copy from the chatter.

        Every route that leaves Odoo re-encrypts on the way out, so encrypting
        the copy at rest buys no delivered protection while costing a colleague
        a password prompt on a record they can already open. Off by default.
        """
        self.report.x_pdf_protect_stored_copy = False
        p = _scrub(_partners(self.env), name="Preview", vat="V3")
        vals = self.report._prepare_pdf_report_attachment_vals_list(
            self.report, self._streams_for(p)
        )
        self.assertTrue(vals)
        for v in vals:
            self.assertNotIn(b"/Encrypt", v["raw"])

    def test_58_delivery_is_encrypted_even_with_a_readable_archive(self):
        """The point of the default: nothing that leaves is weakened."""
        self.report.x_pdf_protect_stored_copy = False
        parent = _super_class_of_override(self.report)
        source = _blank_pdf()
        with patch.object(parent, "_render_qweb_pdf", return_value=(source, "pdf")):
            delivered, _ = self.report._render_qweb_pdf(self.report.id)
        self.assertIn(b"/Encrypt", delivered)


class TestPasswordLimits(TransactionCase):
    """ISO 32000 caps the standard security handler password at 127 bytes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env["ir.actions.report"].search(
            [("report_type", "=", "qweb-pdf")], limit=1
        )

    def setUp(self):
        super().setUp()
        self.report.write({
            "x_pdf_password_enabled": True,
            "x_pdf_password_method": "static",
        })

    def test_54_password_at_the_limit_is_accepted(self):
        self.report.x_pdf_static_password = "x" * 127
        self.assertIsNotNone(self.report._encrypt_pdf(_blank_pdf(), None))

    def test_55_over_limit_password_refuses_rather_than_truncating(self):
        """Readers truncate differently; an unopenable file is the worst case."""
        self.report.x_pdf_static_password = "x" * 128
        self.assertIsNone(self.report._encrypt_pdf(_blank_pdf(), None))

    def test_56_limit_is_measured_in_bytes_not_characters(self):
        self.report.x_pdf_static_password = "é" * 64  # 64 x 2 bytes = 128 bytes in UTF-8
        self.assertIsNone(self.report._encrypt_pdf(_blank_pdf(), None))
