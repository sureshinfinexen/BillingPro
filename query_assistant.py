"""BillingPro Data Assistant — safe intent → SQL templates (no free-form SQL).

Super Admin: all shops (optional shop filter).
Store Admin: own shop only; cross-shop / all-store asks are denied.
Cashier: no access (UI + API gated).
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from access import is_superadmin, is_store_admin


DENY_MSG = "You are not allowed to view that information. Store users can only see data for their own shop."

SUGGESTION_CHIPS: list[str] = [
    "Today's sales summary",
    "Top 10 products by sales",
    "Low stock products",
    "Out of stock items",
    "Recent bills",
    "Sales by payment mode",
    "Sales by counter",
    "Cashier performance",
    "GST collected this month",
    "Top customers by spend",
    "Credit outstanding",
    "Bills this week",
    "Monthly revenue trend",
    "Returns this month",
    "Held bills list",
    "Stock value report",
    "Reorder list",
    "Sales by hour today",
    "Average bill value",
    "Coupon usage",
]

# Superadmin-only chips (cross-shop / platform)
SUPERADMIN_CHIPS: list[str] = [
    "Sales by shop",
    "Compare all shops today",
    "Staff count by shop",
]

CHIP_INTENTS: dict[str, tuple[str, dict[str, Any]]] = {
    "today's sales summary": ("today_summary", {}),
    "todays sales summary": ("today_summary", {}),
    "top 10 products by sales": ("top_products", {"days": 30, "limit": 10}),
    "low stock products": ("low_stock", {}),
    "out of stock items": ("out_of_stock", {}),
    "recent bills": ("recent_bills", {"days": 7, "limit": 20}),
    "sales by payment mode": ("sales_by_payment", {"days": 30}),
    "sales by counter": ("sales_by_counter", {"days": 30}),
    "cashier performance": ("cashier_performance", {"days": 30}),
    "gst collected this month": ("gst_collected", {"days": 30}),
    "top customers by spend": ("top_customers", {"days": 90, "limit": 10}),
    "credit outstanding": ("credit_outstanding", {}),
    "bills this week": ("recent_bills", {"days": 7, "limit": 50}),
    "monthly revenue trend": ("monthly_sales", {"days": 365}),
    "returns this month": ("returns_list", {"days": 30, "limit": 50}),
    "held bills list": ("held_bills", {"limit": 30}),
    "stock value report": ("stock_value", {}),
    "reorder list": ("reorder", {}),
    "sales by hour today": ("sales_by_hour", {}),
    "average bill value": ("avg_bill", {"days": 30}),
    "coupon usage": ("coupon_usage", {"days": 90}),
    "sales by shop": ("sales_by_shop", {"days": 30}),
    "compare all shops today": ("compare_shops_today", {}),
    "staff count by shop": ("staff_by_shop", {}),
}

# Query keys only Super Admin may run
SUPERADMIN_ONLY = {
    "sales_by_shop",
    "compare_shops_today",
    "staff_by_shop",
}

# Phrases that imply cross-shop / out-of-scope for store users
CROSS_SHOP_PHRASES = (
    "all shops", "all stores", "every shop", "every store", "other shop",
    "other store", "across shops", "across stores", "compare shops",
    "compare stores", "by shop", "by store", "each shop", "each store",
    "all branches", "other branch",
)


def serialize_cell(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


def serialize_rows(rows: list) -> list[list]:
    out = []
    for row in rows:
        if hasattr(row, "keys"):
            out.append([serialize_cell(row[k]) for k in row.keys()])
        else:
            out.append([serialize_cell(c) for c in row])
    return out


def rows_to_csv(columns: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def _norm(text: str) -> str:
    t = text.lower().strip()
    t = t.replace("×", "x").replace("–", "-").replace("—", "-").replace("'", "'")
    t = re.sub(r"\s+", " ", t)
    return t


def _days(text: str, default: int = 30) -> int:
    m = re.search(r"last\s+(\d+)\s+days?", text)
    if m:
        return min(int(m.group(1)), 365)
    if "this month" in text or "month" in text:
        return 30
    if "this week" in text or "week" in text:
        return 7
    if "today" in text:
        return 1
    if "year" in text:
        return 365
    return default


def _limit(text: str, default: int = 10) -> int:
    m = re.search(r"top\s+(\d+)", text)
    if m:
        return min(int(m.group(1)), 100)
    return default


def chips_for_user(u) -> list[str]:
    chips = list(SUGGESTION_CHIPS)
    if is_superadmin(u):
        chips = chips + SUPERADMIN_CHIPS
    return chips


def can_use_assistant(u) -> bool:
    """Superadmin and store admin only."""
    return bool(u and (is_superadmin(u) or is_store_admin(u)))


def detect_out_of_scope(u, question: str, qkey: str, shop_filter: str | None) -> str | None:
    """Return deny message if store admin asks outside their shop."""
    if not u:
        return DENY_MSG
    if is_superadmin(u):
        return None
    if not is_store_admin(u):
        return DENY_MSG
    if qkey in SUPERADMIN_ONLY:
        return DENY_MSG
    t = _norm(question)
    if any(p in t for p in CROSS_SHOP_PHRASES):
        return DENY_MSG
    # Store admin cannot pick another shop
    if shop_filter and str(shop_filter).isdigit():
        try:
            if int(shop_filter) != int(u.get("shop_id") or 0):
                return DENY_MSG
        except (TypeError, ValueError):
            return DENY_MSG
    if not u.get("shop_id"):
        return "Your account is not linked to a shop. Ask Super Admin to assign a shop."
    return None


def match_intent(text: str) -> tuple[str, dict[str, Any]]:
    raw = text.strip()
    if not raw:
        return "help", {}
    t = _norm(raw)
    if t in CHIP_INTENTS:
        qkey, params = CHIP_INTENTS[t]
        return qkey, dict(params)

    days = _days(t)
    lim = _limit(t)

    rules = [
        (["help", "what can", "how to"], [], "help", {}),
        (["today", "summary"], ["sale"], "today_summary", {}),
        (["low stock", "reorder"], [], "low_stock", {}),
        (["out of stock", "zero stock"], [], "out_of_stock", {}),
        (["payment"], ["sale", "mode", "cash", "upi", "card"], "sales_by_payment", {"days": days}),
        (["counter"], ["sale"], "sales_by_counter", {"days": days}),
        (["cashier", "staff performance", "employee sales"], [], "cashier_performance", {"days": days}),
        (["gst", "tax collected"], [], "gst_collected", {"days": days}),
        (["customer"], ["top", "spend", "revenue"], "top_customers", {"days": days, "limit": lim}),
        (["credit", "udhaar", "outstanding"], [], "credit_outstanding", {}),
        (["return"], [], "returns_list", {"days": days, "limit": 50}),
        (["hold", "held"], [], "held_bills", {"limit": 30}),
        (["stock value", "inventory value"], [], "stock_value", {}),
        (["product"], ["top", "sale", "selling"], "top_products", {"days": days, "limit": lim}),
        (["recent bill", "latest bill"], [], "recent_bills", {"days": days, "limit": lim}),
        (["monthly", "trend", "revenue"], [], "monthly_sales", {"days": 365}),
        (["hour"], ["sale", "today"], "sales_by_hour", {}),
        (["average bill", "avg bill"], [], "avg_bill", {"days": days}),
        (["coupon"], [], "coupon_usage", {"days": days}),
        (["by shop", "per shop", "each shop"], ["sale"], "sales_by_shop", {"days": days}),
        (["compare"], ["shop"], "compare_shops_today", {}),
        (["staff count"], ["shop"], "staff_by_shop", {}),
    ]
    for any_of, all_req, key, params in rules:
        if any(a in t for a in any_of) and (not all_req or all(a in t for a in all_req)):
            return key, dict(params)
    return "help", {}


def _shop_sql(u, shop_filter: str | None, alias: str = "") -> tuple[str, tuple]:
    """AND shop_id filter. Superadmin: optional filter; store admin: forced shop."""
    col = f"{alias}.shop_id" if alias else "shop_id"
    if is_superadmin(u):
        if shop_filter and str(shop_filter).isdigit():
            return f" AND {col}=?", (int(shop_filter),)
        return "", ()
    sid = u.get("shop_id")
    if not sid:
        return " AND 1=0", ()
    return f" AND {col}=?", (int(sid),)


async def _fetch(db, sql: str, args: tuple = ()) -> list[list]:
    rows = await db.fetchall(sql, args)
    if not rows:
        return []
    keys = list(rows[0].keys())
    return [[serialize_cell(r[k]) for k in keys] for r in rows]


async def _cols(db, sql: str, args: tuple = ()) -> tuple[list[str], list[list]]:
    rows = await db.fetchall(sql, args)
    if not rows:
        return [], []
    keys = list(rows[0].keys())
    labels = [k.replace("_", " ").title() for k in keys]
    data = [[serialize_cell(r[k]) for k in keys] for r in rows]
    return labels, data


def _since(days: int) -> str:
    return (date.today() - timedelta(days=max(1, days) - 1)).isoformat()


async def run_query(
    db, qkey: str, params: dict, u, shop_filter: str | None = None,
) -> dict[str, Any]:
    """Execute whitelist handler. Raises PermissionError if denied."""
    handlers = {
        "help": _q_help,
        "today_summary": _q_today_summary,
        "top_products": _q_top_products,
        "low_stock": _q_low_stock,
        "out_of_stock": _q_out_of_stock,
        "recent_bills": _q_recent_bills,
        "sales_by_payment": _q_sales_by_payment,
        "sales_by_counter": _q_sales_by_counter,
        "cashier_performance": _q_cashier_performance,
        "gst_collected": _q_gst_collected,
        "top_customers": _q_top_customers,
        "credit_outstanding": _q_credit_outstanding,
        "monthly_sales": _q_monthly_sales,
        "returns_list": _q_returns,
        "held_bills": _q_held,
        "stock_value": _q_stock_value,
        "reorder": _q_reorder,
        "sales_by_hour": _q_sales_by_hour,
        "avg_bill": _q_avg_bill,
        "coupon_usage": _q_coupon_usage,
        "sales_by_shop": _q_sales_by_shop,
        "compare_shops_today": _q_compare_shops_today,
        "staff_by_shop": _q_staff_by_shop,
    }
    fn = handlers.get(qkey, _q_help)
    result = await fn(db, params, u, shop_filter)
    result["query_key"] = qkey
    return result


async def _q_help(db, params, u, shop_filter):
    scope = "all shops" if is_superadmin(u) else "your shop only"
    return {
        "title": "How to use BillingPro Assistant",
        "columns": ["Tip"],
        "rows": [
            [f"Your access scope: {scope}."],
            ["Click a suggestion chip or type a question about sales, stock, bills, GST, credit."],
            ["Results are read-only safe reports — not free SQL."],
            ["Store admins cannot view other shops' data."],
            ["Download CSV from the result panel when needed."],
        ],
        "sql_hint": "help",
    }


async def _q_today_summary(db, params, u, shop_filter):
    sh, sp = _shop_sql(u, shop_filter)
    today = date.today().isoformat()
    cols, rows = await _cols(
        db,
        f"""SELECT COUNT(*) AS bills,
                   COALESCE(SUM(total),0) AS revenue,
                   COALESCE(SUM(tax),0) AS gst,
                   COALESCE(SUM(discount),0) AS discount
            FROM bill
            WHERE bill_date=? AND COALESCE(status,'completed')='completed'{sh}""",
        (today, *sp),
    )
    return {"title": "Today's Sales Summary", "columns": cols, "rows": rows, "sql_hint": "bill today"}


async def _q_top_products(db, params, u, shop_filter):
    days = int(params.get("days") or 30)
    lim = int(params.get("limit") or 10)
    sh, sp = _shop_sql(u, shop_filter, "b")
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT COALESCE(bi.name, bi.sku) AS product, bi.sku,
                   COALESCE(SUM(bi.qty),0) AS qty_sold,
                   COALESCE(SUM(bi.line_total),0) AS amount
            FROM bill_item bi
            JOIN bill b ON b.id=bi.bill_id
            WHERE b.bill_date>=? AND COALESCE(b.status,'completed')='completed'{sh}
            GROUP BY bi.name, bi.sku
            ORDER BY qty_sold DESC LIMIT ?""",
        (since, *sp, lim),
    )
    return {"title": f"Top Products (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill_item"}


