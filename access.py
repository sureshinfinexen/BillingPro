"""Access control: Super Admin, shop feature packs, page assignments."""
from __future__ import annotations

import json
from typing import Any

# Feature packs Super Admin can enable/disable per shop (selling modules)
FEATURE_CATALOG = [
    {"key": "billing", "label": "Billing (New Bill, Bills list)", "core": True},
    {"key": "holds", "label": "Hold / Recall bills", "core": False},
    {"key": "returns", "label": "Returns / credit notes", "core": False},
    {"key": "credit", "label": "Credit sales (Udhaar)", "core": False},
    {"key": "loyalty", "label": "Loyalty points", "core": False},
    {"key": "coupons", "label": "Coupons / promotions", "core": False},
    {"key": "stock", "label": "Stock view & adjust", "core": True},
    {"key": "reorder", "label": "Reorder / low stock alerts", "core": False},
    {"key": "products", "label": "Product master", "core": True},
    {"key": "purchases", "label": "Purchases / GRN", "core": False},
    {"key": "warehouses", "label": "Warehouses & transfers", "core": False},
    {"key": "batches", "label": "Batch / expiry tracking", "core": False},
    {"key": "day_close", "label": "Day-end closing", "core": False},
    {"key": "shifts", "label": "Shift / counter reports", "core": False},
    {"key": "reports", "label": "Sales reports dashboard", "core": False},
    {"key": "gst_export", "label": "GST CSV export", "core": False},
    {"key": "audit", "label": "Audit log", "core": False},
    {"key": "offline", "label": "Offline mode", "core": False},
    {"key": "multi_shop", "label": "Multi-branch (extra shops)", "core": False},
]

# Screens store Admin can assign to each user/cashier
PAGE_CATALOG = [
    {"key": "dashboard", "label": "Dashboard", "feature": "reports", "roles": ("admin", "superadmin")},
    {"key": "reports", "label": "Reports", "feature": "reports", "roles": ("admin", "superadmin")},
    {"key": "shifts", "label": "Shift / counter sales", "feature": "shifts", "roles": ("admin", "superadmin")},
    {"key": "day_close", "label": "Day close", "feature": "day_close", "roles": ("admin", "cashier", "superadmin")},
    {"key": "billing", "label": "New Bill", "feature": "billing", "roles": ("admin", "cashier", "superadmin")},
    {"key": "holds", "label": "Held bills", "feature": "holds", "roles": ("admin", "cashier", "superadmin")},
    {"key": "bills", "label": "Bills list / view / edit", "feature": "billing", "roles": ("admin", "cashier", "superadmin")},
    {"key": "returns", "label": "Returns", "feature": "returns", "roles": ("admin", "cashier", "superadmin")},
    {"key": "credit", "label": "Credit (Udhaar)", "feature": "credit", "roles": ("admin", "cashier", "superadmin")},
    {"key": "stock", "label": "Stock screen", "feature": "stock", "roles": ("admin", "cashier", "superadmin")},
    {"key": "reorder", "label": "Reorder list", "feature": "reorder", "roles": ("admin", "cashier", "superadmin")},
    {"key": "products", "label": "Products", "feature": "products", "roles": ("admin", "superadmin")},
    {"key": "purchases", "label": "Purchases / GRN", "feature": "purchases", "roles": ("admin", "superadmin")},
    {"key": "warehouses", "label": "Warehouses", "feature": "warehouses", "roles": ("admin", "superadmin")},
    {"key": "batches", "label": "Batches", "feature": "batches", "roles": ("admin", "superadmin")},
    {"key": "loyalty", "label": "Loyalty", "feature": "loyalty", "roles": ("admin", "superadmin")},
    {"key": "coupons", "label": "Coupons", "feature": "coupons", "roles": ("admin", "superadmin")},
    {"key": "gst_export", "label": "GST export", "feature": "gst_export", "roles": ("admin", "superadmin")},
    {"key": "audit", "label": "Audit log", "feature": "audit", "roles": ("admin", "superadmin")},
    {"key": "shops", "label": "Shops (store list)", "feature": None, "roles": ("admin", "superadmin")},
    {"key": "counters", "label": "Counters", "feature": None, "roles": ("admin", "superadmin")},
    {"key": "employees", "label": "Employees", "feature": None, "roles": ("admin", "superadmin")},
    {"key": "permissions", "label": "Assign pages to users", "feature": None, "roles": ("admin", "superadmin")},
    {"key": "features", "label": "Shop feature packs (Super Admin)", "feature": None, "roles": ("superadmin",)},
    {"key": "offline", "label": "Offline mode", "feature": "offline", "roles": ("admin", "superadmin")},
    {"key": "settings", "label": "Settings", "feature": None, "roles": ("admin", "superadmin")},
]

