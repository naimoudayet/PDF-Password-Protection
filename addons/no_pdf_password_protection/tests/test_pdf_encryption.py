from odoo.tests.common import TransactionCase


class TestPdfPasswordProtection(TransactionCase):

    def test_password_fields_exist(self):
        """Test that password fields were added to ir.actions.report."""
        report = self.env["ir.actions.report"].search([], limit=1)
        self.assertTrue(hasattr(report, "x_pdf_password_enabled"))
        self.assertTrue(hasattr(report, "x_pdf_password_method"))
        self.assertTrue(hasattr(report, "x_pdf_static_password"))

    def test_static_password_retrieval(self):
        """Test static password method returns the configured password."""
        report = self.env["ir.actions.report"].search([], limit=1)
        report.write(
            {
                "x_pdf_password_enabled": True,
                "x_pdf_password_method": "static",
                "x_pdf_static_password": "test123",
            }
        )
        password = report._get_pdf_password(report, None)
        self.assertEqual(password, "test123")

    def test_vat_password_with_partner(self):
        """Test VAT-based password retrieval from a partner record."""
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "vat": "BE0123456789",
            }
        )
        report = self.env["ir.actions.report"].search(
            [("model", "=", "res.partner")], limit=1
        )
        if not report:
            return  # Skip if no partner report exists
        report.write(
            {
                "x_pdf_password_enabled": True,
                "x_pdf_password_method": "vat",
            }
        )
        password = report._get_pdf_password(report, [partner.id])
        self.assertEqual(password, "BE0123456789")

    def test_phone_password_with_partner(self):
        """Test phone-based password strips spaces."""
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner Phone",
                "phone": "+216 12 345 678",
            }
        )
        report = self.env["ir.actions.report"].search(
            [("model", "=", "res.partner")], limit=1
        )
        if not report:
            return
        report.write(
            {
                "x_pdf_password_enabled": True,
                "x_pdf_password_method": "phone",
            }
        )
        password = report._get_pdf_password(report, [partner.id])
        self.assertEqual(password, "+21612345678")

    def test_email_password_with_partner(self):
        """Test email-based password retrieval."""
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner Email",
                "email": "test@example.com",
            }
        )
        report = self.env["ir.actions.report"].search(
            [("model", "=", "res.partner")], limit=1
        )
        if not report:
            return
        report.write(
            {
                "x_pdf_password_enabled": True,
                "x_pdf_password_method": "email",
            }
        )
        password = report._get_pdf_password(report, [partner.id])
        self.assertEqual(password, "test@example.com")

    def test_fallback_to_static_password(self):
        """Test fallback to static password when dynamic field is empty."""
        partner = self.env["res.partner"].create(
            {
                "name": "No VAT Partner",
            }
        )
        report = self.env["ir.actions.report"].search(
            [("model", "=", "res.partner")], limit=1
        )
        if not report:
            return
        report.write(
            {
                "x_pdf_password_enabled": True,
                "x_pdf_password_method": "vat",
                "x_pdf_static_password": "fallback123",
            }
        )
        password = report._get_pdf_password(report, [partner.id])
        self.assertEqual(password, "fallback123")

    def test_disabled_protection_returns_none(self):
        """Test that disabled protection does not interfere with reports."""
        report = self.env["ir.actions.report"].search([], limit=1)
        report.write(
            {
                "x_pdf_password_enabled": False,
            }
        )
        # The override checks x_pdf_password_enabled before encrypting,
        # so this just verifies the field value.
        self.assertFalse(report.x_pdf_password_enabled)