async def _q_low_stock(db, params, u, shop_filter):
    sh, sp = _shop_sql(u, shop_filter)
    cols, rows = await _cols(
        db,
        f"""SELECT sku, name, stock, COALESCE(reorder_level,5) AS reorder_level, unit
            FROM product WHERE active=1 AND stock <= COALESCE(reorder_level,5){sh}
            ORDER BY stock ASC, name LIMIT 100""",
        sp,
    )
    return {"title": "Low Stock Products", "columns": cols, "rows": rows, "sql_hint": "product"}


async def _q_out_of_stock(db, params, u, shop_filter):
    sh, sp = _shop_sql(u, shop_filter)
    cols, rows = await _cols(
        db,
        f"""SELECT sku, name, stock, unit FROM product
            WHERE active=1 AND stock<=0{sh} ORDER BY name LIMIT 100""",
        sp,
    )
    return {"title": "Out of Stock", "columns": cols, "rows": rows, "sql_hint": "product"}


async def _q_recent_bills(db, params, u, shop_filter):
    days = int(params.get("days") or 7)
    lim = int(params.get("limit") or 20)
    sh, sp = _shop_sql(u, shop_filter, "b")
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT b.bill_no, b.bill_date, b.customer_name, b.payment_mode,
                   b.total, s.name AS cashier, c.name AS counter
            FROM bill b
            LEFT JOIN staff s ON s.id=b.staff_id
            LEFT JOIN counter c ON c.id=b.counter_id
            WHERE b.bill_date>=? AND COALESCE(b.status,'completed')='completed'{sh}
            ORDER BY b.id DESC LIMIT ?""",
        (since, *sp, lim),
    )
    return {"title": f"Recent Bills (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill"}


async def _q_sales_by_payment(db, params, u, shop_filter):
    days = int(params.get("days") or 30)
    sh, sp = _shop_sql(u, shop_filter)
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT payment_mode, COUNT(*) AS bills, COALESCE(SUM(total),0) AS amount
            FROM bill
            WHERE bill_date>=? AND COALESCE(status,'completed')='completed'{sh}
            GROUP BY payment_mode ORDER BY amount DESC""",
        (since, *sp),
    )
    return {"title": f"Sales by Payment (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill"}


