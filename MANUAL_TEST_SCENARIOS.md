# Manual test scenarios

Dev-only. Run these on a provisioned stack (ODOO_GUIDELINES section 13) with both
modules installed, `sale_management` / `contacts` / `account` / `project` and demo
data, and the 9 Tier 2 languages active.

Set up once: **Settings > Technical > Actions > Reports > Invoice PDF**, enable
**PDF Password Protection**, leave **AES-256**, set **Password Source** to
*Partner VAT Number*, and give two customers different VAT numbers.

## 1. What leaves is locked, what stays is readable

1. Open a posted customer invoice and click **Print**.
2. The downloaded file asks for the customer's VAT number. It opens with it.
3. Back on the record, open the PDF in the preview pane on the right.
4. **Expected:** it opens with no password. Your own team is never locked out.

## 2. The emailed invoice is protected, and says so

1. On a posted invoice, click **Send**.
2. **Expected:** an **Explain the password in the email** tick above the message,
   already on.
3. Send it. Open the message in the chatter.
4. **Expected:** a short notice sits above your usual text, rendered as a
   sentence and not as markup, and the attachment asks for the password.
5. Untick the option and send another invoice.
6. **Expected:** the attachment is still protected; only the notice is absent.

## 3. Your own wording, in your own language

1. On the report, type your own text in **Password Notice for Emails**.
2. Send an invoice; confirm your wording appears.
3. Clear the field, switch a user to French, and send again.
4. **Expected:** the standard sentence appears in French without anyone
   translating anything.

## 4. A bulk print is never interrupted

1. From the invoice list, tick two invoices belonging to **different** customers.
2. **Print > Invoices**.
3. **Expected:** no error dialog. One merged file, unprotected, and a line in the
   server log explaining why. Nothing is written to either record's chatter.
4. Repeat with two invoices for the **same** customer.
5. **Expected:** the merged file is protected with that customer's password.

## 5. Where protection is deliberately skipped

1. Send an invoice by **Post** (snailmail) rather than email.
2. **Expected:** the document is left readable - a postal printer cannot open an
   encrypted file. A line appears in the log.
3. On a database configured for Factur-X / ZUGFeRD e-invoicing, send an invoice.
4. **Expected:** left readable, with a note on the invoice explaining that
   encrypting it would break the e-invoice.

## 6. The nine languages

Switch **Preferences > Language** through each of EN, FR, ES, DE, NL, PT-BR, IT,
ZH-CN, AR and confirm on the report form that the section title, every field
label, the algorithm choices, the notice placeholder and both banners are
translated, and that Arabic renders right-to-left.
