"""Advanced BillingPro features — schema + routes registered onto main app."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from typing import Any, Callable
from urllib.parse import quote

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from markupsafe import Markup

# Filled by register_advanced()
_D: dict[str, Any] = {}


def money(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


async def ensure_advanced_schema(db):
    """Create tables/columns for all advanced POS features."""
    ensure_column = _D["ensure_column"]

    await db.execute("""
    CREATE TABLE IF NOT EXISTS shop (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        address TEXT DEFAULT '',
        active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS warehouse (
        id SERIAL PRIMARY KEY,
        shop_id INTEGER REFERENCES shop(id),
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS warehouse_stock (
        id SERIAL PRIMARY KEY,
        warehouse_id INTEGER NOT NULL REFERENCES warehouse(id),
        product_id INTEGER NOT NULL REFERENCES product(id),
        qty REAL NOT NULL DEFAULT 0,
        UNIQUE(warehouse_id, product_id)
    );
    CREATE TABLE IF NOT EXISTS supplier (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        mobile TEXT DEFAULT '',
        gstin TEXT DEFAULT '',
        active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS purchase (
        id SERIAL PRIMARY KEY,
        grn_no TEXT UNIQUE NOT NULL,
        purchase_date TEXT NOT NULL,
        supplier_id INTEGER REFERENCES supplier(id),
        warehouse_id INTEGER REFERENCES warehouse(id),
        staff_id INTEGER REFERENCES staff(id),
        shop_id INTEGER REFERENCES shop(id),
        subtotal REAL DEFAULT 0,
        tax REAL DEFAULT 0,
        total REAL DEFAULT 0,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS purchase_item (
        id SERIAL PRIMARY KEY,
        purchase_id INTEGER NOT NULL REFERENCES purchase(id),
        product_id INTEGER REFERENCES product(id),
        sku TEXT,
        name TEXT,
        qty REAL NOT NULL,
        cost REAL NOT NULL DEFAULT 0,
        batch_no TEXT DEFAULT '',
        expiry TEXT DEFAULT '',
        line_total REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS product_batch (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES product(id),
        warehouse_id INTEGER REFERENCES warehouse(id),
        batch_no TEXT NOT NULL,
        expiry TEXT DEFAULT '',
        qty REAL NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS bill_hold (
        id SERIAL PRIMARY KEY,
        hold_no TEXT UNIQUE NOT NULL,
        counter_id INTEGER REFERENCES counter(id),
        staff_id INTEGER REFERENCES staff(id),
        shop_id INTEGER REFERENCES shop(id),
        customer_name TEXT DEFAULT '',
        customer_mobile TEXT DEFAULT '',
        cart_json TEXT NOT NULL,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS bill_payment (
        id SERIAL PRIMARY KEY,
        bill_id INTEGER NOT NULL REFERENCES bill(id),
        mode TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        card_last4 TEXT DEFAULT '',
        ref TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS return_note (
        id SERIAL PRIMARY KEY,
        return_no TEXT UNIQUE NOT NULL,
        bill_id INTEGER REFERENCES bill(id),
        return_date TEXT NOT NULL,
        staff_id INTEGER REFERENCES staff(id),
        counter_id INTEGER REFERENCES counter(id),
        reason TEXT DEFAULT '',
        total REAL DEFAULT 0,
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS return_item (
        id SERIAL PRIMARY KEY,
        return_id INTEGER NOT NULL REFERENCES return_note(id),
        bill_item_id INTEGER,
        product_id INTEGER REFERENCES product(id),
        sku TEXT,
        name TEXT,
        qty REAL NOT NULL,
        unit_price REAL NOT NULL DEFAULT 0,
        line_total REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS coupon (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        discount_pct REAL DEFAULT 0,
        discount_amt REAL DEFAULT 0,
        min_bill REAL DEFAULT 0,
        active INTEGER DEFAULT 1,
        valid_till TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS loyalty_ledger (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customer(id),
        bill_id INTEGER,
        points REAL NOT NULL DEFAULT 0,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS credit_ledger (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER REFERENCES customer(id),
        bill_id INTEGER REFERENCES bill(id),
        amount REAL NOT NULL DEFAULT 0,
        paid REAL NOT NULL DEFAULT 0,
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS day_close (
        id SERIAL PRIMARY KEY,
        close_date TEXT NOT NULL,
        counter_id INTEGER REFERENCES counter(id),
        staff_id INTEGER REFERENCES staff(id),
        shop_id INTEGER REFERENCES shop(id),
        expected_cash REAL DEFAULT 0,
        actual_cash REAL DEFAULT 0,
        expected_upi REAL DEFAULT 0,
        expected_card REAL DEFAULT 0,
        bills_count INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        staff_id INTEGER,
        action TEXT NOT NULL,
        entity TEXT DEFAULT '',
        entity_id INTEGER,
        detail TEXT DEFAULT '',
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS stock_transfer (
        id SERIAL PRIMARY KEY,
        transfer_no TEXT UNIQUE NOT NULL,
        from_warehouse_id INTEGER REFERENCES warehouse(id),
        to_warehouse_id INTEGER REFERENCES warehouse(id),
        staff_id INTEGER REFERENCES staff(id),
        transfer_date TEXT NOT NULL,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS stock_transfer_item (
        id SERIAL PRIMARY KEY,
        transfer_id INTEGER NOT NULL REFERENCES stock_transfer(id),
        product_id INTEGER REFERENCES product(id),
        qty REAL NOT NULL
    );
    """)

    # Product / customer / staff / bill columns
    await ensure_column(db, "product", "hsn", "TEXT DEFAULT ''")
    await ensure_column(db, "product", "track_batch", "INTEGER DEFAULT 0")
    await ensure_column(db, "product", "reorder_level", "REAL DEFAULT 5")
    await ensure_column(db, "product", "shop_id", "INTEGER")
    await ensure_column(db, "customer", "loyalty_points", "REAL DEFAULT 0")
    await ensure_column(db, "customer", "credit_limit", "REAL DEFAULT 0")
    await ensure_column(db, "staff", "shop_id", "INTEGER")
    await ensure_column(db, "staff", "permissions", "TEXT DEFAULT ''")
    await ensure_column(db, "staff", "pages", "TEXT DEFAULT ''")
    await ensure_column(db, "shop", "features", "TEXT DEFAULT ''")
    await ensure_column(db, "bill", "shop_id", "INTEGER")
    await ensure_column(db, "bill", "status", "TEXT DEFAULT 'completed'")
    await ensure_column(db, "bill", "bill_discount_pct", "REAL DEFAULT 0")
    await ensure_column(db, "bill", "bill_discount_amt", "REAL DEFAULT 0")
    await ensure_column(db, "bill", "coupon_code", "TEXT DEFAULT ''")
    await ensure_column(db, "bill", "is_credit", "INTEGER DEFAULT 0")
    await ensure_column(db, "bill", "loyalty_earned", "REAL DEFAULT 0")
    await ensure_column(db, "bill", "loyalty_redeemed", "REAL DEFAULT 0")
    await ensure_column(db, "bill", "original_bill_id", "INTEGER")
    await ensure_column(db, "bill", "reprint_count", "INTEGER DEFAULT 0")
    await ensure_column(db, "bill", "warehouse_id", "INTEGER")
    await ensure_column(db, "counter", "shop_id", "INTEGER")

    from access import ALL_FEATURE_KEYS, features_to_storage

    # Seed default shop + warehouse (full feature pack for demo Main Shop)
    shop = await db.fetchone("SELECT id FROM shop LIMIT 1")
    if not shop:
        await db.execute(
            "INSERT INTO shop (name,code,address,features,active) VALUES (?,?,?,?,1)",
            ("Main Shop", "S1", "Head Office", features_to_storage(ALL_FEATURE_KEYS)),
        )
        shop = await db.fetchone("SELECT id FROM shop LIMIT 1")
    else:
        # Ensure features column populated for legacy shops
        row = await db.fetchone("SELECT id, features FROM shop WHERE id=?", (shop["id"],))
        if row and (row.get("features") is None or str(row.get("features") or "").strip() == ""):
            await db.execute(
                "UPDATE shop SET features=? WHERE id=?",
                (features_to_storage(ALL_FEATURE_KEYS), shop["id"]),
            )
    wid = await db.fetchone("SELECT id FROM warehouse LIMIT 1")
    if not wid and shop:
        await db.execute(
            "INSERT INTO warehouse (shop_id,name,code,active) VALUES (?,?,?,1)",
            (shop["id"], "Main Godown", "W1"),
        )
    # Link existing staff without shop to default shop
    if shop:
        await db.execute(
            "UPDATE staff SET shop_id=? WHERE shop_id IS NULL AND role IN ('admin','cashier')",
            (shop["id"],),
        )
        await db.execute(
            "UPDATE counter SET shop_id=? WHERE shop_id IS NULL",
            (shop["id"],),
        )
    # Seed sample coupon for default shop
    cpn = await db.fetchone("SELECT id FROM coupon WHERE code=?", ("SAVE10",))
    if not cpn:
        shop = await db.fetchone("SELECT id FROM shop ORDER BY id LIMIT 1")
        await db.execute(
            "INSERT INTO coupon (code,discount_pct,discount_amt,min_bill,shop_id,active) VALUES (?,?,?,?,?,1)",
            ("SAVE10", 10, 0, 200, shop["id"] if shop else None),
        )
    await db.execute(
        "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
        ("loyalty_earn_rate", "1"),
    )
    await db.execute(
        "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
        ("loyalty_redeem_value", "1"),
    )
    await db.execute(
        "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
        ("whatsapp_bill_enabled", "1"),
    )
    await db.execute(
        "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
        ("default_gst_pct", "18"),
    )
    await ensure_column(db, "product", "gst_override", "INTEGER DEFAULT 1")


async def audit(db, staff_id, action, entity="", entity_id=None, detail="", shop_id=None):
    await db.execute(
        "INSERT INTO audit_log (staff_id,action,entity,entity_id,detail,shop_id) VALUES (?,?,?,?,?,?)",
        (staff_id, action, entity, entity_id, detail[:2000] if detail else "", shop_id),
    )


def can(u, perm: str, shop_features=None) -> bool:
    """Permission check via access module (role + pages + shop features)."""
    from access import can as access_can
    return access_can(u, perm, shop_features)


def _next_no(prefix: str) -> str:
    return f"{prefix}-{date.today().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"


def register_advanced(app, deps: dict):
    """Attach advanced routes to FastAPI app. deps = shared helpers from app.py."""
    _D.update(deps)
    get_conn = deps["get_conn"]
    templates = deps["templates"]
    tctx = deps["tctx"]
    require_login = deps["require_login"]
    is_admin = deps["is_admin"]
    tr = deps["tr"]
    get_lang = deps["get_lang"]
    d = deps["d"]
    parse_card_last4 = deps["parse_card_last4"]
    build_bill_lines = deps["build_bill_lines"]
    _get = deps["_get"]
    product_effective_gst = deps.get("product_effective_gst") or (lambda r: money((r or {}).get("gst_pct") or 18))
    default_gst_pct = deps.get("default_gst_pct") or (lambda: 18.0)

    # ── helpers exposed for init ──
    deps["ensure_advanced_schema"] = ensure_advanced_schema
    deps["audit"] = audit
    deps["can"] = can

    from access import (
        can_page, is_superadmin, parse_features, FEATURE_CATALOG,
        assignable_pages, features_to_storage, DEFAULT_NEW_SHOP_FEATURES,
        DEFAULT_ADMIN_PAGES, DEFAULT_CASHIER_PAGES, ALL_FEATURE_KEYS,
    )
    from shop_scope import (
        sql_shop, sql_shop_prefixed, require_shop_id, assert_same_shop, shop_id_of,
    )

    def session_features(request) -> set:
        raw = request.session.get("shop_features")
        if raw is None and is_superadmin(require_login(request) or {}):
            return set(ALL_FEATURE_KEYS)
        return parse_features(raw)

    def need(request, perm=None, admin=False, page=None):
        u = require_login(request)
        if not u:
            return None, RedirectResponse("/login")
        feats = session_features(request)
        if admin and not is_admin(u):
            return None, RedirectResponse("/billing")
        if page and not can_page(u, page, feats):
            return None, RedirectResponse("/billing")
        if perm and not can(u, perm, feats):
            return None, RedirectResponse("/billing")
        return u, None

    # ═══════════════════════════════════════════════════════════
    # HOLD / RECALL
    # ═══════════════════════════════════════════════════════════
    @app.get("/holds", response_class=HTMLResponse)
    async def holds_list(request: Request):
        u, redir = need(request, page="holds")
        if redir:
            return redir
        async with await get_conn() as db:
            sh, sp = sql_shop_prefixed(u, "h")
            rows = await db.fetchall(
                f"""SELECT h.*, s.name AS staff_name, c.name AS counter_name
                   FROM bill_hold h
                   LEFT JOIN staff s ON s.id=h.staff_id
                   LEFT JOIN counter c ON c.id=h.counter_id
                   WHERE 1=1{sh}
                   ORDER BY h.id DESC LIMIT 100""",
                sp,
            )
        return templates.TemplateResponse(
            "holds.html", tctx(request, user=u, holds=rows, active="holds")
        )

    @app.post("/api/holds")
    async def hold_create(request: Request):
        u = require_login(request)
        if not u or not can(u, "hold", session_features(request)):
            return JSONResponse({"ok": False, "error": "Not allowed"}, 403)
        body = await request.json()
        items = body.get("items") or []
        if not items:
            return JSONResponse({"ok": False, "error": tr(request, "err_cart_empty")}, 400)
        hold_no = _next_no("HLD")
        async with await get_conn() as db:
            await db.execute(
                """INSERT INTO bill_hold
                   (hold_no,counter_id,staff_id,shop_id,customer_name,customer_mobile,cart_json,notes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    hold_no,
                    int(body.get("counter_id") or u.get("counter_id") or 0) or None,
                    u["id"],
                    require_shop_id(u),
                    str(body.get("customer_name") or ""),
                    "".join(ch for ch in str(body.get("customer_mobile") or "") if ch.isdigit()),
                    json.dumps(items),
                    str(body.get("notes") or ""),
                ),
            )
            hid = await db.lastrowid()
            await audit(db, u["id"], "hold_create", "bill_hold", hid, hold_no)
            await db.commit()
        return JSONResponse({"ok": True, "hold_id": hid, "hold_no": hold_no})

    @app.get("/api/holds/{hid}")
    async def hold_get(request: Request, hid: int):
        u = require_login(request)
        if not u:
            return JSONResponse({"ok": False}, 401)
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            row = await db.fetchone(
                f"SELECT * FROM bill_hold WHERE id=?{sh}", (hid, *sp)
            )
        if not row:
            return JSONResponse({"ok": False, "error": "Not found"}, 404)
        return JSONResponse({
            "ok": True,
            "hold": {
                "id": row["id"],
                "hold_no": row["hold_no"],
                "customer_name": row["customer_name"],
                "customer_mobile": row["customer_mobile"],
                "items": json.loads(row["cart_json"] or "[]"),
            },
        })

    @app.post("/api/holds/{hid}/delete")
    async def hold_delete(request: Request, hid: int):
        u = require_login(request)
        if not u or not can(u, "hold", session_features(request)):
            return JSONResponse({"ok": False}, 403)
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            await db.execute(f"DELETE FROM bill_hold WHERE id=?{sh}", (hid, *sp))
            await audit(db, u["id"], "hold_delete", "bill_hold", hid)
            await db.commit()
        return RedirectResponse("/holds", 303)

    # ═══════════════════════════════════════════════════════════
    # RETURNS
    # ═══════════════════════════════════════════════════════════
    @app.get("/returns", response_class=HTMLResponse)
    async def returns_page(request: Request, bill_no: str = ""):
        u, redir = need(request, page="returns")
        if redir:
            return redir
        bill = None
        items = []
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            if bill_no.strip():
                bill = await db.fetchone(
                    f"SELECT * FROM bill WHERE bill_no=? AND COALESCE(status,'completed')='completed'{sh}",
                    (bill_no.strip().upper(), *sp),
                )
                if bill:
                    items = await db.fetchall(
                        "SELECT * FROM bill_item WHERE bill_id=? ORDER BY id", (bill["id"],)
                    )
            recent = await db.fetchall(
                f"""SELECT r.*, b.bill_no FROM return_note r
                   LEFT JOIN bill b ON b.id=r.bill_id
                   WHERE 1=1{sql_shop_prefixed(u, 'r')[0]}
                   ORDER BY r.id DESC LIMIT 30""",
                sql_shop_prefixed(u, "r")[1],
            )
        return templates.TemplateResponse(
            "returns.html",
            tctx(request, user=u, bill=bill, items=items, bill_no=bill_no,
                 recent=recent, active="returns"),
        )

    @app.post("/api/returns")
    async def create_return(request: Request):
        u = require_login(request)
        if not u or not can(u, "returns", session_features(request)):
            return JSONResponse({"ok": False, "error": "Not allowed"}, 403)
        body = await request.json()
        bill_id = int(body.get("bill_id") or 0)
        ret_items = body.get("items") or []
        if not bill_id or not ret_items:
            return JSONResponse({"ok": False, "error": "Invalid return"}, 400)
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            bill = await db.fetchone(
                f"SELECT * FROM bill WHERE id=?{sh}", (bill_id, *sp)
            )
            if not bill:
                return JSONResponse({"ok": False, "error": "Bill not found"}, 404)
            total = 0.0
            lines = []
            for it in ret_items:
                qty = money(it.get("qty"))
                if qty <= 0:
                    continue
                bi = await db.fetchone("SELECT * FROM bill_item WHERE id=? AND bill_id=?",
                                       (int(it["bill_item_id"]), bill_id))
                if not bi or qty > money(bi["qty"]):
                    return JSONResponse({"ok": False, "error": f"Invalid qty for {it.get('name')}"}, 400)
                lt = money(money(bi["unit_price"]) * qty * (1 + money(bi.get("gst_pct")) / 100))
                total += lt
                lines.append((bi, qty, lt))
            if not lines:
                return JSONResponse({"ok": False, "error": "No lines"}, 400)
            rno = _next_no("RTN")
            await db.execute(
                """INSERT INTO return_note
                   (return_no,bill_id,return_date,staff_id,counter_id,reason,total,shop_id)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (rno, bill_id, date.today().isoformat(), u["id"],
                 bill.get("counter_id"), str(body.get("reason") or ""), money(total),
                 require_shop_id(u)),
            )
            rid = await db.lastrowid()
            for bi, qty, lt in lines:
                await db.execute(
                    """INSERT INTO return_item
                       (return_id,bill_item_id,product_id,sku,name,qty,unit_price,line_total)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (rid, bi["id"], bi.get("product_id"), bi.get("sku"), bi.get("name"),
                     qty, bi["unit_price"], lt),
                )
                if bi.get("product_id"):
                    await db.execute(
                        "UPDATE product SET stock = stock + ? WHERE id=?",
                        (qty, int(bi["product_id"])),
                    )
            await audit(db, u["id"], "return_create", "return_note", rid, rno)
            await db.commit()
        return JSONResponse({"ok": True, "return_no": rno, "total": money(total)})

    # ═══════════════════════════════════════════════════════════
    # COUPON CHECK
    # ═══════════════════════════════════════════════════════════
    @app.get("/api/coupons/check")
    async def coupon_check(request: Request, code: str = "", subtotal: float = 0):
        if not require_login(request):
            return JSONResponse({"ok": False}, 401)
        code = (code or "").strip().upper()
        async with await get_conn() as db:
            c = await db.fetchone(
                "SELECT * FROM coupon WHERE code=? AND active=1" + sql_shop(u)[0],
                (code, *sql_shop(u)[1]),
            )
        if not c:
            return JSONResponse({"ok": False, "error": tr(request, "coupon_invalid")})
        if money(subtotal) < money(c["min_bill"]):
            return JSONResponse({"ok": False, "error": tr(request, "coupon_min_bill")})
        disc_pct = money(c["discount_pct"])
        disc_amt = money(c["discount_amt"])
        if disc_pct > 0:
            amt = money(subtotal * disc_pct / 100)
        else:
            amt = disc_amt
        return JSONResponse({"ok": True, "code": code, "discount_amt": amt, "discount_pct": disc_pct})

    @app.get("/coupons", response_class=HTMLResponse)
    async def coupons_page(request: Request):
        u, redir = need(request, admin=True, page="coupons")
        if redir:
            return redir
        async with await get_conn() as db:
            rows = await db.fetchall(
                "SELECT * FROM coupon WHERE 1=1" + sql_shop(u)[0] + " ORDER BY id DESC",
                sql_shop(u)[1],
            )
        return templates.TemplateResponse(
            "coupons.html", tctx(request, user=u, coupons=rows, active="coupons",
                                 saved=request.query_params.get("saved"))
        )

    @app.post("/coupons")
    async def coupons_save(
        request: Request,
        code: str = Form(...), discount_pct: str = Form("0"),
        discount_amt: str = Form("0"), min_bill: str = Form("0"),
    ):
        u, redir = need(request, admin=True, page="coupons")
        if redir:
            return redir
        async with await get_conn() as db:
            sid = require_shop_id(u)
            # Upsert within shop (composite unique shop_id+code)
            existing = await db.fetchone(
                "SELECT id FROM coupon WHERE code=?" + sql_shop(u)[0],
                (code.strip().upper(), *sql_shop(u)[1]),
            )
            if existing:
                await db.execute(
                    "UPDATE coupon SET discount_pct=?,discount_amt=?,min_bill=?,active=1 WHERE id=?",
                    (money(discount_pct), money(discount_amt), money(min_bill), existing["id"]),
                )
            else:
                await db.execute(
                    """INSERT INTO coupon (code,discount_pct,discount_amt,min_bill,shop_id,active)
                       VALUES (?,?,?,?,?,1)""",
                    (code.strip().upper(), money(discount_pct), money(discount_amt),
                     money(min_bill), sid),
                )
            await audit(db, u["id"], "coupon_save", "coupon", None, code)
            await db.commit()
        return RedirectResponse("/coupons?saved=1", 303)

    # ═══════════════════════════════════════════════════════════
    # PURCHASE / GRN
    # ═══════════════════════════════════════════════════════════
    @app.get("/purchases", response_class=HTMLResponse)
    async def purchases_list(request: Request):
        u, redir = need(request, admin=True, page="purchases")
        if redir:
            return redir
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            sp_p, spp = sql_shop_prefixed(u, "p")
            rows = await db.fetchall(
                f"""SELECT p.*, s.name AS supplier_name, w.name AS warehouse_name
                   FROM purchase p
                   LEFT JOIN supplier s ON s.id=p.supplier_id
                   LEFT JOIN warehouse w ON w.id=p.warehouse_id
                   WHERE 1=1{sp_p}
                   ORDER BY p.id DESC LIMIT 50""",
                spp,
            )
            suppliers = await db.fetchall(
                f"SELECT * FROM supplier WHERE active=1{sh} ORDER BY name", sp
            )
            warehouses = await db.fetchall(
                f"SELECT * FROM warehouse WHERE active=1{sh} ORDER BY name", sp
            )
            products = await db.fetchall(
                f"SELECT id,sku,name FROM product WHERE active=1{sh} ORDER BY name LIMIT 500", sp
            )
        return templates.TemplateResponse(
            "purchases.html",
            tctx(request, user=u, purchases=rows, suppliers=suppliers,
                 warehouses=warehouses, products=products, active="purchases"),
        )

    @app.post("/purchases")
    async def purchase_create(
        request: Request,
        supplier_id: str = Form(""), warehouse_id: str = Form(""),
        product_id: str = Form(...), qty: str = Form(...), cost: str = Form("0"),
        batch_no: str = Form(""), expiry: str = Form(""),
        supplier_name: str = Form(""),
    ):
        u, redir = need(request, admin=True, page="purchases")
        if redir:
            return redir
        q = money(qty)
        c = money(cost)
        if q <= 0:
            return RedirectResponse("/purchases?error=qty", 303)
        async with await get_conn() as db:
            shop_sid = require_shop_id(u)
            sh, sp = sql_shop(u)
            sid = int(supplier_id) if supplier_id.strip().isdigit() else None
            if not sid and supplier_name.strip():
                await db.execute(
                    "INSERT INTO supplier (name,shop_id,active) VALUES (?,?,1)",
                    (supplier_name.strip(), shop_sid),
                )
                sid = await db.lastrowid()
            wid = int(warehouse_id) if warehouse_id.strip().isdigit() else None
            if not wid:
                wh = await db.fetchone(
                    f"SELECT id FROM warehouse WHERE active=1{sh} ORDER BY id LIMIT 1", sp
                )
                wid = wh["id"] if wh else None
            prod = await db.fetchone(
                f"SELECT * FROM product WHERE id=? AND active=1{sh}", (int(product_id), *sp)
            )
            if not prod:
                return RedirectResponse("/purchases?error=product", 303)
            grn = _next_no("GRN")
            lt = money(q * c)
            await db.execute(
                """INSERT INTO purchase
                   (grn_no,purchase_date,supplier_id,warehouse_id,staff_id,shop_id,subtotal,tax,total)
                   VALUES (?,?,?,?,?,?,?,0,?)""",
                (grn, date.today().isoformat(), sid, wid, u["id"], shop_sid, lt, lt),
            )
            pid = await db.lastrowid()
            await db.execute(
                """INSERT INTO purchase_item
                   (purchase_id,product_id,sku,name,qty,cost,batch_no,expiry,line_total)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (pid, prod["id"], prod["sku"], prod["name"], q, c,
                 batch_no.strip(), expiry.strip(), lt),
            )
            await db.execute("UPDATE product SET stock = stock + ?, cost=? WHERE id=?",
                             (q, c if c > 0 else prod["cost"], prod["id"]))
            if wid:
                await db.execute(
                    """INSERT INTO warehouse_stock (warehouse_id,product_id,qty)
                       VALUES (?,?,?)
                       ON CONFLICT (warehouse_id,product_id)
                       DO UPDATE SET qty = warehouse_stock.qty + EXCLUDED.qty""",
                    (wid, prod["id"], q),
                )
            if batch_no.strip() or expiry.strip() or prod.get("track_batch"):
                await db.execute(
                    """INSERT INTO product_batch (product_id,warehouse_id,batch_no,expiry,qty,shop_id)
                       VALUES (?,?,?,?,?,?)""",
                    (prod["id"], wid, batch_no.strip() or "DEFAULT", expiry.strip(), q, shop_sid),
                )
            await audit(db, u["id"], "purchase_create", "purchase", pid, grn)
            await db.commit()
        return RedirectResponse("/purchases?saved=1", 303)

    # ═══════════════════════════════════════════════════════════
    # WAREHOUSE + TRANSFER + REORDER + BATCHES
    # ═══════════════════════════════════════════════════════════
    @app.get("/warehouses", response_class=HTMLResponse)
    async def warehouses_page(request: Request):
        u, redir = need(request, admin=True, page="warehouses")
        if redir:
            return redir
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            sw, swp = sql_shop_prefixed(u, "w")
            rows = await db.fetchall(
                f"""SELECT w.*, s.name AS shop_name,
                          (SELECT COALESCE(SUM(qty),0) FROM warehouse_stock ws WHERE ws.warehouse_id=w.id) AS total_qty
                   FROM warehouse w
                   LEFT JOIN shop s ON s.id=w.shop_id
                   WHERE 1=1{sw}
                   ORDER BY w.id""",
                swp,
            )
            if is_superadmin(u):
                shops = await db.fetchall("SELECT * FROM shop WHERE active=1")
            else:
                shops = await db.fetchall(
                    "SELECT * FROM shop WHERE active=1 AND id=?", (u.get("shop_id"),)
                )
            products = await db.fetchall(
                f"SELECT id,sku,name,stock FROM product WHERE active=1{sh} ORDER BY name LIMIT 200",
                sp,
            )
        return templates.TemplateResponse(
            "warehouses.html",
            tctx(request, user=u, warehouses=rows, shops=shops, products=products,
                 active="warehouses", saved=request.query_params.get("saved")),
        )

    @app.post("/warehouses")
    async def warehouse_save(
        request: Request, name: str = Form(...), code: str = Form(...), shop_id: str = Form(""),
    ):
        u, redir = need(request, admin=True, page="warehouses")
        if redir:
            return redir
        async with await get_conn() as db:
            # Force warehouse into user's shop (store users cannot assign other shops)
            sid = require_shop_id(u)
            if is_superadmin(u) and shop_id.isdigit():
                sid = int(shop_id)
            await db.execute(
                "INSERT INTO warehouse (shop_id,name,code,active) VALUES (?,?,?,1)",
                (sid, name.strip(), code.strip().upper()),
            )
            await db.commit()
        return RedirectResponse("/warehouses?saved=1", 303)

    @app.post("/warehouses/transfer")
    async def warehouse_transfer(
        request: Request,
        from_warehouse_id: int = Form(...), to_warehouse_id: int = Form(...),
        product_id: int = Form(...), qty: str = Form(...),
    ):
        u, redir = need(request, admin=True, page="warehouses")
        if redir:
            return redir
        q = money(qty)
        if q <= 0 or from_warehouse_id == to_warehouse_id:
            return RedirectResponse("/warehouses?error=1", 303)
        async with await get_conn() as db:
            src = await db.fetchone(
                "SELECT qty FROM warehouse_stock WHERE warehouse_id=? AND product_id=?",
                (from_warehouse_id, product_id),
            )
            avail = money(src["qty"]) if src else 0
            if avail < q:
                return RedirectResponse("/warehouses?error=stock", 303)
            tno = _next_no("TRF")
            await db.execute(
                """INSERT INTO stock_transfer
                   (transfer_no,from_warehouse_id,to_warehouse_id,staff_id,transfer_date)
                   VALUES (?,?,?,?,?)""",
                (tno, from_warehouse_id, to_warehouse_id, u["id"], date.today().isoformat()),
            )
            tid = await db.lastrowid()
            await db.execute(
                "INSERT INTO stock_transfer_item (transfer_id,product_id,qty) VALUES (?,?,?)",
                (tid, product_id, q),
            )
            await db.execute(
                "UPDATE warehouse_stock SET qty = qty - ? WHERE warehouse_id=? AND product_id=?",
                (q, from_warehouse_id, product_id),
            )
            await db.execute(
                """INSERT INTO warehouse_stock (warehouse_id,product_id,qty) VALUES (?,?,?)
                   ON CONFLICT (warehouse_id,product_id)
                   DO UPDATE SET qty = warehouse_stock.qty + EXCLUDED.qty""",
                (to_warehouse_id, product_id, q),
            )
            await audit(db, u["id"], "stock_transfer", "stock_transfer", tid, tno)
            await db.commit()
        return RedirectResponse("/warehouses?saved=1", 303)

    @app.get("/reorder", response_class=HTMLResponse)
    async def reorder_page(request: Request):
        u, redir = need(request, page="reorder")
        if redir:
            return redir
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            rows = await db.fetchall(
                f"""SELECT id,sku,name,stock,reorder_level,unit,category
                   FROM product WHERE active=1 AND stock <= COALESCE(reorder_level,5){sh}
                   ORDER BY stock ASC, name LIMIT 200""",
                sp,
            )
            expiring = await db.fetchall(
                f"""SELECT b.*, p.name AS product_name, p.sku
                   FROM product_batch b
                   JOIN product p ON p.id=b.product_id
                   WHERE b.expiry IS NOT NULL AND b.expiry <> '' AND b.qty > 0
                     AND b.expiry <= ?{sql_shop_prefixed(u, 'p')[0]}
                   ORDER BY b.expiry LIMIT 100""",
                ((date.today() + timedelta(days=30)).isoformat(), *sql_shop_prefixed(u, "p")[1]),
            )
        return templates.TemplateResponse(
            "reorder.html",
            tctx(request, user=u, products=rows, expiring=expiring, active="reorder"),
        )

    @app.get("/batches", response_class=HTMLResponse)
    async def batches_page(request: Request):
        u, redir = need(request, admin=True, page="batches")
        if redir:
            return redir
        async with await get_conn() as db:
            rows = await db.fetchall(
                f"""SELECT b.*, p.name AS product_name, p.sku, w.name AS warehouse_name
                   FROM product_batch b
                   JOIN product p ON p.id=b.product_id
                   LEFT JOIN warehouse w ON w.id=b.warehouse_id
                   WHERE b.qty > 0{sql_shop_prefixed(u, 'p')[0]}
                   ORDER BY b.expiry NULLS LAST, p.name LIMIT 200""",
                sql_shop_prefixed(u, "p")[1],
            )
        return templates.TemplateResponse(
            "batches.html", tctx(request, user=u, batches=rows, active="batches")
        )

    # ═══════════════════════════════════════════════════════════
    # CREDIT + LOYALTY
    # ═══════════════════════════════════════════════════════════
    @app.get("/credit", response_class=HTMLResponse)
    async def credit_page(request: Request):
        u, redir = need(request, page="credit")
        if redir:
            return redir
        async with await get_conn() as db:
            sb, sbp = sql_shop_prefixed(u, "b")
            rows = await db.fetchall(
                f"""SELECT cl.*, c.name AS customer_name, c.mobile, b.bill_no,
                          (cl.amount - cl.paid) AS due
                   FROM credit_ledger cl
                   LEFT JOIN customer c ON c.id=cl.customer_id
                   LEFT JOIN bill b ON b.id=cl.bill_id
                   WHERE cl.amount > cl.paid{sb}
                   ORDER BY cl.id DESC LIMIT 100""",
                sbp,
            )
        return templates.TemplateResponse(
            "credit.html", tctx(request, user=u, rows=rows, active="credit",
                                saved=request.query_params.get("saved"))
        )

    @app.post("/credit/{cid}/pay")
    async def credit_pay(request: Request, cid: int, amount: str = Form(...)):
        u, redir = need(request, page="credit")
        if redir:
            return redir
        amt = money(amount)
        async with await get_conn() as db:
            # Only pay credits belonging to this shop's bills
            sb, sbp = sql_shop_prefixed(u, "b")
            row = await db.fetchone(
                f"""SELECT cl.* FROM credit_ledger cl
                   JOIN bill b ON b.id=cl.bill_id
                   WHERE cl.id=?{sb}""",
                (cid, *sbp),
            )
            if not row:
                return RedirectResponse("/credit", 303)
            due = money(row["amount"]) - money(row["paid"])
            pay = min(amt, due)
            await db.execute(
                "UPDATE credit_ledger SET paid = paid + ? WHERE id=?", (pay, cid)
            )
            await audit(db, u["id"], "credit_pay", "credit_ledger", cid, str(pay))
            await db.commit()
        return RedirectResponse("/credit?saved=1", 303)

    @app.get("/loyalty", response_class=HTMLResponse)
    async def loyalty_page(request: Request, q: str = ""):
        u, redir = need(request, admin=True, page="loyalty")
        if redir:
            return redir
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            if q.strip():
                like = f"%{q.strip()}%"
                customers = await db.fetchall(
                    f"""SELECT * FROM customer
                       WHERE (mobile ILIKE ? OR name ILIKE ?){sh}
                       ORDER BY loyalty_points DESC LIMIT 50""",
                    (like, like, *sp),
                )
            else:
                customers = await db.fetchall(
                    f"SELECT * FROM customer WHERE 1=1{sh} ORDER BY loyalty_points DESC LIMIT 50",
                    sp,
                )
            ledger = await db.fetchall(
                f"""SELECT l.*, c.name, c.mobile FROM loyalty_ledger l
                   JOIN customer c ON c.id=l.customer_id
                   WHERE 1=1{sql_shop_prefixed(u, 'c')[0]}
                   ORDER BY l.id DESC LIMIT 40""",
                sql_shop_prefixed(u, "c")[1],
            )
        return templates.TemplateResponse(
            "loyalty.html",
            tctx(request, user=u, customers=customers, ledger=ledger, q=q, active="loyalty"),
        )

    # ═══════════════════════════════════════════════════════════
    # DAY CLOSE + SHIFT REPORTS
    # ═══════════════════════════════════════════════════════════
    @app.get("/day-close", response_class=HTMLResponse)
    async def day_close_page(request: Request):
        u, redir = need(request, page="day_close")
        if redir:
            return redir
        today = date.today().isoformat()
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            sb, sbp = sql_shop_prefixed(u, "b")
            if is_admin(u):
                summary = await db.fetchone(
                    f"""SELECT COUNT(*) AS bills,
                              COALESCE(SUM(total),0) AS revenue,
                              COALESCE(SUM(CASE WHEN payment_mode='cash' AND COALESCE(is_credit,0)=0 THEN total ELSE 0 END),0) AS cash,
                              COALESCE(SUM(CASE WHEN payment_mode='upi' THEN total ELSE 0 END),0) AS upi,
                              COALESCE(SUM(CASE WHEN payment_mode='card' THEN total ELSE 0 END),0) AS card,
                              COALESCE(SUM(CASE WHEN COALESCE(is_credit,0)=1 OR payment_mode='credit' THEN total ELSE 0 END),0) AS credit
                       FROM bill
                       WHERE bill_date=? AND COALESCE(status,'completed')='completed'{sh}""",
                    (today, *sp),
                )
            else:
                summary = await db.fetchone(
                    f"""SELECT COUNT(*) AS bills,
                              COALESCE(SUM(total),0) AS revenue,
                              COALESCE(SUM(CASE WHEN payment_mode='cash' AND COALESCE(is_credit,0)=0 THEN total ELSE 0 END),0) AS cash,
                              COALESCE(SUM(CASE WHEN payment_mode='upi' THEN total ELSE 0 END),0) AS upi,
                              COALESCE(SUM(CASE WHEN payment_mode='card' THEN total ELSE 0 END),0) AS card,
                              COALESCE(SUM(CASE WHEN COALESCE(is_credit,0)=1 OR payment_mode='credit' THEN total ELSE 0 END),0) AS credit
                       FROM bill
                       WHERE bill_date=? AND COALESCE(status,'completed')='completed'
                         AND (staff_id=? OR counter_id=?){sh}""",
                    (today, u["id"], u.get("counter_id") or 0, *sp),
                )
            pay_sum = await db.fetchall(
                f"""SELECT bp.mode, COALESCE(SUM(bp.amount),0) AS amt
                   FROM bill_payment bp
                   JOIN bill b ON b.id=bp.bill_id
                   WHERE b.bill_date=?{sb}
                   GROUP BY bp.mode""",
                (today, *sbp),
            )
            history = await db.fetchall(
                f"""SELECT d.*, c.name AS counter_name, s.name AS staff_name
                   FROM day_close d
                   LEFT JOIN counter c ON c.id=d.counter_id
                   LEFT JOIN staff s ON s.id=d.staff_id
                   WHERE 1=1{sql_shop_prefixed(u, 'd')[0]}
                   ORDER BY d.id DESC LIMIT 20""",
                sql_shop_prefixed(u, "d")[1],
            )
        return templates.TemplateResponse(
            "day_close.html",
            tctx(request, user=u, summary=summary, pay_sum=pay_sum, history=history,
                 today=today, active="day_close", saved=request.query_params.get("saved")),
        )

    @app.post("/day-close")
    async def day_close_save(
        request: Request, actual_cash: str = Form(...), notes: str = Form(""),
    ):
        u, redir = need(request, page="day_close")
        if redir:
            return redir
        today = date.today().isoformat()
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            summary = await db.fetchone(
                f"""SELECT COUNT(*) AS bills,
                          COALESCE(SUM(CASE WHEN payment_mode='cash' AND COALESCE(is_credit,0)=0 THEN total ELSE 0 END),0) AS cash,
                          COALESCE(SUM(CASE WHEN payment_mode='upi' THEN total ELSE 0 END),0) AS upi,
                          COALESCE(SUM(CASE WHEN payment_mode='card' THEN total ELSE 0 END),0) AS card
                   FROM bill WHERE bill_date=? AND COALESCE(status,'completed')='completed'{sh}""",
                (today, *sp),
            )
            await db.execute(
                """INSERT INTO day_close
                   (close_date,counter_id,staff_id,shop_id,expected_cash,actual_cash,expected_upi,expected_card,bills_count,notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (today, u.get("counter_id"), u["id"], require_shop_id(u),
                 money(summary["cash"]), money(actual_cash),
                 money(summary["upi"]), money(summary["card"]),
                 int(summary["bills"] or 0), notes.strip()),
            )
            await audit(db, u["id"], "day_close", "day_close", None, today)
            await db.commit()
        return RedirectResponse("/day-close?saved=1", 303)

    @app.get("/shifts", response_class=HTMLResponse)
    async def shifts_page(request: Request):
        u, redir = need(request, admin=True, page="shifts")
        if redir:
            return redir
        async with await get_conn() as db:
            sb, sbp = sql_shop_prefixed(u, "b")
            by_counter = await db.fetchall(
                f"""SELECT c.name AS counter_name, COUNT(b.id) AS bills, COALESCE(SUM(b.total),0) AS amount
                   FROM bill b LEFT JOIN counter c ON c.id=b.counter_id
                   WHERE b.bill_date=? AND COALESCE(b.status,'completed')='completed'{sb}
                   GROUP BY c.name ORDER BY amount DESC""",
                (date.today().isoformat(), *sbp),
            )
            by_staff = await db.fetchall(
                f"""SELECT s.name AS staff_name, COUNT(b.id) AS bills, COALESCE(SUM(b.total),0) AS amount
                   FROM bill b LEFT JOIN staff s ON s.id=b.staff_id
                   WHERE b.bill_date=? AND COALESCE(b.status,'completed')='completed'{sb}
                   GROUP BY s.name ORDER BY amount DESC""",
                (date.today().isoformat(), *sbp),
            )
        return templates.TemplateResponse(
            "shifts.html",
            tctx(request, user=u, by_counter=by_counter, by_staff=by_staff, active="shifts"),
        )

    # ═══════════════════════════════════════════════════════════
    # GST EXPORT
    # ═══════════════════════════════════════════════════════════
    @app.get("/gst-export", response_class=HTMLResponse)
    async def gst_export_page(request: Request):
        u, redir = need(request, admin=True, page="gst_export")
        if redir:
            return redir
        return templates.TemplateResponse(
            "gst_export.html",
            tctx(
                request, user=u, active="gst",
                default_gst=default_gst_pct(),
            ),
        )

    @app.get("/gst-export/csv")
    async def gst_export_csv(request: Request, from_date: str = "", to_date: str = ""):
        u, redir = need(request, admin=True, page="gst_export")
        if redir:
            return redir
        from_date = from_date or date.today().replace(day=1).isoformat()
        to_date = to_date or date.today().isoformat()
        async with await get_conn() as db:
            sb, sbp = sql_shop_prefixed(u, "b")
            rows = await db.fetchall(
                f"""SELECT b.bill_no, b.bill_date, b.customer_name, b.customer_mobile,
                          bi.sku, bi.name, p.hsn, bi.qty, bi.unit_price, bi.gst_pct,
                          bi.cgst_amt, bi.sgst_amt, bi.gst_amt, bi.line_total
                   FROM bill_item bi
                   JOIN bill b ON b.id=bi.bill_id
                   LEFT JOIN product p ON p.id=bi.product_id
                   WHERE b.bill_date >= ? AND b.bill_date <= ?
                     AND COALESCE(b.status,'completed')='completed'{sb}
                   ORDER BY b.bill_date, b.id, bi.id""",
                (from_date, to_date, *sbp),
            )
        buf = io.StringIO()
        w = csv.writer(buf)
        # Formula notes (Excel-friendly comment rows)
        w.writerow(["# BillingPro GST calculation (intra-state)"])
        w.writerow(["# Rate (taxable value / unit) = MRP - Discount"])
        w.writerow(["# Taxable amount (base) = Rate x Qty"])
        w.writerow(["# GST amount = Taxable amount x (GST% / 100)"])
        w.writerow(["# CGST = round(GST amount / 2, 2)"])
        w.writerow(["# SGST = GST amount - CGST  (so CGST + SGST = GST)"])
        w.writerow(["# Line total = Taxable amount + GST amount"])
        w.writerow(["# IGST is not used (same-state supply assumed)"])
        w.writerow([])
        w.writerow([
            "Bill No", "Date", "Customer", "Mobile", "SKU", "Item", "HSN",
            "Qty", "Rate", "GST%", "Taxable (base)", "CGST", "SGST", "GST", "Line Total",
        ])
        for r in rows:
            qty = money(r["qty"])
            rate = money(r["unit_price"])
            base = money(qty * rate)
            w.writerow([
                r["bill_no"], r["bill_date"], r["customer_name"], r["customer_mobile"],
                r["sku"], r["name"], r.get("hsn") or "", qty, rate,
                r["gst_pct"], base, r.get("cgst_amt") or 0, r.get("sgst_amt") or 0,
                r.get("gst_amt") or 0, r["line_total"],
            ])
        data = buf.getvalue().encode("utf-8-sig")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=gstr1_{from_date}_{to_date}.csv"},
        )

    # ═══════════════════════════════════════════════════════════
    # SHOPS + FEATURE PACKS + AUDIT + PAGE ASSIGNMENT + OFFLINE
    # ═══════════════════════════════════════════════════════════
    @app.get("/shops", response_class=HTMLResponse)
    async def shops_page(request: Request):
        u, redir = need(request, admin=True, page="shops")
        if redir:
            return redir
        async with await get_conn() as db:
            if is_superadmin(u):
                rows = await db.fetchall("SELECT * FROM shop ORDER BY id")
            else:
                sid = u.get("shop_id")
                if sid:
                    rows = await db.fetchall("SELECT * FROM shop WHERE id=? ORDER BY id", (sid,))
                else:
                    rows = await db.fetchall("SELECT * FROM shop ORDER BY id LIMIT 1")
        return templates.TemplateResponse(
            "shops.html",
            tctx(
                request, user=u, shops=rows, active="shops",
                feature_catalog=FEATURE_CATALOG,
                is_superadmin=is_superadmin(u),
                saved=request.query_params.get("saved"),
            ),
        )

    @app.post("/shops")
    async def shop_save(
        request: Request, name: str = Form(...), code: str = Form(...), address: str = Form(""),
    ):
        u, redir = need(request, admin=True, page="shops")
        if redir:
            return redir
        # Only superadmin creates shops (selling to new stores)
        if not is_superadmin(u):
            return RedirectResponse("/shops", 303)
        form = await request.form()
        selected = form.getlist("feature")
        if not selected:
            selected = list(DEFAULT_NEW_SHOP_FEATURES)
        # Always include core
        from access import CORE_FEATURES
        for c in CORE_FEATURES:
            if c not in selected:
                selected.append(c)
        async with await get_conn() as db:
            await db.execute(
                "INSERT INTO shop (name,code,address,features,active) VALUES (?,?,?,?,1)",
                (name.strip(), code.strip().upper(), address.strip(), features_to_storage(selected)),
            )
            await db.commit()
        return RedirectResponse("/shops?saved=1", 303)

    @app.get("/shops/{shop_id}/features", response_class=HTMLResponse)
    async def shop_features_page(request: Request, shop_id: int):
        u, redir = need(request, page="features")
        if redir:
            return redir
        if not is_superadmin(u):
            return RedirectResponse("/shops")
        async with await get_conn() as db:
            shop = await db.fetchone("SELECT * FROM shop WHERE id=?", (shop_id,))
            admins = await db.fetchall(
                "SELECT id,name,username FROM staff WHERE role='admin' AND shop_id=? AND active=1",
                (shop_id,),
            )
        if not shop:
            return RedirectResponse("/shops")
        enabled = parse_features(shop.get("features"))
        return templates.TemplateResponse(
            "shop_features.html",
            tctx(
                request, user=u, shop=shop, active="shops",
                feature_catalog=FEATURE_CATALOG, enabled=enabled,
                store_admins=admins,
                saved=request.query_params.get("saved"),
            ),
        )

    @app.post("/shops/{shop_id}/features")
    async def shop_features_save(request: Request, shop_id: int):
        u, redir = need(request, page="features")
        if redir:
            return redir
        if not is_superadmin(u):
            return RedirectResponse("/shops")
        form = await request.form()
        selected = form.getlist("feature")
        from access import CORE_FEATURES
        for c in CORE_FEATURES:
            if c not in selected:
                selected.append(c)
        async with await get_conn() as db:
            await db.execute(
                "UPDATE shop SET features=? WHERE id=?",
                (features_to_storage(selected), shop_id),
            )
            await audit(db, u["id"], "shop_features", "shop", shop_id, ",".join(selected))
            await db.commit()
        return RedirectResponse(f"/shops/{shop_id}/features?saved=1", 303)

    @app.post("/shops/{shop_id}/admin")
    async def shop_create_admin(
        request: Request, shop_id: int,
        name: str = Form(...), username: str = Form(...), password: str = Form("admin123"),
    ):
        u, redir = need(request, page="features")
        if redir:
            return redir
        if not is_superadmin(u):
            return RedirectResponse("/shops")
        uname = username.strip().lower()
        hash_pw = deps["hash_pw"]
        async with await get_conn() as db:
            dup = await db.fetchone("SELECT id FROM staff WHERE username=?", (uname,))
            if dup:
                return RedirectResponse(f"/shops/{shop_id}/features?saved=username_exists", 303)
            await db.execute(
                """INSERT INTO staff (name,username,password,role,shop_id,pages,active)
                   VALUES (?,?,?,?,?,?,1)""",
                (name.strip(), uname, hash_pw(password or "admin123"), "admin",
                 shop_id, DEFAULT_ADMIN_PAGES),
            )
            await audit(db, u["id"], "create_store_admin", "staff", None, uname)
            await db.commit()
        return RedirectResponse(f"/shops/{shop_id}/features?saved=admin_created", 303)

    @app.get("/audit", response_class=HTMLResponse)
    async def audit_page(request: Request):
        u, redir = need(request, admin=True, page="audit")
        if redir:
            return redir
        async with await get_conn() as db:
            sa, sap = sql_shop_prefixed(u, "a")
            rows = await db.fetchall(
                f"""SELECT a.*, s.name AS staff_name FROM audit_log a
                   LEFT JOIN staff s ON s.id=a.staff_id
                   WHERE 1=1{sa}
                   ORDER BY a.id DESC LIMIT 200""",
                sap,
            )
        return templates.TemplateResponse(
            "audit.html", tctx(request, user=u, rows=rows, active="audit")
        )

    @app.get("/permissions", response_class=HTMLResponse)
    async def permissions_page(request: Request):
        u, redir = need(request, admin=True, page="permissions")
        if redir:
            return redir
        feats = session_features(request)
        async with await get_conn() as db:
            if is_superadmin(u):
                staff = await db.fetchall(
                    """SELECT id,name,username,role,pages,permissions,shop_id
                       FROM staff WHERE active=1 AND role!='superadmin' ORDER BY name"""
                )
            else:
                staff = await db.fetchall(
                    """SELECT id,name,username,role,pages,permissions,shop_id
                       FROM staff WHERE active=1 AND role!='superadmin'
                         AND (shop_id=? OR ? IS NULL) ORDER BY name""",
                    (u.get("shop_id"), u.get("shop_id")),
                )
        # Attach assignable page lists per staff role
        staff_out = []
        for s in staff:
            role = s["role"] or "cashier"
            pages_raw = (s.get("pages") or s.get("permissions") or "").strip()
            selected = {x.strip() for x in pages_raw.split(",") if x.strip()} if pages_raw else set()
            if not pages_raw:
                selected = set(
                    (DEFAULT_ADMIN_PAGES if role == "admin" else DEFAULT_CASHIER_PAGES).split(",")
                )
            staff_out.append({
                **dict(s),
                "selected_pages": selected,
                "assignable": assignable_pages(role, feats),
            })
        return templates.TemplateResponse(
            "permissions.html",
            tctx(
                request, user=u, staff=staff_out, active="permissions",
                saved=request.query_params.get("saved"),
            ),
        )

    @app.post("/permissions/{sid}")
    async def permissions_save(request: Request, sid: int):
        u, redir = need(request, admin=True, page="permissions")
        if redir:
            return redir
        form = await request.form()
        selected = form.getlist("page")
        pages_csv = ",".join(selected)
        async with await get_conn() as db:
            row = await db.fetchone("SELECT id,role,shop_id FROM staff WHERE id=?", (sid,))
            if not row or row["role"] == "superadmin":
                return RedirectResponse("/permissions", 303)
            if not is_superadmin(u) and u.get("shop_id") and row.get("shop_id") != u.get("shop_id"):
                return RedirectResponse("/permissions", 303)
            await db.execute(
                "UPDATE staff SET pages=?, permissions=? WHERE id=?",
                (pages_csv, pages_csv, sid),
            )
            await audit(db, u["id"], "pages_update", "staff", sid, pages_csv)
            await db.commit()
        return RedirectResponse("/permissions?saved=1", 303)

    @app.get("/offline", response_class=HTMLResponse)
    async def offline_page(request: Request):
        u, redir = need(request, page="offline")
        if redir:
            return redir
        return templates.TemplateResponse(
            "offline.html", tctx(request, user=u, active="offline")
        )

    @app.get("/static/sw.js")
    async def service_worker():
        js = """
const CACHE='billingpro-offline-v1';
self.addEventListener('install', e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/offline','/static/offline.js'])));
});
self.addEventListener('fetch', e=>{
  e.respondWith(fetch(e.request).catch(()=>caches.match(e.request).then(r=>r||caches.match('/offline'))));
});
"""
        return StreamingResponse(io.BytesIO(js.encode()), media_type="application/javascript")

    # ═══════════════════════════════════════════════════════════
    # BILL EXTRAS: reprint, whatsapp, thermal flag bump
    # ═══════════════════════════════════════════════════════════
    @app.post("/bills/{bid}/reprint")
    async def bill_reprint(request: Request, bid: int):
        u = require_login(request)
        if not u:
            return RedirectResponse("/login")
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            await db.execute(
                f"UPDATE bill SET reprint_count = COALESCE(reprint_count,0)+1 WHERE id=?{sh}",
                (bid, *sp),
            )
            await audit(db, u["id"], "bill_reprint", "bill", bid)
            await db.commit()
        return RedirectResponse(f"/bills/{bid}?reprint=1&thermal=1", 303)

    @app.get("/bills/{bid}/whatsapp")
    async def bill_whatsapp(request: Request, bid: int):
        u = require_login(request)
        if not u:
            return RedirectResponse("/login")
        async with await get_conn() as db:
            sh, sp = sql_shop(u)
            bill = await db.fetchone(f"SELECT * FROM bill WHERE id=?{sh}", (bid, *sp))
            items = await db.fetchall("SELECT name,qty,line_total FROM bill_item WHERE bill_id=?", (bid,))
        if not bill:
            return RedirectResponse("/bills")
        lines = [f"{i['name']} x {i['qty']} = Rs {money(i['line_total'])}" for i in items[:20]]
        text = (
            f"Bill {bill['bill_no']} dated {bill['bill_date']}\n"
            + "\n".join(lines)
            + f"\nTotal: Rs {money(bill['total'])}\nThank you!"
        )
        mobile = "".join(ch for ch in str(bill.get("customer_mobile") or "") if ch.isdigit())
        if mobile and len(mobile) == 10:
            mobile = "91" + mobile
        url = f"https://wa.me/{mobile}?text={quote(text)}" if mobile else f"https://wa.me/?text={quote(text)}"
        return RedirectResponse(url, 302)

    # Coupon admin already; expose products for purchase form via existing list

    @app.get("/api/products/barcode")
    async def barcode_lookup(request: Request, code: str = ""):
        """Exact SKU match for barcode scanners."""
        u = require_login(request)
        if not u:
            return JSONResponse({"ok": False}, 401)
        code = (code or "").strip()
        if not code:
            return JSONResponse({"ok": False, "error": "empty"})
        sh, sp = sql_shop(u)
        async with await get_conn() as db:
            r = await db.fetchone(
                f"""SELECT id,sku,name,mrp,discount,price,cost,stock,unit,gst_pct,gst_override,hsn
                   FROM product WHERE active=1 AND UPPER(sku)=UPPER(?){sh}""",
                (code, *sp),
            )
        if not r:
            return JSONResponse({"ok": False, "error": "not_found"})
        lang = get_lang(request)
        mrp = money(r.get("mrp") or r["price"])
        disc = money(r.get("discount"))
        rate = money(r["price"])
        return JSONResponse({
            "ok": True,
            "product": {
                "id": int(r["id"]), "sku": r["sku"], "name": d(r["name"], lang),
                "mrp": mrp, "discount": disc, "rate": rate, "price": rate,
                "cost": money(r.get("cost")), "stock": money(r["stock"]),
                "unit": r["unit"] or "pcs", "gst_pct": product_effective_gst(r),
                "gst_override": int(r.get("gst_override") or 0),
                "hsn": r.get("hsn") or "",
            },
        })