async def _q_sales_by_counter(db, params, u, shop_filter):
    days = int(params.get("days") or 30)
    sh, sp = _shop_sql(u, shop_filter, "b")
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT COALESCE(c.name,'(none)') AS counter, COUNT(b.id) AS bills,
                   COALESCE(SUM(b.total),0) AS amount
            FROM bill b LEFT JOIN counter c ON c.id=b.counter_id
            WHERE b.bill_date>=? AND COALESCE(b.status,'completed')='completed'{sh}
            GROUP BY c.name ORDER BY amount DESC""",
        (since, *sp),
    )
    return {"title": f"Sales by Counter (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill+counter"}


async def _q_cashier_performance(db, params, u, shop_filter):
    days = int(params.get("days") or 30)
    sh, sp = _shop_sql(u, shop_filter, "b")
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT COALESCE(s.name,'(none)') AS cashier, COUNT(b.id) AS bills,
                   COALESCE(SUM(b.total),0) AS amount
            FROM bill b LEFT JOIN staff s ON s.id=b.staff_id
            WHERE b.bill_date>=? AND COALESCE(b.status,'completed')='completed'{sh}
            GROUP BY s.name ORDER BY amount DESC""",
        (since, *sp),
    )
    return {"title": f"Cashier Performance (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill+staff"}


