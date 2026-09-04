import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
TEMPLATE_DIR = os.path.join(UPLOAD_DIR, "templates")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SESSION_COOKIE = "admin_session"

# Render target width in pixels for generated certificates (quality control).
RENDER_TARGET_WIDTH = 1800

# Canonical PDF page width (in points) used to scale name font size so that it
# appears at the same relative size on image templates as on PDF templates.
REF_PAGE_WIDTH = 612.0
