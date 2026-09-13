"""Theme presets — same model as FactPro (1 default + 5 light + 5 dark)."""

DEFAULT_THEME = {
    "app_name": "BillingPro",
    "app_tagline": "Point of Sale & Billing",
    "logo_url": "",
    "theme_preset": "default",
    "primary_color": "#0F766E",
    "primary_dark": "#0B5D57",
    "sidebar_bg": "#0B3D3A",
    "accent_color": "#F4B41A",
    "bg_main": "#F0F7F5",
    "card_bg": "#FFFFFF",
}

THEME_COLOR_KEYS = (
    "primary_color",
    "primary_dark",
    "sidebar_bg",
    "accent_color",
    "bg_main",
    "card_bg",
)

THEME_PRESETS = {
    "default": {
        "label": "Default (Teal)",
        "mode": "default",
        "colors": {
            "primary_color": "#0F766E",
            "primary_dark": "#0B5D57",
            "sidebar_bg": "#0B3D3A",
            "accent_color": "#F4B41A",
            "bg_main": "#F0F7F5",
            "card_bg": "#FFFFFF",
        },
    },
    "light_ocean": {
        "label": "Ocean Blue",
        "mode": "light",
        "colors": {
            "primary_color": "#2563EB",
            "primary_dark": "#1D4ED8",
            "sidebar_bg": "#1E3A5F",
            "accent_color": "#0EA5E9",
            "bg_main": "#F0F7FF",
            "card_bg": "#FFFFFF",
        },
    },
    "light_forest": {
        "label": "Forest Green",
        "mode": "light",
        "colors": {
            "primary_color": "#059669",
            "primary_dark": "#047857",
            "sidebar_bg": "#14532D",
            "accent_color": "#84CC16",
            "bg_main": "#F0FDF4",
            "card_bg": "#FFFFFF",
        },
    },
    "light_violet": {
        "label": "Soft Violet",
        "mode": "light",
        "colors": {
            "primary_color": "#7C3AED",
            "primary_dark": "#6D28D9",
            "sidebar_bg": "#2E1065",
            "accent_color": "#A78BFA",
            "bg_main": "#F5F3FF",
            "card_bg": "#FFFFFF",
        },
    },
    "light_rose": {
        "label": "Rose Pink",
        "mode": "light",
        "colors": {
            "primary_color": "#E11D48",
            "primary_dark": "#BE123C",
            "sidebar_bg": "#4C0519",
            "accent_color": "#FB7185",
            "bg_main": "#FFF1F2",
            "card_bg": "#FFFFFF",
        },
    },
    "light_slate": {
        "label": "Clean Slate",
        "mode": "light",
        "colors": {
            "primary_color": "#475569",
            "primary_dark": "#334155",
            "sidebar_bg": "#0F172A",
            "accent_color": "#64748B",
            "bg_main": "#F8FAFC",
            "card_bg": "#FFFFFF",
        },
    },
    "dark_midnight": {
        "label": "Midnight",
        "mode": "dark",
        "colors": {
            "primary_color": "#3B82F6",
            "primary_dark": "#2563EB",
            "sidebar_bg": "#020617",
            "accent_color": "#38BDF8",
            "bg_main": "#0F172A",
            "card_bg": "#1E293B",
        },
    },
    "dark_charcoal": {
        "label": "Charcoal",
        "mode": "dark",
        "colors": {
            "primary_color": "#F97316",
            "primary_dark": "#EA580C",
            "sidebar_bg": "#0A0A0A",
            "accent_color": "#FBBF24",
            "bg_main": "#171717",
            "card_bg": "#262626",
        },
    },
    "dark_emerald": {
        "label": "Emerald Night",
        "mode": "dark",
        "colors": {
            "primary_color": "#10B981",
            "primary_dark": "#059669",
            "sidebar_bg": "#022C22",
            "accent_color": "#34D399",
            "bg_main": "#052E26",
            "card_bg": "#0A3D34",
        },
    },
    "dark_purple": {
        "label": "Deep Purple",
        "mode": "dark",
        "colors": {
            "primary_color": "#A855F7",
            "primary_dark": "#9333EA",
            "sidebar_bg": "#1E1B4B",
            "accent_color": "#C084FC",
            "bg_main": "#0F0A1F",
            "card_bg": "#1E1B4B",
        },
    },
    "dark_crimson": {
        "label": "Crimson Dark",
        "mode": "dark",
        "colors": {
            "primary_color": "#EF4444",
            "primary_dark": "#DC2626",
            "sidebar_bg": "#1C1917",
            "accent_color": "#F59E0B",
            "bg_main": "#0C0A09",
            "card_bg": "#292524",
        },
    },
}


def _hex_luminance(hex_color: str) -> float:
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return 1.0
    try:
        r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    except ValueError:
        return 1.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def build_theme(settings: dict, base: dict) -> dict:
    primary = settings.get("primary_color", base["primary"])
    bg = settings.get("bg_main", base["bg_main"])
    card = settings.get("card_bg", base["card_bg"])
    preset = THEME_PRESETS.get(settings.get("theme_preset", "default"), {})
    is_dark = preset.get("mode") == "dark" or _hex_luminance(bg) < 0.35
    if is_dark:
        text_primary, text_secondary = "#F1F5F9", "#94A3B8"
        primary_light, border, border_soft = "#1E293B", "#334155", "#1E293B"
        input_bg, hover_row = card, "rgba(255,255,255,.04)"
    else:
        text_primary, text_secondary = "#1A2332", "#5D6D7E"
        primary_light, border, border_soft = "#D6ECE8", "#e5e7eb", "#f3f4f6"
        input_bg, hover_row = "#ffffff", "#fafafa"
    return {
        "primary": primary,
        "primary_dark": settings.get("primary_dark", base["primary_dark"]),
        "primary_light": primary_light,
        "accent": settings.get("accent_color", base["accent"]),
        "success": "#27AE60",
        "danger": "#E74C3C",
        "warning": "#F39C12",
        "text_primary": text_primary,
        "text_secondary": text_secondary,
        "sidebar_bg": settings.get("sidebar_bg", base["sidebar_bg"]),
        "sidebar_text": "#BDC3C7",
        "sidebar_active": primary,
        "bg_main": bg,
        "card_bg": card,
        "is_dark": is_dark,
        "border": border,
        "border_soft": border_soft,
        "input_bg": input_bg,
        "hover_row": hover_row,
    }