async def _q_gst_collected(db, params, u, shop_filter):
    days = int(params.get("days") or 30)
    sh, sp = _shop_sql(u, shop_filter)
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT COALESCE(SUM(cgst),0) AS cgst, COALESCE(SUM(sgst),0) AS sgst,
                   COALESCE(SUM(tax),0) AS gst_total, COUNT(*) AS bills
            FROM bill
            WHERE bill_date>=? AND COALESCE(status,'completed')='completed'{sh}""",
        (since, *sp),
    )
    return {"title": f"GST Collected (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill tax"}


async def _q_top_customers(db, params, u, shop_filter):
    days = int(params.get("days") or 90)
    lim = int(params.get("limit") or 10)
    sh, sp = _shop_sql(u, shop_filter)
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT COALESCE(NULLIF(customer_name,''), customer_mobile, 'Walk-in') AS customer,
                   COALESCE(customer_mobile,'') AS mobile,
                   COUNT(*) AS bills, COALESCE(SUM(total),0) AS spent
            FROM bill
            WHERE bill_date>=? AND COALESCE(status,'completed')='completed'
              AND (COALESCE(customer_mobile,'')<>'' OR COALESCE(customer_name,'')<>''){sh}
            GROUP BY 1, 2 ORDER BY spent DESC LIMIT ?""",
        (since, *sp, lim),
    )
    return {"title": f"Top Customers (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill customers"}


