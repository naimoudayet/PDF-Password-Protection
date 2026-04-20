FROM odoo:16
USER root

# PyPDF2 — the module's external Python dep for PDF encryption
RUN pip install --break-system-packages --no-cache-dir PyPDF2

USER odoo
