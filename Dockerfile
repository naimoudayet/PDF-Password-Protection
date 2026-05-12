FROM odoo:19
USER root

# pypdf is the maintained successor to PyPDF2 and shares the same
# PdfReader/PdfWriter API. Installing 'pypdf' side-steps two issues:
#   1. apt-installed PyPDF2 can't be uninstalled by pip
#      ('RECORD file not found' on upgrade).
#   2. Newer Ubuntu bases (v18, v19 = 24.04) require
#      --break-system-packages under PEP 668.
RUN pip install --no-cache-dir pypdf \
 || pip install --no-cache-dir --break-system-packages pypdf

USER odoo