async def _q_credit_outstanding(db, params, u, shop_filter):
    sh, sp = _shop_sql(u, shop_filter, "b")
    cols, rows = await _cols(
        db,
        f"""SELECT COALESCE(c.name, b.customer_name) AS customer, c.mobile,
                   b.bill_no, cl.amount, cl.paid, (cl.amount-cl.paid) AS due
            FROM credit_ledger cl
            JOIN bill b ON b.id=cl.bill_id
            LEFT JOIN customer c ON c.id=cl.customer_id
            WHERE cl.amount > cl.paid{sh}
            ORDER BY due DESC LIMIT 100""",
        sp,
    )
    return {"title": "Credit Outstanding", "columns": cols, "rows": rows, "sql_hint": "credit_ledger"}


async def _q_monthly_sales(db, params, u, shop_filter):
    sh, sp = _shop_sql(u, shop_filter)
    since = _since(365)
    cols, rows = await _cols(
        db,
        f"""SELECT SUBSTR(bill_date,1,7) AS month, COUNT(*) AS bills,
                   COALESCE(SUM(total),0) AS revenue
            FROM bill
            WHERE bill_date>=? AND COALESCE(status,'completed')='completed'{sh}
            GROUP BY SUBSTR(bill_date,1,7) ORDER BY month""",
        (since, *sp),
    )
    return {"title": "Monthly Revenue Trend", "columns": cols, "rows": rows, "sql_hint": "bill by month"}


async def _q_returns(db, params, u, shop_filter):
    days = int(params.get("days") or 30)
    lim = int(params.get("limit") or 50)
    sh, sp = _shop_sql(u, shop_filter, "r")
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT r.return_no, r.return_date, b.bill_no, r.total, r.reason, s.name AS staff
            FROM return_note r
            LEFT JOIN bill b ON b.id=r.bill_id
            LEFT JOIN staff s ON s.id=r.staff_id
            WHERE r.return_date>=?{sh}
            ORDER BY r.id DESC LIMIT ?""",
        (since, *sp, lim),
    )
    return {"title": f"Returns (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "return_note"}


async def _q_held(db, params, u, shop_filter):
    lim = int(params.get("limit") or 30)
    sh, sp = _shop_sql(u, shop_filter, "h")
    cols, rows = await _cols(
        db,
        f"""SELECT h.hold_no, h.customer_name, h.customer_mobile, s.name AS staff, h.created_at
            FROM bill_hold h LEFT JOIN staff s ON s.id=h.staff_id
            WHERE 1=1{sh} ORDER BY h.id DESC LIMIT ?""",
        (*sp, lim),
    )
    return {"title": "Held Bills", "columns": cols, "rows": rows, "sql_hint": "bill_hold"}


async def _q_stock_value(db, params, u, shop_filter):
    sh, sp = _shop_sql(u, shop_filter)
    cols, rows = await _cols(
        db,
        f"""SELECT COUNT(*) AS products,
                   COALESCE(SUM(stock),0) AS total_qty,
                   COALESCE(SUM(stock * COALESCE(cost,0)),0) AS cost_value,
                   COALESCE(SUM(stock * COALESCE(price,0)),0) AS sell_value
            FROM product WHERE active=1{sh}""",
        sp,
    )
    return {"title": "Stock Value", "columns": cols, "rows": rows, "sql_hint": "product stock*cost"}


async def _q_reorder(db, params, u, shop_filter):
    return await _q_low_stock(db, params, u, shop_filter)


async def _q_sales_by_hour(db, params, u, shop_filter):
    sh, sp = _shop_sql(u, shop_filter)
    today = date.today().isoformat()
    cols, rows = await _cols(
        db,
        f"""SELECT SUBSTR(COALESCE(created_at, bill_date),12,2) AS hour,
                   COUNT(*) AS bills, COALESCE(SUM(total),0) AS amount
            FROM bill
            WHERE bill_date=? AND COALESCE(status,'completed')='completed'{sh}
            GROUP BY SUBSTR(COALESCE(created_at, bill_date),12,2)
            ORDER BY hour""",
        (today, *sp),
    )
    return {"title": "Sales by Hour Today", "columns": cols, "rows": rows, "sql_hint": "bill created_at"}


async def _q_avg_bill(db, params, u, shop_filter):
    days = int(params.get("days") or 30)
    sh, sp = _shop_sql(u, shop_filter)
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT COUNT(*) AS bills,
                   COALESCE(SUM(total),0) AS revenue,
                   CASE WHEN COUNT(*)=0 THEN 0
                        ELSE ROUND(COALESCE(SUM(total),0)/COUNT(*),2) END AS avg_bill
            FROM bill
            WHERE bill_date>=? AND COALESCE(status,'completed')='completed'{sh}""",
        (since, *sp),
    )
    return {"title": f"Average Bill (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill avg"}