DEFAULT_CASHIER_PAGES = "billing,bills,holds,stock,returns,credit,day_close,reorder"

DEFAULT_ADMIN_PAGES = ",".join(
    p["key"] for p in PAGE_CATALOG if "admin" in p["roles"] and p["key"] != "features"
)

CORE_FEATURES = [f["key"] for f in FEATURE_CATALOG if f.get("core")]
ALL_FEATURE_KEYS = [f["key"] for f in FEATURE_CATALOG]
DEFAULT_NEW_SHOP_FEATURES = CORE_FEATURES + [
    "holds", "returns", "day_close", "reports", "shifts", "reorder",
]


def is_superadmin(u) -> bool:
    return bool(u and u.get("role") == "superadmin")


def is_store_admin(u) -> bool:
    return bool(u and u.get("role") == "admin")


def is_admin(u) -> bool:
    """Store admin OR super admin."""
    return is_superadmin(u) or is_store_admin(u)


def parse_csv(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {x.strip() for x in str(raw).split(",") if x.strip()}


def parse_features(raw) -> set[str]:
    """Shop.features may be JSON list or CSV. Empty/null = all features (legacy)."""
    if raw is None or raw == "":
        return set(ALL_FEATURE_KEYS)
    s = str(raw).strip()
    if not s:
        return set(ALL_FEATURE_KEYS)
    if s.startswith("["):
        try:
            data = json.loads(s)
            return set(str(x) for x in data)
        except Exception:
            pass
    return parse_csv(s)


def features_to_storage(keys) -> str:
    return json.dumps(sorted(set(keys)))


def shop_has_feature(shop_features: set[str] | None, feature_key: str | None) -> bool:
    if feature_key is None:
        return True
    if shop_features is None:
        return True
    # Core POS modules stay available for every licensed shop
    if feature_key in CORE_FEATURES:
        return True
    return feature_key in shop_features


def user_pages(u) -> set[str]:
    if not u:
        return set()
    if is_superadmin(u):
        return {p["key"] for p in PAGE_CATALOG}
    raw = (u.get("pages") or "").strip()
    if not raw:
        raw = (u.get("permissions") or "").strip()
        # Legacy permission tokens → ignore as pages if they look like old perms
        if raw and any(x in raw for x in ("bills_view", "stock_view", "hold", "credit_view")):
            raw = ""
    if not raw:
        if is_store_admin(u):
            return parse_csv(DEFAULT_ADMIN_PAGES)
        return parse_csv(DEFAULT_CASHIER_PAGES)
    return parse_csv(raw)


def _role_allows(u, meta: dict) -> bool:
    role = (u or {}).get("role")
    if role == "superadmin":
        return True
    if role == "admin":
        return "admin" in meta["roles"]
    if role == "cashier":
        return "cashier" in meta["roles"]
    return False


def can_page(u, page_key: str, shop_features: set[str] | None = None) -> bool:
    """Can this user open this page (role + assigned pages + shop feature)?"""
    if not u:
        return False
    if is_superadmin(u):
        return True
    meta = next((p for p in PAGE_CATALOG if p["key"] == page_key), None)
    if not meta:
        return False
    if not _role_allows(u, meta):
        return False
    if page_key not in user_pages(u):
        return False
    return shop_has_feature(shop_features, meta.get("feature"))


def can_feature(u, feature_key: str, shop_features: set[str] | None = None) -> bool:
    if is_superadmin(u):
        return True
    return shop_has_feature(shop_features, feature_key)


PERM_TO_PAGE = {
    "billing": "billing",
    "bills_view": "bills",
    "bills_edit": "bills",
    "stock_view": "stock",
    "hold": "holds",
    "returns": "returns",
    "day_close": "day_close",
    "credit_view": "credit",
    "products": "products",
    "reports": "reports",
    "all": "*",
}


def can(u, perm: str, shop_features: set[str] | None = None) -> bool:
    """Backward-compatible permission check used by advanced routes."""
    if not u:
        return False
    if is_superadmin(u):
        return True
    page = PERM_TO_PAGE.get(perm, perm)
    if page == "*":
        return is_admin(u) or "all" in parse_csv(u.get("permissions") or "")
    return can_page(u, page, shop_features)


def pages_for_role(role: str) -> list[dict]:
    if role == "superadmin":
        return list(PAGE_CATALOG)
    if role == "admin":
        return [p for p in PAGE_CATALOG if "admin" in p["roles"] and p["key"] != "features"]
    return [p for p in PAGE_CATALOG if "cashier" in p["roles"]]


def assignable_pages(role: str, shop_features: set[str] | None) -> list[dict]:
    """Pages a store admin may assign to a user of given role (filtered by shop features)."""
    out = []
    for p in pages_for_role(role):
        if shop_has_feature(shop_features, p.get("feature")):
            out.append(p)
    return out
