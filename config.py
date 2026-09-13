"""BillingPro — configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "BillingPro"
APP_TAGLINE = "Point of Sale & Billing"
COMPANY_NAME = "Infinexen Technologies"
COMPANY_YEAR = 2026
COMPANY_EMAIL = "suresh.baskaran@infinexen.com"
COMPANY_MOBILE = "+91 87780 99759"

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://postgres:pgadmin@localhost:5433/billingpro",
)
SECRET_KEY = os.getenv("SECRET_KEY", "billingpro-secret-key-change-me-2026")
DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "ta", "hi")

THEME = {
    "primary": "#0F766E",
    "primary_dark": "#0B5D57",
    "primary_light": "#D6ECE8",
    "accent": "#F4B41A",
    "success": "#27AE60",
    "danger": "#E74C3C",
    "warning": "#F39C12",
    "text_primary": "#1A2332",
    "text_secondary": "#5D6D7E",
    "sidebar_bg": "#0B3D3A",
    "sidebar_text": "#BDC3C7",
    "sidebar_active": "#0F766E",
    "bg_main": "#F0F7F5",
    "card_bg": "#FFFFFF",
}