async def _q_coupon_usage(db, params, u, shop_filter):
    days = int(params.get("days") or 90)
    sh, sp = _shop_sql(u, shop_filter)
    since = _since(days)
    cols, rows = await _cols(
        db,
        f"""SELECT COALESCE(NULLIF(coupon_code,''),'(none)') AS coupon,
                   COUNT(*) AS bills, COALESCE(SUM(total),0) AS amount
            FROM bill
            WHERE bill_date>=? AND COALESCE(status,'completed')='completed'
              AND COALESCE(coupon_code,'')<>''{sh}
            GROUP BY coupon_code ORDER BY bills DESC""",
        (since, *sp),
    )
    return {"title": f"Coupon Usage (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill coupon"}


async def _q_sales_by_shop(db, params, u, shop_filter):
    if not is_superadmin(u):
        raise PermissionError(DENY_MSG)
    days = int(params.get("days") or 30)
    since = _since(days)
    cols, rows = await _cols(
        db,
        """SELECT COALESCE(sh.name,'(no shop)') AS shop, sh.code,
                  COUNT(b.id) AS bills, COALESCE(SUM(b.total),0) AS revenue
           FROM bill b LEFT JOIN shop sh ON sh.id=b.shop_id
           WHERE b.bill_date>=? AND COALESCE(b.status,'completed')='completed'
           GROUP BY sh.name, sh.code ORDER BY revenue DESC""",
        (since,),
    )
    return {"title": f"Sales by Shop (last {days} days)", "columns": cols, "rows": rows, "sql_hint": "bill×shop"}


async def _q_compare_shops_today(db, params, u, shop_filter):
    if not is_superadmin(u):
        raise PermissionError(DENY_MSG)
    today = date.today().isoformat()
    cols, rows = await _cols(
        db,
        """SELECT COALESCE(sh.name,'(no shop)') AS shop,
                  COUNT(b.id) AS bills, COALESCE(SUM(b.total),0) AS revenue
           FROM shop sh
           LEFT JOIN bill b ON b.shop_id=sh.id AND b.bill_date=? AND COALESCE(b.status,'completed')='completed'
           WHERE sh.active=1
           GROUP BY sh.name ORDER BY revenue DESC""",
        (today,),
    )
    return {"title": "Compare All Shops Today", "columns": cols, "rows": rows, "sql_hint": "shop×bill today"}


async def _q_staff_by_shop(db, params, u, shop_filter):
    if not is_superadmin(u):
        raise PermissionError(DENY_MSG)
    cols, rows = await _cols(
        db,
        """SELECT COALESCE(sh.name,'(none)') AS shop, st.role, COUNT(*) AS staff_count
           FROM staff st LEFT JOIN shop sh ON sh.id=st.shop_id
           WHERE st.active=1 AND st.role<>'superadmin'
           GROUP BY sh.name, st.role ORDER BY shop, st.role""",
        (),
    )
    return {"title": "Staff Count by Shop", "columns": cols, "rows": rows, "sql_hint": "staff×shop"}
