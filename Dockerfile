FROM odoo:18
USER root

# pypdf is the forward-maintained successor to PyPDF2. It has the same
# PdfReader/PdfWriter API the module uses. Installing 'pypdf' instead of
# 'PyPDF2' side-steps two real problems:
#
#   1. apt-installed PyPDF2 (debian/ubuntu base images) can't be uninstalled
#      by pip — attempts to upgrade fail with 'RECORD file not found'.
#   2. Older bases (v16 = pip 20, v17 = pip 22) don't recognise the
#      --break-system-packages flag that newer pip 24+ needs under PEP 668.
#
# The module's import code already falls back to pypdf when PyPDF2 isn't
# available. Try plain install; fall back to --break-system-packages only
# when PEP 668 blocks the first attempt (v18, v19 = Ubuntu 24.04).
RUN pip install --no-cache-dir pypdf  || pip install --no-cache-dir --break-system-packages pypdf

USER odoo
