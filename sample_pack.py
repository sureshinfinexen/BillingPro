"""Coherent sample CSV/Excel packs for BillingPro testing & fast setup.

All templates share the same SKUs / supplier names so you can:
  1) upload products → 2) upload GRN → 3) upload supplier template
without fixing codes by hand.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, timedelta
from typing import Any

# ── Shared catalogue (SKU 101+) so it won’t clash with seed 001–005 ──────────

SUPPLIERS = [
    {"name": "Sri Arora Enterprises", "mobile": "9876501001", "gstin": "33AAAAA0000A1Z5"},
    {"name": "Fresh Dairy Co", "mobile": "9876501002", "gstin": "33BBBBB0000B1Z5"},
    {"name": "City Wholesale Mart", "mobile": "9876501003", "gstin": ""},
]

PRODUCTS = [
    # sku, name, mrp, discount, cost, stock, unit, category, gst
    ("101", "Toor Dal 1kg", 140, 10, 95, 0, "bag", "Grocery", 5),
    ("102", "Sugar 1kg", 55, 0, 42, 0, "bag", "Grocery", 5),
    ("103", "Tea Dust 250g", 120, 15, 70, 0, "pack", "Grocery", 5),
    ("104", "Wheat Flour 1kg", 60, 5, 40, 0, "bag", "Grocery", 5),
    ("105", "Curd 400g", 35, 0, 22, 0, "cup", "Dairy", 5),
    ("106", "Butter 100g", 62, 2, 45, 0, "pcs", "Dairy", 12),
    ("107", "Eggs Tray 12", 90, 0, 65, 0, "tray", "Dairy", 0),
    ("108", "Tomato Sauce 500g", 95, 10, 55, 0, "bottle", "Food", 12),
    ("109", "Biscuits Pack", 40, 5, 22, 0, "pack", "Food", 18),
    ("110", "Hand Wash 250ml", 85, 10, 40, 0, "bottle", "Personal Care", 18),
    ("111", "Toothpaste 100g", 75, 8, 38, 0, "pcs", "Personal Care", 18),
    ("112", "Notebook A4", 50, 0, 28, 0, "pcs", "Stationery", 12),
]

# GRN lines: supplier name must match SUPPLIERS; sku must match PRODUCTS
_EXP = (date.today() + timedelta(days=180)).isoformat()
GRN_LINES = [
    {"supplier": "Sri Arora Enterprises", "sku": "101", "qty": "80", "cost": "95", "gst_pct": "5", "batch_no": "TD-A1", "expiry": _EXP},
    {"supplier": "Sri Arora Enterprises", "sku": "102", "qty": "100", "cost": "42", "gst_pct": "5", "batch_no": "SG-A1", "expiry": ""},
    {"supplier": "Sri Arora Enterprises", "sku": "103", "qty": "40", "cost": "70", "gst_pct": "5", "batch_no": "", "expiry": ""},
    {"supplier": "Sri Arora Enterprises", "sku": "104", "qty": "60", "cost": "40", "gst_pct": "5", "batch_no": "WF-A1", "expiry": _EXP},
    {"supplier": "Fresh Dairy Co", "sku": "105", "qty": "50", "cost": "22", "gst_pct": "5", "batch_no": "CU-B1", "expiry": (date.today() + timedelta(days=10)).isoformat()},
    {"supplier": "Fresh Dairy Co", "sku": "106", "qty": "30", "cost": "45", "gst_pct": "12", "batch_no": "BT-B1", "expiry": (date.today() + timedelta(days=60)).isoformat()},
    {"supplier": "Fresh Dairy Co", "sku": "107", "qty": "20", "cost": "65", "gst_pct": "0", "batch_no": "EG-B1", "expiry": (date.today() + timedelta(days=14)).isoformat()},
    {"supplier": "City Wholesale Mart", "sku": "108", "qty": "25", "cost": "55", "gst_pct": "12", "batch_no": "", "expiry": ""},
    {"supplier": "City Wholesale Mart", "sku": "109", "qty": "40", "cost": "22", "gst_pct": "18", "batch_no": "", "expiry": ""},
    {"supplier": "City Wholesale Mart", "sku": "110", "qty": "35", "cost": "40", "gst_pct": "18", "batch_no": "", "expiry": ""},
    {"supplier": "City Wholesale Mart", "sku": "111", "qty": "30", "cost": "38", "gst_pct": "18", "batch_no": "", "expiry": ""},
    {"supplier": "City Wholesale Mart", "sku": "112", "qty": "50", "cost": "28", "gst_pct": "12", "batch_no": "", "expiry": ""},
]

TEMPLATE_LINES = [
    {"sku": "101", "qty": "50", "cost": "95", "gst_pct": "5"},
    {"sku": "102", "qty": "80", "cost": "42", "gst_pct": "5"},
    {"sku": "103", "qty": "20", "cost": "70", "gst_pct": "5"},
    {"sku": "104", "qty": "40", "cost": "40", "gst_pct": "5"},
]

COUPONS = [
    {"code": "WELCOME50", "discount_pct": "0", "discount_amt": "50", "min_bill": "499"},
    {"code": "FLAT10", "discount_pct": "10", "discount_amt": "0", "min_bill": "200"},
    {"code": "SAVE20", "discount_pct": "0", "discount_amt": "20", "min_bill": "150"},
]

CUSTOMERS = [
    {"name": "Ravi Kumar", "mobile": "9000001001", "loyalty_points": "120"},
    {"name": "Priya S", "mobile": "9000001002", "loyalty_points": "45"},
    {"name": "Anand M", "mobile": "9000001003", "loyalty_points": "0"},
    {"name": "Walk-in Demo", "mobile": "9000001099", "loyalty_points": "10"},
]

WAREHOUSES = [
    {"name": "Main Godown", "code": "W1"},
    {"name": "Cold Store", "code": "W2"},
    {"name": "Front Shelf", "code": "W3"},
]

COUNTERS = [
    {"name": "Counter 1", "code": "C1", "location": "Front"},
    {"name": "Counter 2", "code": "C2", "location": "Side"},
    {"name": "Express Counter", "code": "C3", "location": "Exit"},
]

EMPLOYEES = [
    {"name": "Demo Cashier A", "username": "demo_cash_a", "password": "pass123", "role": "cashier", "counter_code": "C1"},
    {"name": "Demo Cashier B", "username": "demo_cash_b", "password": "pass123", "role": "cashier", "counter_code": "C2"},
]

# Catalog for the Samples hub UI
SAMPLE_FILES = [
    {
        "key": "products",
        "title": "Products (master)",
        "desc": "Upload on Products page. Leave stock blank/0; receive stock via GRN.",
        "filename": "01_products_sample.csv",
        "page": "/products",
    },
    {
        "key": "suppliers",
        "title": "Suppliers",
        "desc": "Upload on Samples page or Suppliers (CSV).",
        "filename": "02_suppliers_sample.csv",
        "page": "/suppliers",
    },
    {
        "key": "grn",
        "title": "Purchases / GRN (stock-in)",
        "desc": "Upload on Purchases. Products + supplier names must already exist.",
        "filename": "03_grn_stock_in_sample.csv",
        "page": "/purchases",
    },
    {
        "key": "template",
        "title": "Supplier template lines",
        "desc": "Upload on a Supplier template edit page (CSV or Excel).",
        "filename": "04_supplier_template_products.csv",
        "page": "/purchase-templates",
        "also_xlsx": True,
    },
    {
        "key": "coupons",
        "title": "Coupons",
        "desc": "Upload on Samples page or Coupons (CSV).",
        "filename": "05_coupons_sample.csv",
        "page": "/coupons",
    },
    {
        "key": "customers",
        "title": "Customers / loyalty",
        "desc": "Upload to create mobiles + starting points for billing tests.",
        "filename": "06_customers_loyalty_sample.csv",
        "page": "/loyalty",
    },
    {
        "key": "warehouses",
        "title": "Warehouses",
        "desc": "Reference / upload sample warehouse list.",
        "filename": "07_warehouses_sample.csv",
        "page": "/warehouses",
    },
    {
        "key": "counters",
        "title": "Counters",
        "desc": "Reference sample — create from Counters screen or Load demo pack.",
        "filename": "08_counters_sample.csv",
        "page": "/counters",
    },
    {
        "key": "employees",
        "title": "Employees (cashiers)",
        "desc": "Reference sample usernames for testing Assign pages.",
        "filename": "09_employees_sample.csv",
        "page": "/employees",
    },
]


def _csv_bytes(headers: list[str], rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode("utf-8-sig")


def build_csv(key: str) -> tuple[bytes, str]:
    """Return (bytes, download_filename) for a sample key."""
    meta = next((x for x in SAMPLE_FILES if x["key"] == key), None)
    fname = meta["filename"] if meta else f"{key}_sample.csv"

    if key == "products":
        rows = [[*p] for p in PRODUCTS]
        return _csv_bytes(
            ["sku", "name", "mrp", "discount", "cost", "stock", "unit", "category", "gst"],
            rows,
        ), fname
    if key == "suppliers":
        rows = [[s["name"], s["mobile"], s["gstin"]] for s in SUPPLIERS]
        return _csv_bytes(["name", "mobile", "gstin"], rows), fname
    if key == "grn":
        rows = [[g[k] for k in ("supplier", "sku", "qty", "cost", "gst_pct", "batch_no", "expiry")] for g in GRN_LINES]
        return _csv_bytes(
            ["supplier", "sku", "qty", "cost", "gst_pct", "batch_no", "expiry"],
            rows,
        ), fname
    if key == "template":
        rows = [[t["sku"], t["qty"], t["cost"], t["gst_pct"]] for t in TEMPLATE_LINES]
        return _csv_bytes(["sku", "qty", "cost", "gst_pct"], rows), fname
    if key == "coupons":
        rows = [[c["code"], c["discount_pct"], c["discount_amt"], c["min_bill"]] for c in COUPONS]
        return _csv_bytes(["code", "discount_pct", "discount_amt", "min_bill"], rows), fname
    if key == "customers":
        rows = [[c["name"], c["mobile"], c["loyalty_points"]] for c in CUSTOMERS]
        return _csv_bytes(["name", "mobile", "loyalty_points"], rows), fname
    if key == "warehouses":
        rows = [[w["name"], w["code"]] for w in WAREHOUSES]
        return _csv_bytes(["name", "code"], rows), fname
    if key == "counters":
        rows = [[c["name"], c["code"], c["location"]] for c in COUNTERS]
        return _csv_bytes(["name", "code", "location"], rows), fname
    if key == "employees":
        rows = [[e["name"], e["username"], e["password"], e["role"], e["counter_code"]] for e in EMPLOYEES]
        return _csv_bytes(["name", "username", "password", "role", "counter_code"], rows), fname
    raise KeyError(key)


def build_xlsx(key: str) -> tuple[bytes, str]:
    from openpyxl import Workbook

    data, csv_name = build_csv(key)
    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    wb = Workbook()
    ws = wb.active
    ws.title = key[:31] or "Sample"
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue(), csv_name.replace(".csv", ".xlsx")


def build_zip() -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in SAMPLE_FILES:
            raw, name = build_csv(item["key"])
            zf.writestr(name, raw)
            if item.get("also_xlsx"):
                try:
                    xraw, xname = build_xlsx(item["key"])
                    zf.writestr(xname, xraw)
                except Exception:
                    pass
        zf.writestr(
            "README.txt",
            "BillingPro sample pack\n"
            "======================\n"
            "Order of use:\n"
            "1) 01_products_sample.csv  → Products → Upload\n"
            "2) 02_suppliers_sample.csv → Samples / Suppliers upload\n"
            "3) 03_grn_stock_in_sample.csv → Purchases → Bulk GRN\n"
            "4) 04_supplier_template_products.csv → Supplier template edit → Upload\n"
            "5) 05_coupons / 06_customers as needed\n"
            "Or click Load demo pack on the Samples page to insert everything at once.\n",
        )
    return bio.getvalue()


def write_samples_dir(folder: str) -> list[str]:
    """Write all sample files to disk; return paths written."""
    import os

    os.makedirs(folder, exist_ok=True)
    written = []
    for item in SAMPLE_FILES:
        raw, name = build_csv(item["key"])
        path = os.path.join(folder, name)
        with open(path, "wb") as f:
            f.write(raw)
        written.append(path)
        if item.get("also_xlsx"):
            try:
                xraw, xname = build_xlsx(item["key"])
                xpath = os.path.join(folder, xname)
                with open(xpath, "wb") as f:
                    f.write(xraw)
                written.append(xpath)
            except Exception:
                pass
    zip_path = os.path.join(folder, "BillingPro_All_Samples.zip")
    with open(zip_path, "wb") as f:
        f.write(build_zip())
    written.append(zip_path)
    return written


async def load_demo_pack(db, shop_id: int, hash_pw, staff_id: int | None = None) -> dict:
    """Insert/upsert a full demo dataset for one shop. Returns counts."""
    counts = {
        "suppliers": 0, "products": 0, "warehouses": 0, "coupons": 0,
        "customers": 0, "counters": 0, "employees": 0, "grn": 0, "template": 0,
    }
    if not shop_id:
        return counts

    # Suppliers
    for s in SUPPLIERS:
        ex = await db.fetchone(
            "SELECT id FROM supplier WHERE shop_id=? AND lower(name)=lower(?)",
            (shop_id, s["name"]),
        )
        if ex:
            await db.execute(
                "UPDATE supplier SET mobile=?, gstin=?, active=1 WHERE id=?",
                (s["mobile"], s["gstin"], ex["id"]),
            )
        else:
            await db.execute(
                "INSERT INTO supplier (name,mobile,gstin,shop_id,active) VALUES (?,?,?,?,1)",
                (s["name"], s["mobile"], s["gstin"], shop_id),
            )
            counts["suppliers"] += 1

    # Products
    for sku, name, mrp, disc, cost, stock, unit, cat, gst in PRODUCTS:
        rate = float(mrp) - float(disc)
        ex = await db.fetchone(
            "SELECT id FROM product WHERE shop_id=? AND sku=?", (shop_id, sku)
        )
        if ex:
            await db.execute(
                """UPDATE product SET name=?,mrp=?,discount=?,price=?,cost=?,unit=?,category=?,
                   gst_pct=?,gst_override=1,active=1 WHERE id=?""",
                (name, mrp, disc, rate, cost, unit, cat, gst, ex["id"]),
            )
        else:
            await db.execute(
                """INSERT INTO product
                   (sku,name,mrp,discount,price,cost,stock,unit,category,gst_pct,gst_override,shop_id,active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,1,?,1)""",
                (sku, name, mrp, disc, rate, cost, stock, unit, cat, gst, shop_id),
            )
            counts["products"] += 1

    # Warehouses
    for w in WAREHOUSES:
        ex = await db.fetchone(
            "SELECT id FROM warehouse WHERE shop_id=? AND code=?", (shop_id, w["code"])
        )
        if not ex:
            await db.execute(
                "INSERT INTO warehouse (shop_id,name,code,active) VALUES (?,?,?,1)",
                (shop_id, w["name"], w["code"]),
            )
            counts["warehouses"] += 1

    # Coupons
    for c in COUPONS:
        ex = await db.fetchone(
            "SELECT id FROM coupon WHERE shop_id=? AND code=?", (shop_id, c["code"])
        )
        if not ex:
            await db.execute(
                """INSERT INTO coupon (code,discount_pct,discount_amt,min_bill,shop_id,active)
                   VALUES (?,?,?,?,?,1)""",
                (c["code"], float(c["discount_pct"]), float(c["discount_amt"]),
                 float(c["min_bill"]), shop_id),
            )
            counts["coupons"] += 1

    # Customers
    for c in CUSTOMERS:
        ex = await db.fetchone(
            "SELECT id FROM customer WHERE shop_id=? AND mobile=?", (shop_id, c["mobile"])
        )
        if ex:
            await db.execute(
                "UPDATE customer SET name=?, loyalty_points=? WHERE id=?",
                (c["name"], float(c["loyalty_points"]), ex["id"]),
            )
        else:
            await db.execute(
                "INSERT INTO customer (name,mobile,loyalty_points,shop_id) VALUES (?,?,?,?)",
                (c["name"], c["mobile"], float(c["loyalty_points"]), shop_id),
            )
            counts["customers"] += 1

    # Counters
    for c in COUNTERS:
        ex = await db.fetchone(
            "SELECT id FROM counter WHERE shop_id=? AND code=?", (shop_id, c["code"])
        )
        if not ex:
            await db.execute(
                "INSERT INTO counter (name,code,location,shop_id,active) VALUES (?,?,?,?,1)",
                (c["name"], c["code"], c["location"], shop_id),
            )
            counts["counters"] += 1

    # Employees (demo cashiers)
    for e in EMPLOYEES:
        ex = await db.fetchone("SELECT id FROM staff WHERE username=?", (e["username"],))
        ctr = await db.fetchone(
            "SELECT id FROM counter WHERE shop_id=? AND code=?", (shop_id, e["counter_code"])
        )
        pages = "billing,bills,holds,stock,returns,credit,day_close,reorder"
        if not ex:
            await db.execute(
                """INSERT INTO staff (name,username,password,role,counter_id,shop_id,pages,active)
                   VALUES (?,?,?,?,?,?,?,1)""",
                (e["name"], e["username"], hash_pw(e["password"]), e["role"],
                 ctr["id"] if ctr else None, shop_id, pages),
            )
            counts["employees"] += 1

    # One multi-line GRN for demo stock-in
    from datetime import datetime as _dt

    wh = await db.fetchone(
        "SELECT id FROM warehouse WHERE shop_id=? ORDER BY id LIMIT 1", (shop_id,)
    )
    wid = wh["id"] if wh else None
    already = await db.fetchone(
        "SELECT id FROM purchase WHERE shop_id=? AND notes=?", (shop_id, "demo pack")
    )
    if not already and GRN_LINES:
        subtotal = tax = 0.0
        lines = []
        for g in GRN_LINES:
            prod = await db.fetchone(
                "SELECT id,sku,name FROM product WHERE shop_id=? AND sku=?",
                (shop_id, g["sku"]),
            )
            if not prod:
                continue
            qty = float(g["qty"])
            cost = float(g["cost"])
            gst = float(g["gst_pct"] or 0)
            line_sub = qty * cost
            line_tax = line_sub * gst / 100.0
            line_total = line_sub + line_tax
            subtotal += line_sub
            tax += line_tax
            lines.append((prod, qty, cost, gst, line_total, g))
        if lines:
            first_sup = await db.fetchone(
                "SELECT id FROM supplier WHERE shop_id=? AND lower(name)=lower(?)",
                (shop_id, lines[0][5]["supplier"]),
            )
            grn = f"GRN-DEMO-{_dt.now().strftime('%Y%m%d%H%M%S')}-{shop_id}"
            await db.execute(
                """INSERT INTO purchase
                   (grn_no,purchase_date,supplier_id,warehouse_id,staff_id,shop_id,subtotal,tax,total,notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (grn, date.today().isoformat(), first_sup["id"] if first_sup else None,
                 wid, staff_id, shop_id, round(subtotal, 2), round(tax, 2),
                 round(subtotal + tax, 2), "demo pack"),
            )
            pid = await db.lastrowid()
            for prod, qty, cost, gst, line_total, g in lines:
                await db.execute(
                    """INSERT INTO purchase_item
                       (purchase_id,product_id,sku,name,qty,cost,gst_pct,batch_no,expiry,line_total)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (pid, prod["id"], prod["sku"], prod["name"], qty, cost, gst,
                     g.get("batch_no") or "", g.get("expiry") or "", round(line_total, 2)),
                )
                await db.execute(
                    "UPDATE product SET stock=COALESCE(stock,0)+?, cost=? WHERE id=?",
                    (qty, cost, prod["id"]),
                )
                if wid:
                    await db.execute(
                        """INSERT INTO warehouse_stock (warehouse_id,product_id,qty) VALUES (?,?,?)
                           ON CONFLICT (warehouse_id,product_id) DO UPDATE
                           SET qty = warehouse_stock.qty + EXCLUDED.qty""",
                        (wid, prod["id"], qty),
                    )
                batch_no = (g.get("batch_no") or "").strip()
                if batch_no:
                    await db.execute(
                        """INSERT INTO product_batch (product_id,warehouse_id,batch_no,expiry,qty,shop_id)
                           VALUES (?,?,?,?,?,?)""",
                        (prod["id"], wid, batch_no, g.get("expiry") or None, qty, shop_id),
                    )
                counts["grn"] += 1

    # Supplier purchase template
    tpl = await db.fetchone(
        "SELECT id FROM purchase_template WHERE shop_id=? AND name=? AND COALESCE(active,1)=1",
        (shop_id, "Monthly Grocery — Sri Arora"),
    )
    if not tpl:
        sup = await db.fetchone(
            "SELECT id FROM supplier WHERE shop_id=? AND lower(name)=lower(?)",
            (shop_id, "Sri Arora Enterprises"),
        )
        await db.execute(
            """INSERT INTO purchase_template (name,supplier_id,shop_id,notes,active)
               VALUES (?,?,?,?,1)""",
            ("Monthly Grocery — Sri Arora", sup["id"] if sup else None, shop_id, "Demo monthly list"),
        )
        tpl = await db.fetchone(
            "SELECT id FROM purchase_template WHERE shop_id=? AND name=?",
            (shop_id, "Monthly Grocery — Sri Arora"),
        )
        counts["template"] += 1
    if tpl:
        for t in TEMPLATE_LINES:
            prod = await db.fetchone(
                "SELECT id,sku,name FROM product WHERE shop_id=? AND sku=?",
                (shop_id, t["sku"]),
            )
            if not prod:
                continue
            ex = await db.fetchone(
                "SELECT id FROM purchase_template_item WHERE template_id=? AND product_id=?",
                (tpl["id"], prod["id"]),
            )
            if ex:
                await db.execute(
                    "UPDATE purchase_template_item SET qty=?,cost=?,gst_pct=?,name=? WHERE id=?",
                    (float(t["qty"]), float(t["cost"]), float(t["gst_pct"]), prod["name"], ex["id"]),
                )
            else:
                await db.execute(
                    """INSERT INTO purchase_template_item
                       (template_id,product_id,sku,name,qty,cost,gst_pct)
                       VALUES (?,?,?,?,?,?,?)""",
                    (tpl["id"], prod["id"], prod["sku"], prod["name"],
                     float(t["qty"]), float(t["cost"]), float(t["gst_pct"])),
                )

    return counts
