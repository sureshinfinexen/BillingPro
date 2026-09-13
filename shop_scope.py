"""Per-shop data isolation helpers.

Store Admin / Cashier: only their shop_id.
Super Admin: all shops (no filter).
"""
from __future__ import annotations

from access import is_superadmin


def shop_id_of(u) -> int | None:
    """User's shop id, or None for superadmin (means all shops)."""
    if not u:
        return None
    if is_superadmin(u):
        return None
    sid = u.get("shop_id")
    try:
        return int(sid) if sid is not None else None
    except (TypeError, ValueError):
        return None


def require_shop_id(u) -> int | None:
    """Shop id that must be stamped on inserts for non-superadmin.
    Superadmin returns None (caller may pick a shop explicitly).
    """
    if not u or is_superadmin(u):
        return u.get("shop_id") if u else None
    sid = shop_id_of(u)
    return sid


def sql_shop(u, column: str = "shop_id") -> tuple[str, tuple]:
    """AND fragment + params for scoped queries.
    Superadmin → ('', ()).
    Store user with no shop → AND 1=0 (see nothing).
    """
    if not u:
        return " AND 1=0", ()
    if is_superadmin(u):
        return "", ()
    sid = shop_id_of(u)
    if sid is None:
        return " AND 1=0", ()
    return f" AND {column}=?", (sid,)


def sql_shop_prefixed(u, alias: str) -> tuple[str, tuple]:
    """Same as sql_shop but for aliased columns, e.g. alias='b' → b.shop_id."""
    col = f"{alias}.shop_id" if alias else "shop_id"
    return sql_shop(u, col)


async def assert_same_shop(db, u, table: str, row_id: int, id_col: str = "id") -> bool:
    """True if row exists and belongs to user's shop (or user is superadmin)."""
    if not u or not row_id:
        return False
    if is_superadmin(u):
        row = await db.fetchone(f"SELECT {id_col} FROM {table} WHERE {id_col}=?", (row_id,))
        return bool(row)
    sid = shop_id_of(u)
    if sid is None:
        return False
    row = await db.fetchone(
        f"SELECT {id_col} FROM {table} WHERE {id_col}=? AND shop_id=?",
        (row_id, sid),
    )
    return bool(row)


async def ensure_shop_isolation_schema(db, ensure_column):
    """Add shop_id to remaining tables + composite uniqueness where needed."""
    await ensure_column(db, "customer", "shop_id", "INTEGER")
    await ensure_column(db, "coupon", "shop_id", "INTEGER")
    await ensure_column(db, "supplier", "shop_id", "INTEGER")
    await ensure_column(db, "return_note", "shop_id", "INTEGER")
    await ensure_column(db, "audit_log", "shop_id", "INTEGER")
    await ensure_column(db, "product_batch", "shop_id", "INTEGER")

    shop = await db.fetchone("SELECT id FROM shop ORDER BY id LIMIT 1")
    if shop:
        sid = shop["id"]
        for table in (
            "product", "staff", "bill", "counter", "customer", "coupon",
            "supplier", "warehouse", "purchase", "bill_hold", "day_close",
            "return_note", "audit_log", "product_batch",
        ):
            try:
                await db.execute(
                    f"UPDATE {table} SET shop_id=? WHERE shop_id IS NULL",
                    (sid,),
                )
            except Exception:
                pass
        # Don't assign shop to superadmin
        await db.execute(
            "UPDATE staff SET shop_id=NULL WHERE role='superadmin'"
        )

    # Relax global unique SKU / mobile / counter code so each shop can reuse codes
    for stmt in (
        "ALTER TABLE product DROP CONSTRAINT IF EXISTS product_sku_key",
        "ALTER TABLE customer DROP CONSTRAINT IF EXISTS customer_mobile_key",
        "ALTER TABLE counter DROP CONSTRAINT IF EXISTS counter_code_key",
        "ALTER TABLE coupon DROP CONSTRAINT IF EXISTS coupon_code_key",
        "ALTER TABLE warehouse DROP CONSTRAINT IF EXISTS warehouse_code_key",
    ):
        try:
            await db.execute(stmt)
        except Exception:
            pass

    for stmt in (
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_product_shop_sku ON product (shop_id, sku)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_customer_shop_mobile ON customer (shop_id, mobile)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_counter_shop_code ON counter (shop_id, code)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_coupon_shop_code ON coupon (shop_id, code)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_warehouse_shop_code ON warehouse (shop_id, code)",
    ):
        try:
            await db.execute(stmt)
        except Exception:
            pass
