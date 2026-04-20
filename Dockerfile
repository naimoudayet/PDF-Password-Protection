FROM odoo:18
USER root

# PyPDF2 >= 3.0 has the PdfReader/PdfWriter API this module uses.
# odoo:17 ships PyPDF2 1.x via apt (PdfFileReader API) which would shadow
# the pip install — use -U to force upgrade over the pre-installed version.
# --break-system-packages is needed on pip 23+ (v18/v19 = Ubuntu 24.04,
# PEP 668 enforced); older pips (v16/v17) reject the flag, so try plain
# install first then fall back.
RUN pip install --no-cache-dir -U "PyPDF2>=3.0"  || pip install --no-cache-dir --break-system-packages -U "PyPDF2>=3.0"

USER odoo
