"""BillingPro — POS & billing application."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from markupsafe import Markup

from config import (
    APP_NAME, APP_TAGLINE, COMPANY_NAME, COMPANY_YEAR,
    COMPANY_EMAIL, COMPANY_MOBILE, SECRET_KEY, THEME,
    DEFAULT_LANG, SUPPORTED_LANGS,
)
from database import get_conn
from i18n import t, translator, display_fn, d, und, LANG_LABELS
from themes import (
    DEFAULT_THEME, THEME_PRESETS, THEME_COLOR_KEYS, build_theme,
)
from access import (
    is_admin, is_superadmin, is_store_admin, can_page as check_page, parse_features,
    features_to_storage, ALL_FEATURE_KEYS, DEFAULT_ADMIN_PAGES, DEFAULT_CASHIER_PAGES,
)
from shop_scope import (
    shop_id_of, sql_shop, sql_shop_prefixed, require_shop_id, assert_same_shop,
    ensure_shop_isolation_schema,
)
from query_assistant import (
    can_use_assistant, chips_for_user, match_intent, run_query, rows_to_csv,
    detect_out_of_scope, DENY_MSG,
)

# --------------------------------------------------------------------------- #
_SETTINGS: dict = {}
_base = os.path.dirname(os.path.abspath(__file__))


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _get(key, default=""):
    return _SETTINGS.get(key, default)


def _asset_url(stored: str) -> str:
    """Return public URL for a stored branding path, with cache-bust query."""
    path = (stored or "").strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    disk = os.path.join(_base, path.lstrip("/").replace("/", os.sep))
    try:
        v = int(os.path.getmtime(disk))
        return f"{path}?v={v}"
    except OSError:
        return path


async def _save_brand_upload(upload, stem: str) -> str | None:
    """Save logo/bg upload under uploads/branding/. Returns relative URL path or None."""
    if upload is None:
        return None
    filename = getattr(upload, "filename", None) or ""
    if not filename:
        return None
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return None
    data = await upload.read()
    if not data or len(data) > 2 * 1024 * 1024:
        return None
    brand_dir = os.path.join(_base, "uploads", "branding")
    os.makedirs(brand_dir, exist_ok=True)
    # remove previous files with same stem
    for old in os.listdir(brand_dir):
        if old.startswith(stem + ".") or old == stem:
            try:
                os.remove(os.path.join(brand_dir, old))
            except OSError:
                pass
    out_name = f"{stem}{ext}"
    with open(os.path.join(brand_dir, out_name), "wb") as f:
        f.write(data)
    return f"/uploads/branding/{out_name}"


def _clear_brand_file(stored: str):
    path = (stored or "").strip()
    if not path or not path.startswith("/uploads/"):
        return
    disk = os.path.join(_base, path.lstrip("/").replace("/", os.sep))
    try:
        if os.path.isfile(disk):
            os.remove(disk)
    except OSError:
        pass


def money(v) -> float:
    try:
        return float(Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


async def reload_settings():
    global _SETTINGS
    try:
        async with await get_conn() as db:
            rows = await db.fetchall("SELECT key, value FROM app_settings")
            if rows:
                _SETTINGS = {r["key"]: r["value"] for r in rows}
    except Exception:
        pass


def cur_user(request: Request):
    return request.session.get("user")


def get_lang(request: Request) -> str:
    lang = request.session.get("lang") or _get("default_lang", DEFAULT_LANG)
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def tr(request: Request, key: str, **fmt) -> str:
    """Translate key for current request language; optional .format kwargs."""
    msg = t(key, get_lang(request))
    if fmt:
        try:
            return msg.format(**fmt)
        except (KeyError, ValueError):
            return msg
    return msg


def tctx(request: Request, **kw) -> dict:
    lang = get_lang(request)
    settings = dict(DEFAULT_THEME)
    settings.update(_SETTINGS)
    # Per-user theme overrides shop default
    user = kw.get("user", cur_user(request))
    user_preset = ""
    if user:
        user_preset = (user.get("theme_preset") or "").strip()
        if not user_preset:
            user_preset = (request.session.get("theme_preset") or "").strip()
        if user_preset and user_preset in THEME_PRESETS:
            settings["theme_preset"] = user_preset
            settings.update(THEME_PRESETS[user_preset]["colors"])
        elif user_preset == "custom" and request.session.get("theme_colors"):
            settings["theme_preset"] = "custom"
            try:
                colors = json.loads(request.session.get("theme_colors") or "{}")
                if isinstance(colors, dict):
                    settings.update(colors)
            except Exception:
                pass
    tagline_raw = _get("app_tagline", APP_TAGLINE)
    if "shop_features" in kw:
        shop_features = kw["shop_features"]
        if not isinstance(shop_features, set):
            shop_features = parse_features(shop_features)
    elif is_superadmin(user):
        shop_features = set(ALL_FEATURE_KEYS)
    else:
        shop_features = parse_features(request.session.get("shop_features"))
    out = {
        "request": request,
        "APP_NAME": _get("app_name", APP_NAME),
        "APP_TAGLINE": d(tagline_raw, lang),
        "APP_LOGO_URL": _asset_url(_get("app_logo", "")),
        "APP_BG_URL": _asset_url(_get("app_bg_image", "")),
        "THEME": build_theme(settings, THEME),
        "user": user,
        "lang": lang,
        "langs": LANG_LABELS,
        "t": translator(lang),
        "d": display_fn(lang),
        "COMPANY_NAME": COMPANY_NAME,
        "COMPANY_YEAR": COMPANY_YEAR,
        "COMPANY_EMAIL": COMPANY_EMAIL,
        "COMPANY_MOBILE": COMPANY_MOBILE,
        "theme_presets": THEME_PRESETS,
        "shop_features": shop_features,
        "is_admin": is_admin(user),
        "is_superadmin": is_superadmin(user),
        "is_store_admin": is_store_admin(user),
        "show_assistant": can_use_assistant(user),
        "suggestion_chips": chips_for_user(user) if can_use_assistant(user) else [],
        "user_theme_preset": user_preset or settings.get("theme_preset", "default"),
    }
    out.update(kw)
    # Always set after update so callers cannot drop these helpers
    u_final = out.get("user")
    feats = out.get("shop_features")
    if not isinstance(feats, set):
        feats = parse_features(feats)
        out["shop_features"] = feats
    out["is_admin"] = is_admin(u_final)
    out["is_superadmin"] = is_superadmin(u_final)
    out["is_store_admin"] = is_store_admin(u_final)
    out["show_assistant"] = can_use_assistant(u_final)
    if "suggestion_chips" not in kw:
        out["suggestion_chips"] = chips_for_user(u_final) if can_use_assistant(u_final) else []
    out["can_page"] = lambda key, _u=u_final, _f=feats: check_page(_u, key, _f)
    return out


async def ensure_column(db, table: str, column: str, typedef: str):
    row = await db.fetchone(
        """SELECT 1 AS ok FROM information_schema.columns
           WHERE table_schema='public' AND table_name=? AND column_name=?""",
        (table, column),
    )
    if not row:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")


async def init_db():
    async with await get_conn() as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'cashier',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS counter (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            location TEXT,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS product (
            id SERIAL PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            stock REAL NOT NULL DEFAULT 0,
            unit TEXT DEFAULT 'pcs',
            category TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS customer (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            mobile TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS bill (
            id SERIAL PRIMARY KEY,
            bill_no TEXT UNIQUE NOT NULL,
            bill_date TEXT NOT NULL,
            counter_id INTEGER REFERENCES counter(id),
            staff_id INTEGER REFERENCES staff(id),
            customer_name TEXT DEFAULT '',
            subtotal REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            total REAL DEFAULT 0,
            payment_mode TEXT DEFAULT 'cash',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS bill_item (
            id SERIAL PRIMARY KEY,
            bill_id INTEGER NOT NULL REFERENCES bill(id),
            product_id INTEGER REFERENCES product(id),
            sku TEXT,
            name TEXT,
            qty REAL NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        # Migrations for existing DBs
        await ensure_column(db, "staff", "counter_id", "INTEGER REFERENCES counter(id)")
        await ensure_column(db, "staff", "theme_preset", "TEXT DEFAULT ''")
        await ensure_column(db, "product", "cost", "REAL DEFAULT 0")
        await ensure_column(db, "product", "gst_pct", "REAL DEFAULT 18")
        await ensure_column(db, "product", "gst_override", "INTEGER DEFAULT 1")
        await ensure_column(db, "product", "mrp", "REAL DEFAULT 0")
        await ensure_column(db, "product", "discount", "REAL DEFAULT 0")
        await ensure_column(db, "bill", "customer_id", "INTEGER REFERENCES customer(id)")
        await ensure_column(db, "bill", "customer_mobile", "TEXT DEFAULT ''")
        await ensure_column(db, "bill", "customer_saving", "REAL DEFAULT 0")
        await ensure_column(db, "bill_item", "discount", "REAL DEFAULT 0")
        await ensure_column(db, "bill_item", "gst_pct", "REAL DEFAULT 0")
        await ensure_column(db, "bill_item", "gst_amt", "REAL DEFAULT 0")
        await ensure_column(db, "bill_item", "cost", "REAL DEFAULT 0")
        await ensure_column(db, "bill_item", "mrp", "REAL DEFAULT 0")
        await ensure_column(db, "bill_item", "customer_saving", "REAL DEFAULT 0")
        await ensure_column(db, "bill_item", "cgst_amt", "REAL DEFAULT 0")
        await ensure_column(db, "bill_item", "sgst_amt", "REAL DEFAULT 0")
        await ensure_column(db, "bill", "cgst", "REAL DEFAULT 0")
        await ensure_column(db, "bill", "sgst", "REAL DEFAULT 0")
        await ensure_column(db, "bill", "card_last4", "TEXT DEFAULT ''")
        # Advanced feature tables/columns
        from advanced import ensure_advanced_schema as _eas
        # ensure_column must be available; temporary bind:
        import advanced as _adv
        _adv._D["ensure_column"] = ensure_column
        await _eas(db)
        await ensure_shop_isolation_schema(db, ensure_column)
        await db.execute("UPDATE product SET gst_pct=18 WHERE gst_pct IS NULL")
        await db.execute("UPDATE product SET cost=0 WHERE cost IS NULL")
        await db.execute("UPDATE product SET mrp=price WHERE COALESCE(mrp,0)=0 AND COALESCE(price,0)>0")
        await db.execute(
            "UPDATE product SET discount=GREATEST(COALESCE(mrp,0)-COALESCE(price,0),0) WHERE COALESCE(discount,0)=0 AND COALESCE(mrp,0)>COALESCE(price,0)"
        )
        await db.execute(
            "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
            ("bill_greeting", "Welcome! Thank you for shopping with us."),
        )
        await db.execute(
            "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
            ("bill_thanks", "Thank you! Please visit again."),
        )

        # Seed admin
        admin = await db.fetchone("SELECT id FROM staff WHERE username=?", ("admin",))
        if not admin:
            await db.execute(
                "INSERT INTO staff (name,username,password,role,active) VALUES (?,?,?,?,1)",
                ("Administrator", "admin", hash_pw("admin123"), "admin"),
            )
        # Seed platform Super Admin (all features / all shops)
        sa = await db.fetchone("SELECT id FROM staff WHERE username=?", ("superadmin",))
        if not sa:
            await db.execute(
                "INSERT INTO staff (name,username,password,role,pages,active) VALUES (?,?,?,?,?,1)",
                ("Super Admin", "superadmin", hash_pw("superadmin123"), "superadmin", ""),
            )
        # Seed counters
        c = await db.fetchone("SELECT id FROM counter LIMIT 1")
        if not c:
            await db.execute(
                "INSERT INTO counter (name,code,location,active) VALUES (?,?,?,1)",
                ("Counter 1", "C1", "Front"),
            )
            await db.execute(
                "INSERT INTO counter (name,code,location,active) VALUES (?,?,?,1)",
                ("Counter 2", "C2", "Side"),
            )
        # Seed sample products
        p = await db.fetchone("SELECT id FROM product LIMIT 1")
        if not p:
            samples = [
                # sku, name, mrp, discount, cost, stock, unit, cat, gst
                ("RICE1KG", "Rice 1kg", 70, 10, 45, 100, "bag", "Grocery", 5),
                ("OIL1L", "Cooking Oil 1L", 200, 20, 140, 50, "bottle", "Grocery", 5),
                ("MILK500", "Milk 500ml", 32, 4, 22, 80, "pack", "Dairy", 5),
                ("BREAD", "Bread", 45, 5, 28, 40, "pcs", "Bakery", 5),
                ("SOAP", "Bath Soap", 45, 10, 20, 120, "pcs", "Personal Care", 18),
            ]
            for sku, name, mrp, disc, cost, stock, unit, cat, gst in samples:
                rate = calc_rate(mrp, disc)
                await db.execute(
                    """INSERT INTO product
                       (sku,name,mrp,discount,price,cost,stock,unit,category,gst_pct,active)
                       VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
                    (sku, name, mrp, disc, rate, cost, stock, unit, cat, gst),
                )
        # Seed a sample cashier tied to Counter 1 (if missing)
        cash = await db.fetchone("SELECT id FROM staff WHERE username=?", ("cashier",))
        if not cash:
            c1 = await db.fetchone("SELECT id FROM counter WHERE code=?", ("C1",))
            await db.execute(
                """INSERT INTO staff (name,username,password,role,counter_id,active)
                   VALUES (?,?,?,?,?,1)""",
                ("Cashier One", "cashier", hash_pw("cashier123"), "cashier",
                 c1["id"] if c1 else None),
            )

        # Settings
        for k, v in DEFAULT_THEME.items():
            await db.execute(
                "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
                (k, str(v)),
            )
        await db.execute(
            "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
            ("default_lang", "en"),
        )
        await db.execute(
            "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING",
            ("default_gst_pct", "18"),
        )
        await db.commit()
    await reload_settings()


def default_gst_pct() -> float:
    """Shop-wide / app default GST % (used when product has no override)."""
    try:
        return money(_get("default_gst_pct", "18"))
    except Exception:
        return 18.0


def product_effective_gst(row) -> float:
    """Individual gst_pct when gst_override=1; otherwise default GST %."""
    if row is None:
        return default_gst_pct()
    if int(row.get("gst_override") or 0) == 1:
        if row.get("gst_pct") is not None:
            return money(row.get("gst_pct"))
        return default_gst_pct()
    return default_gst_pct()


def calc_rate(mrp, discount) -> float:
    return money(max(0.0, money(mrp) - money(discount)))


def parse_card_last4(raw) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return digits[-4:] if len(digits) >= 4 else digits


def split_gst(gst_amt: float) -> tuple[float, float]:
    """Intra-state split: CGST + SGST (equal halves)."""
    half = money(money(gst_amt) / 2.0)
    other = money(money(gst_amt) - half)
    return half, other


def build_bill_lines(items: list) -> tuple[list, dict]:
    """Build bill line rows + totals from cart/edit payload."""
    bill_subtotal = bill_discount = bill_tax = bill_cgst = bill_sgst = bill_saving = 0.0
    lines = []
    for it in items:
        qty = money(it.get("qty") or 0)
        mrp = money(it.get("mrp") or 0)
        disc_unit = money(it.get("discount") or 0)
        rate = money(it.get("unit_price") or it.get("rate") or 0)
        if rate <= 0 and mrp:
            rate = calc_rate(mrp, disc_unit)
        gst_pct = money(it.get("gst_pct") or 0)
        cost = money(it.get("cost") or 0)
        if qty <= 0:
            continue
        if mrp <= 0:
            mrp = rate
        if disc_unit <= 0 and mrp > rate:
            disc_unit = money(mrp - rate)
        line_disc = money(disc_unit * qty)
        base = money(rate * qty)
        gst_amt = money(base * gst_pct / 100.0)
        cgst_amt, sgst_amt = split_gst(gst_amt)
        line_total = money(base + gst_amt)
        bill_subtotal += base
        bill_discount += line_disc
        bill_tax += gst_amt
        bill_cgst += cgst_amt
        bill_sgst += sgst_amt
        bill_saving += line_disc
        lines.append({
            "product_id": it.get("product_id"),
            "sku": it.get("sku"),
            "name": it.get("name"),
            "qty": qty,
            "mrp": mrp,
            "unit_price": rate,
            "discount": line_disc,
            "disc_unit": disc_unit,
            "gst_pct": gst_pct,
            "gst_amt": gst_amt,
            "cgst_amt": cgst_amt,
            "sgst_amt": sgst_amt,
            "cost": cost,
            "customer_saving": line_disc,
            "line_total": line_total,
        })
    totals = {
        "subtotal": money(bill_subtotal),
        "discount": money(bill_discount),
        "tax": money(bill_tax),
        "cgst": money(bill_cgst),
        "sgst": money(bill_sgst),
        "customer_saving": money(bill_saving),
        "total": money(bill_subtotal + bill_tax),
    }
    return lines, totals


async def next_bill_no(db, shop_id=None) -> str:
    today = date.today().isoformat()
    if shop_id:
        seq = await db.fetchone(
            "SELECT COUNT(*)+1 AS n FROM bill WHERE bill_date=? AND shop_id=?",
            (today, shop_id),
        )
    else:
        seq = await db.fetchone(
            "SELECT COUNT(*)+1 AS n FROM bill WHERE bill_date=?", (today,)
        )
    return f"BP-{today.replace('-', '')}-{int(seq['n']):04d}"


def session_user_from_row(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "username": row["username"],
        "role": row["role"],
        "counter_id": row.get("counter_id"),
        "shop_id": row.get("shop_id"),
        "permissions": row.get("permissions") or "",
        "pages": row.get("pages") or "",
        "theme_preset": (row.get("theme_preset") or "").strip(),
    }


async def load_shop_features_for_user(db, row) -> str:
    """Return features JSON string for session."""
    if row.get("role") == "superadmin":
        return features_to_storage(ALL_FEATURE_KEYS)
    sid = row.get("shop_id")
    if sid:
        shop = await db.fetchone("SELECT features FROM shop WHERE id=?", (sid,))
        if shop:
            return shop.get("features") or features_to_storage(ALL_FEATURE_KEYS)
    # Fallback: first shop or all features
    shop = await db.fetchone("SELECT features FROM shop ORDER BY id LIMIT 1")
    if shop:
        return shop.get("features") or features_to_storage(ALL_FEATURE_KEYS)
    return features_to_storage(ALL_FEATURE_KEYS)


def require_page(request: Request, page_key: str):
    """Return (user, redirect) — redirect if not logged in or page denied."""
    u = cur_user(request)
    if not u:
        return None, RedirectResponse("/login", 302)
    feats = parse_features(request.session.get("shop_features"))
    if is_superadmin(u):
        feats = set(ALL_FEATURE_KEYS)
    if not check_page(u, page_key, feats):
        dest = "/billing" if u.get("role") == "cashier" else "/dashboard"
        # Avoid redirect loop if dashboard itself is denied
        if page_key == "dashboard":
            dest = "/billing"
        return None, RedirectResponse(dest, 302)
    return u, None


@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield


app = FastAPI(title="BillingPro", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
os.makedirs(os.path.join(_base, "static"), exist_ok=True)
os.makedirs(os.path.join(_base, "uploads", "branding"), exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(_base, "static")), name="static")
app.mount("/uploads", StaticFiles(directory=os.path.join(_base, "uploads")), name="uploads")
templates = Jinja2Templates(directory=os.path.join(_base, "templates"))
# Safe fallbacks if a route forgets tctx helpers
templates.env.globals.setdefault("can_page", lambda *_a, **_k: False)
templates.env.globals.setdefault("is_admin", False)
templates.env.globals.setdefault("is_superadmin", False)
templates.env.globals.setdefault("is_store_admin", False)
templates.env.globals.setdefault("show_assistant", False)
templates.env.globals.setdefault("suggestion_chips", [])
templates.env.globals.setdefault("APP_LOGO_URL", "")
templates.env.globals.setdefault("APP_BG_URL", "")


def _tojson(v):
    return Markup(json.dumps(v))


templates.env.filters["tojson"] = _tojson
templates.env.filters["money"] = lambda v: f"{money(v):,.2f}"


def require_login(request: Request):
    u = cur_user(request)
    if not u:
        return None
    return u


# ═══════════════════════════════════════════════════════════════════════════
# AUTH + LANGUAGE
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if cur_user(request):
        return RedirectResponse("/dashboard", 302)
    return RedirectResponse("/login", 302)


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if cur_user(request):
        return RedirectResponse("/dashboard", 302)
    return templates.TemplateResponse("login.html", tctx(request, error=None))


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    async with await get_conn() as db:
        row = await db.fetchone(
            "SELECT * FROM staff WHERE username=? AND active=1",
            (username.strip(),),
        )
    if not row or row["password"] != hash_pw(password):
        return templates.TemplateResponse(
            "login.html",
            tctx(request, error=t("invalid_login", get_lang(request))),
            status_code=401,
        )
    async with await get_conn() as db:
        # refresh full row in case columns were added
        row = await db.fetchone("SELECT * FROM staff WHERE id=?", (row["id"],))
        request.session["shop_features"] = await load_shop_features_for_user(db, row)
    request.session["user"] = session_user_from_row(row)
    request.session["theme_preset"] = (row.get("theme_preset") or "").strip()
    if row["role"] == "cashier":
        return RedirectResponse("/billing", 302)
    if row["role"] == "superadmin":
        return RedirectResponse("/shops", 302)
    return RedirectResponse("/dashboard", 302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 302)


@app.post("/lang/{code}")
async def set_lang(request: Request, code: str):
    if code in SUPPORTED_LANGS:
        request.session["lang"] = code
    ref = request.headers.get("referer") or "/dashboard"
    return RedirectResponse(ref, 303)


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    u, redir = require_page(request, "dashboard")
    if redir:
        return redir
    today = date.today().isoformat()
    sh, sp = sql_shop(u)
    sb, sbp = sql_shop_prefixed(u, "b")
    async with await get_conn() as db:
        sales = await db.fetchone(
            f"SELECT COALESCE(SUM(total),0) AS s, COUNT(*) AS c FROM bill WHERE bill_date=?{sh}",
            (today, *sp),
        )
        prods = await db.fetchone(
            f"SELECT COUNT(*) AS c FROM product WHERE active=1{sh}", sp
        )
        recent = await db.fetchall(
            f"""SELECT b.*, s.name AS staff_name, c.name AS counter_name
               FROM bill b
               LEFT JOIN staff s ON s.id=b.staff_id
               LEFT JOIN counter c ON c.id=b.counter_id
               WHERE 1=1{sb}
               ORDER BY b.id DESC LIMIT 8""",
            sbp,
        )
    return templates.TemplateResponse(
        "dashboard.html",
        tctx(request, user=u, sales=sales, prods=prods, recent=recent, active="dashboard"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/products", response_class=HTMLResponse)
async def products_list(request: Request, q: str = ""):
    u, redir = require_page(request, "products")
    if redir:
        return redir
    sh, sp = sql_shop(u)
    async with await get_conn() as db:
        if q.strip():
            like = f"%{q.strip()}%"
            rows = await db.fetchall(
                f"""SELECT * FROM product WHERE active=1 AND (name ILIKE ? OR sku ILIKE ?){sh}
                   ORDER BY name LIMIT 200""",
                (like, like, *sp),
            )
        else:
            rows = await db.fetchall(
                f"SELECT * FROM product WHERE active=1{sh} ORDER BY name LIMIT 200", sp
            )
    return templates.TemplateResponse(
        "products.html",
        tctx(
            request, user=u, products=rows, q=q, active="products",
            saved=request.query_params.get("saved"),
            default_gst=default_gst_pct(),
        ),
    )


@app.get("/products/barcodes", response_class=HTMLResponse)
async def products_barcodes(request: Request, ids: str = "", q: str = ""):
    """Printable sticker labels: name + price + Code128 barcode (SKU)."""
    u, redir = require_page(request, "products")
    if redir:
        return redir
    sh, sp = sql_shop(u)
    id_list = []
    for part in (ids or "").split(","):
        part = part.strip()
        if part.isdigit():
            id_list.append(int(part))
    async with await get_conn() as db:
        if id_list:
            placeholders = ",".join("?" for _ in id_list)
            rows = await db.fetchall(
                f"""SELECT id, sku, name, price, mrp FROM product
                    WHERE active=1 AND id IN ({placeholders}){sh}
                    ORDER BY name""",
                (*id_list, *sp),
            )
        elif q.strip():
            like = f"%{q.strip()}%"
            rows = await db.fetchall(
                f"""SELECT id, sku, name, price, mrp FROM product
                    WHERE active=1 AND (name ILIKE ? OR sku ILIKE ?){sh}
                    ORDER BY name LIMIT 200""",
                (like, like, *sp),
            )
        else:
            rows = await db.fetchall(
                f"""SELECT id, sku, name, price, mrp FROM product
                    WHERE active=1{sh} ORDER BY name LIMIT 200""",
                sp,
            )
    return templates.TemplateResponse(
        "barcode_labels.html",
        tctx(request, user=u, products=rows, active="products"),
    )


@app.get("/api/products/next-sku")
async def api_next_sku(request: Request):
    """Suggest a unique scannable SKU/barcode for the shop."""
    u = cur_user(request)
    if not u:
        return JSONResponse({"ok": False}, 401)
    try:
        sid = int(u.get("shop_id") or require_shop_id(u) or 1)
    except (TypeError, ValueError):
        sid = 1
    prefix = f"P{sid:02d}"
    async with await get_conn() as db:
        row = await db.fetchone(
            """SELECT COUNT(*) AS c FROM product
               WHERE COALESCE(shop_id,0)=? AND sku LIKE ?""",
            (sid, prefix + "%"),
        )
        n = int(row["c"] or 0) + 1
        for _ in range(50):
            candidate = f"{prefix}{n:05d}"
            exists = await db.fetchone(
                "SELECT id FROM product WHERE COALESCE(shop_id,0)=? AND UPPER(sku)=UPPER(?)",
                (sid, candidate),
            )
            if not exists:
                return JSONResponse({"ok": True, "sku": candidate})
            n += 1
    return JSONResponse({"ok": True, "sku": f"{prefix}{int(datetime.now().timestamp()) % 100000:05d}"})


@app.get("/products/new", response_class=HTMLResponse)
async def product_new_get(request: Request):
    u, redir = require_page(request, "products")
    if redir:
        return redir
    return templates.TemplateResponse(
        "product_form.html",
        tctx(
            request, user=u, product=None, error=None, active="products",
            default_gst=default_gst_pct(),
        ),
    )


@app.post("/products/new", response_class=HTMLResponse)
async def product_new_post(
    request: Request,
    sku: str = Form(...), name: str = Form(...),
    mrp: str = Form("0"), discount: str = Form("0"),
    cost: str = Form("0"), stock: str = Form("0"), unit: str = Form("pcs"),
    category: str = Form(""), gst_pct: str = Form(""),
    gst_mode: str = Form("default"),
    hsn: str = Form(""), reorder_level: str = Form("5"),
):
    u, redir = require_page(request, "products")
    if redir:
        return redir
    mrp_v = money(mrp)
    disc_v = money(discount)
    rate = calc_rate(mrp_v, disc_v)
    use_override = (gst_mode or "").strip().lower() == "custom"
    def_gst = default_gst_pct()
    gst_v = money(gst_pct) if use_override and str(gst_pct).strip() != "" else def_gst
    override = 1 if use_override else 0
    try:
        async with await get_conn() as db:
            await db.execute(
                """INSERT INTO product
                   (sku,name,mrp,discount,price,cost,stock,unit,category,gst_pct,gst_override,hsn,reorder_level,shop_id,active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (sku.strip().upper(), name.strip(), mrp_v, disc_v, rate, money(cost),
                 money(stock), unit.strip() or "pcs", category.strip(), gst_v, override,
                 hsn.strip(), money(reorder_level), require_shop_id(u)),
            )
            await db.commit()
    except Exception as e:
        return templates.TemplateResponse(
            "product_form.html",
            tctx(
                request, user=u, product=None, error=str(e), active="products",
                default_gst=def_gst,
            ),
            status_code=400,
        )
    return RedirectResponse("/products?saved=1", 302)


@app.get("/products/{pid}/edit", response_class=HTMLResponse)
async def product_edit_get(request: Request, pid: int):
    u, redir = require_page(request, "products")
    if redir:
        return redir
    sh, sp = sql_shop(u)
    async with await get_conn() as db:
        product = await db.fetchone(
            f"SELECT * FROM product WHERE id=?{sh}", (pid, *sp)
        )
    if not product:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "product_form.html",
        tctx(
            request, user=u, product=product, error=None, active="products",
            default_gst=default_gst_pct(),
        ),
    )


@app.post("/products/{pid}/edit", response_class=HTMLResponse)
async def product_edit_post(
    request: Request, pid: int,
    sku: str = Form(...), name: str = Form(...),
    mrp: str = Form("0"), discount: str = Form("0"),
    cost: str = Form("0"), stock: str = Form("0"), unit: str = Form("pcs"),
    category: str = Form(""), gst_pct: str = Form(""), active: str = Form("1"),
    gst_mode: str = Form("default"),
    hsn: str = Form(""), reorder_level: str = Form("5"),
):
    u, redir = require_page(request, "products")
    if redir:
        return redir
    mrp_v = money(mrp)
    disc_v = money(discount)
    rate = calc_rate(mrp_v, disc_v)
    use_override = (gst_mode or "").strip().lower() == "custom"
    def_gst = default_gst_pct()
    gst_v = money(gst_pct) if use_override and str(gst_pct).strip() != "" else def_gst
    override = 1 if use_override else 0
    sh, sp = sql_shop(u)
    async with await get_conn() as db:
        if not await assert_same_shop(db, u, "product", pid):
            raise HTTPException(404)
        await db.execute(
            f"""UPDATE product SET sku=?,name=?,mrp=?,discount=?,price=?,cost=?,stock=?,unit=?,
               category=?,gst_pct=?,gst_override=?,hsn=?,reorder_level=?,active=? WHERE id=?{sh}""",
            (sku.strip().upper(), name.strip(), mrp_v, disc_v, rate, money(cost), money(stock),
             unit.strip() or "pcs", category.strip(), gst_v, override, hsn.strip(),
             money(reorder_level), int(active), pid, *sp),
        )
        await db.commit()
    return RedirectResponse("/products?saved=1", 302)


@app.post("/products/{pid}/delete")
async def product_delete(request: Request, pid: int):
    u, redir = require_page(request, "products")
    if redir:
        return redir
    async with await get_conn() as db:
        if not await assert_same_shop(db, u, "product", pid):
            raise HTTPException(404)
        await db.execute(
            "UPDATE product SET active=0 WHERE id=?" + sql_shop(u)[0],
            (pid, *sql_shop(u)[1]),
        )
        await db.commit()
    return RedirectResponse("/products?saved=deleted", 302)


@app.post("/products/upload", response_class=HTMLResponse)
async def products_upload(request: Request, file: UploadFile = File(...)):
    u, redir = require_page(request, "products")
    if redir:
        return redir
    raw = await file.read()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    n = 0
    sid = require_shop_id(u)
    sh, sp = sql_shop(u)
    async with await get_conn() as db:
        for row in reader:
            sku = (row.get("sku") or row.get("SKU") or "").strip().upper()
            name = (row.get("name") or row.get("Name") or "").strip()
            if not sku or not name:
                continue
            price = money(row.get("price") or row.get("Price") or row.get("rate") or row.get("Rate") or 0)
            stock = money(row.get("stock") or row.get("Stock") or 0)
            unit = (row.get("unit") or row.get("Unit") or "pcs").strip()
            cat = (row.get("category") or row.get("Category") or "").strip()
            existing = await db.fetchone(
                f"SELECT id FROM product WHERE sku=?{sh}", (sku, *sp)
            )
            cost = money(row.get("cost") or row.get("Cost") or 0)
            gst_raw = row.get("gst") or row.get("gst_pct") or row.get("GST")
            if gst_raw is not None and str(gst_raw).strip() != "":
                gst = money(gst_raw)
                gst_override = 1
            else:
                gst = default_gst_pct()
                gst_override = 0
            mrp = money(row.get("mrp") or row.get("MRP") or price)
            disc = money(row.get("discount") or row.get("Discount") or 0)
            if disc <= 0 and mrp > price > 0:
                disc = money(mrp - price)
            rate = calc_rate(mrp, disc) if mrp else price
            if existing:
                await db.execute(
                    f"""UPDATE product SET name=?,mrp=?,discount=?,price=?,cost=?,stock=?,unit=?,category=?,
                       gst_pct=?,gst_override=?,active=1
                       WHERE sku=?{sh}""",
                    (name, mrp, disc, rate, cost, stock, unit, cat, gst, gst_override, sku, *sp),
                )
            else:
                await db.execute(
                    """INSERT INTO product (sku,name,mrp,discount,price,cost,stock,unit,category,gst_pct,gst_override,shop_id,active)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (sku, name, mrp, disc, rate, cost, stock, unit, cat, gst, gst_override, sid),
                )
            n += 1
        await db.commit()
    return RedirectResponse(f"/products?saved=uploaded-{n}", 302)


@app.get("/api/products/search")
async def api_product_search(request: Request, q: str = ""):
    u = cur_user(request)
    if not u:
        return JSONResponse({"error": "auth"}, 401)
    q = q.strip()
    sh, sp = sql_shop(u)
    async with await get_conn() as db:
        if not q:
            rows = await db.fetchall(
                f"""SELECT id,sku,name,mrp,discount,price,cost,stock,unit,gst_pct,gst_override FROM product
                   WHERE active=1{sh} ORDER BY name LIMIT 50""",
                sp,
            )
        else:
            like = f"%{q}%"
            rows = await db.fetchall(
                f"""SELECT id,sku,name,mrp,discount,price,cost,stock,unit,gst_pct,gst_override FROM product
                   WHERE active=1 AND (name ILIKE ? OR sku ILIKE ? OR COALESCE(category,'') ILIKE ?){sh}
                   ORDER BY
                     CASE WHEN sku ILIKE ? THEN 0 WHEN name ILIKE ? THEN 1 ELSE 2 END,
                     name
                   LIMIT 50""",
                (like, like, like, *sp, q + "%", q + "%"),
            )
    out = []
    lang = get_lang(request)
    for r in rows:
        mrp = money(r.get("mrp") or r["price"] or 0)
        disc = money(r.get("discount") or 0)
        rate = money(r["price"] or calc_rate(mrp, disc))
        out.append({
            "id": int(r["id"]),
            "sku": r["sku"] or "",
            "name": d(r["name"] or "", lang),
            "name_raw": r["name"] or "",
            "mrp": mrp,
            "discount": disc,
            "rate": rate,
            "price": rate,
            "cost": money(r.get("cost")),
            "stock": money(r["stock"]),
            "unit": d(r["unit"] or "pcs", lang),
            "gst_pct": product_effective_gst(r),
            "gst_override": int(r.get("gst_override") or 0),
            "customer_saving": money(max(0.0, mrp - rate)),
        })
    return JSONResponse(out)


@app.get("/api/customers/lookup")
async def api_customer_lookup(request: Request, mobile: str = ""):
    u = cur_user(request)
    if not u:
        return JSONResponse({"error": "auth"}, 401)
    mobile = "".join(ch for ch in mobile if ch.isdigit())
    if len(mobile) < 10:
        return JSONResponse({"found": False})
    sh, sp = sql_shop(u)
    async with await get_conn() as db:
        row = await db.fetchone(
            f"""SELECT id, name, mobile, COALESCE(loyalty_points,0) AS loyalty_points
                FROM customer WHERE mobile=?{sh}""",
            (mobile, *sp),
        )
    if not row:
        return JSONResponse({"found": False, "mobile": mobile})
    return JSONResponse({
        "found": True,
        "id": int(row["id"]),
        "name": row["name"] or "",
        "mobile": row["mobile"],
        "loyalty_points": float(row["loyalty_points"] or 0),
    })


# ═══════════════════════════════════════════════════════════════════════════
# BILLING (POS)
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request):
    u, redir = require_page(request, "billing")
    if redir:
        return redir
    async with await get_conn() as db:
        sh, sp = sql_shop(u)
        counters = await db.fetchall(
            f"SELECT * FROM counter WHERE active=1{sh} ORDER BY name", sp
        )
        staff_row = await db.fetchone("SELECT * FROM staff WHERE id=?", (u["id"],))
        if staff_row:
            u = session_user_from_row(staff_row)
            request.session["user"] = u
        counter_name = None
        if u.get("counter_id"):
            c = await db.fetchone(
                f"SELECT * FROM counter WHERE id=?{sh}", (u["counter_id"], *sp)
            )
            if c:
                counter_name = f"{d(c['name'], get_lang(request))} ({c['code']})"
        bill_no = await next_bill_no(db, require_shop_id(u))
    return templates.TemplateResponse(
        "billing.html",
        tctx(
            request, user=u, counters=counters, active="billing",
            is_admin=is_admin(u), counter_name=counter_name, bill_no=bill_no,
        ),
    )


@app.post("/api/bills")
async def create_bill(request: Request):
    u = require_login(request)
    if not u:
        return JSONResponse({"ok": False, "error": tr(request, "err_not_logged_in")}, 401)
    body = await request.json()
    items = body.get("items") or []
    if not items:
        return JSONResponse({"ok": False, "error": tr(request, "err_cart_empty")}, 400)

    bill_no = str(body.get("bill_no") or "").strip().upper()
    if not bill_no:
        return JSONResponse({"ok": False, "error": tr(request, "err_bill_no_required")}, 400)

    staff_id = int(u["id"])
    if is_admin(u):
        counter_id = int(body.get("counter_id") or u.get("counter_id") or 0)
    else:
        counter_id = int(u.get("counter_id") or body.get("counter_id") or 0)
    if not counter_id:
        return JSONResponse({"ok": False, "error": tr(request, "err_counter_required")}, 400)

    customer_name = str(body.get("customer_name") or "").strip()
    customer_mobile = "".join(ch for ch in str(body.get("customer_mobile") or "") if ch.isdigit())
    if len(customer_mobile) != 10:
        return JSONResponse({"ok": False, "error": tr(request, "err_mobile_required")}, 400)
    payment_mode = str(body.get("payment_mode") or "cash").lower().strip()
    if payment_mode not in ("cash", "upi", "card", "split", "credit"):
        payment_mode = "cash"
    card_last4 = parse_card_last4(body.get("card_last4"))
    if payment_mode == "card" and len(card_last4) != 4:
        return JSONResponse({"ok": False, "error": tr(request, "err_card_last4")}, 400)
    if payment_mode not in ("card", "split"):
        card_last4 = ""
    is_credit = 1 if payment_mode == "credit" or body.get("is_credit") else 0
    if is_credit:
        payment_mode = "credit"
    notes = str(body.get("notes") or "")
    bill_discount_pct = money(body.get("bill_discount_pct"))
    bill_discount_amt = money(body.get("bill_discount_amt"))
    coupon_code = str(body.get("coupon_code") or "").strip().upper()
    loyalty_redeem = money(body.get("loyalty_redeemed"))
    split_pays = body.get("payments") or []

    lines, totals = build_bill_lines(items)
    if not lines:
        return JSONResponse({"ok": False, "error": tr(request, "err_no_valid_lines")}, 400)

    # Apply bill-level discount + coupon + loyalty redeem on taxable total
    base_total = totals["total"]
    extra_disc = bill_discount_amt
    if bill_discount_pct > 0:
        extra_disc = money(max(extra_disc, base_total * bill_discount_pct / 100))
    if coupon_code:
        async with await get_conn() as db:
            cpn = await db.fetchone(
                "SELECT * FROM coupon WHERE code=? AND active=1" + sql_shop(u)[0],
                (coupon_code, *sql_shop(u)[1]),
            )
        if cpn and money(totals["subtotal"]) >= money(cpn["min_bill"]):
            if money(cpn["discount_pct"]) > 0:
                extra_disc = money(extra_disc + totals["subtotal"] * money(cpn["discount_pct"]) / 100)
            else:
                extra_disc = money(extra_disc + money(cpn["discount_amt"]))
        else:
            coupon_code = ""
    loyalty_redeem = min(loyalty_redeem, max(0.0, base_total - extra_disc))
    final_total = money(max(0.0, base_total - extra_disc - loyalty_redeem))
    totals["discount"] = money(totals["discount"] + extra_disc)
    totals["total"] = final_total
    today = date.today().isoformat()

    # Validate split payments sum
    if payment_mode == "split":
        if not split_pays:
            return JSONResponse({"ok": False, "error": tr(request, "err_split_pay")}, 400)
        pay_sum = money(sum(money(p.get("amount")) for p in split_pays))
        if abs(pay_sum - final_total) > 0.05:
            return JSONResponse({"ok": False, "error": tr(request, "err_split_mismatch")}, 400)
        for p in split_pays:
            if str(p.get("mode")) == "card" and len(parse_card_last4(p.get("card_last4"))) != 4:
                return JSONResponse({"ok": False, "error": tr(request, "err_card_last4")}, 400)

    async with await get_conn() as db:
        sid = require_shop_id(u)
        sh, sp = sql_shop(u)
        exists = await db.fetchone(
            f"SELECT id FROM bill WHERE bill_no=?{sh}", (bill_no, *sp)
        )
        if exists:
            return JSONResponse({"ok": False, "error": tr(request, "err_bill_exists")}, 400)

        # Stock check (shop-scoped products only)
        for ln in lines:
            if not ln["product_id"]:
                continue
            prod = await db.fetchone(
                f"SELECT id,name,stock FROM product WHERE id=? AND active=1{sh}",
                (int(ln["product_id"]), *sp),
            )
            if not prod:
                return JSONResponse({
                    "ok": False,
                    "error": tr(request, "err_product_not_found", name=ln["name"]),
                }, 400)
            if money(prod["stock"]) < ln["qty"]:
                return JSONResponse({
                    "ok": False,
                    "error": tr(
                        request, "err_insufficient_stock",
                        name=prod["name"], available=money(prod["stock"]), needed=ln["qty"],
                    ),
                }, 400)

        customer_id = None
        if customer_mobile:
            existing = await db.fetchone(
                f"SELECT id FROM customer WHERE mobile=?{sh}", (customer_mobile, *sp)
            )
            if existing:
                customer_id = existing["id"]
                if customer_name:
                    await db.execute(
                        "UPDATE customer SET name=? WHERE id=?",
                        (customer_name, customer_id),
                    )
            else:
                await db.execute(
                    "INSERT INTO customer (name,mobile,shop_id) VALUES (?,?,?)",
                    (customer_name or customer_mobile, customer_mobile, sid),
                )
                customer_id = await db.lastrowid()
                if not customer_name:
                    customer_name = customer_mobile

        if is_credit and not customer_id:
            return JSONResponse({"ok": False, "error": tr(request, "err_credit_customer")}, 400)

        # Loyalty redeem check
        if loyalty_redeem > 0 and customer_id:
            cust = await db.fetchone("SELECT loyalty_points FROM customer WHERE id=?", (customer_id,))
            if money(cust.get("loyalty_points")) < loyalty_redeem:
                return JSONResponse({"ok": False, "error": tr(request, "err_loyalty_points")}, 400)

        earn_rate = money(_get("loyalty_earn_rate", "1"))  # points per ₹100
        loyalty_earned = money((final_total / 100.0) * earn_rate) if customer_id and not is_credit else 0

        await db.execute(
            """INSERT INTO bill (bill_no,bill_date,counter_id,staff_id,customer_name,
               customer_id,customer_mobile,subtotal,discount,tax,cgst,sgst,total,customer_saving,
               payment_mode,card_last4,notes,status,bill_discount_pct,bill_discount_amt,
               coupon_code,is_credit,loyalty_earned,loyalty_redeemed,shop_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (bill_no, today, counter_id, staff_id, customer_name, customer_id,
             customer_mobile, totals["subtotal"], totals["discount"], totals["tax"],
             totals["cgst"], totals["sgst"], totals["total"], totals["customer_saving"],
             payment_mode, card_last4, notes, "completed", bill_discount_pct, extra_disc,
             coupon_code, is_credit, loyalty_earned, loyalty_redeem, sid),
        )
        bill_id = await db.lastrowid()
        for ln in lines:
            await db.execute(
                """INSERT INTO bill_item
                   (bill_id,product_id,sku,name,qty,unit_price,discount,gst_pct,gst_amt,cgst_amt,sgst_amt,cost,mrp,customer_saving,line_total)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (bill_id, ln["product_id"], ln["sku"], ln["name"], ln["qty"],
                 ln["unit_price"], ln["discount"], ln["gst_pct"], ln["gst_amt"],
                 ln["cgst_amt"], ln["sgst_amt"], ln["cost"], ln["mrp"],
                 ln["customer_saving"], ln["line_total"]),
            )
            if ln["product_id"]:
                await db.execute(
                    "UPDATE product SET stock = GREATEST(stock - ?, 0) WHERE id=?" + sh,
                    (ln["qty"], int(ln["product_id"]), *sp),
                )

        # Payments
        if payment_mode == "split":
            for p in split_pays:
                await db.execute(
                    "INSERT INTO bill_payment (bill_id,mode,amount,card_last4,ref) VALUES (?,?,?,?,?)",
                    (bill_id, str(p.get("mode") or "cash"), money(p.get("amount")),
                     parse_card_last4(p.get("card_last4")) if str(p.get("mode")) == "card" else "",
                     str(p.get("ref") or "")),
                )
        else:
            await db.execute(
                "INSERT INTO bill_payment (bill_id,mode,amount,card_last4,ref) VALUES (?,?,?,?,?)",
                (bill_id, payment_mode if not is_credit else "credit", final_total, card_last4, ""),
            )

        if is_credit and customer_id:
            await db.execute(
                "INSERT INTO credit_ledger (customer_id,bill_id,amount,paid,note) VALUES (?,?,?,?,?)",
                (customer_id, bill_id, final_total, 0, bill_no),
            )

        if customer_id and (loyalty_earned or loyalty_redeem):
            if loyalty_redeem:
                await db.execute(
                    "UPDATE customer SET loyalty_points = GREATEST(COALESCE(loyalty_points,0) - ?, 0) WHERE id=?",
                    (loyalty_redeem, customer_id),
                )
                await db.execute(
                    "INSERT INTO loyalty_ledger (customer_id,bill_id,points,note) VALUES (?,?,?,?)",
                    (customer_id, bill_id, -loyalty_redeem, "redeem"),
                )
            if loyalty_earned:
                await db.execute(
                    "UPDATE customer SET loyalty_points = COALESCE(loyalty_points,0) + ? WHERE id=?",
                    (loyalty_earned, customer_id),
                )
                await db.execute(
                    "INSERT INTO loyalty_ledger (customer_id,bill_id,points,note) VALUES (?,?,?,?)",
                    (customer_id, bill_id, loyalty_earned, "earn"),
                )

        try:
            from advanced import audit as _audit
            await _audit(db, staff_id, "bill_create", "bill", bill_id, bill_no)
        except Exception:
            pass
        await db.commit()
    return JSONResponse({
        "ok": True, "bill_id": bill_id, "bill_no": bill_no, "total": totals["total"],
        "cgst": totals["cgst"], "sgst": totals["sgst"], "tax": totals["tax"],
    })


@app.get("/bills", response_class=HTMLResponse)
async def bills_list(request: Request):
    u, redir = require_page(request, "bills")
    if redir:
        return redir
    async with await get_conn() as db:
        sb, sbp = sql_shop_prefixed(u, "b")
        if is_admin(u):
            rows = await db.fetchall(
                f"""SELECT b.*, s.name AS staff_name, c.name AS counter_name
                   FROM bill b
                   LEFT JOIN staff s ON s.id=b.staff_id
                   LEFT JOIN counter c ON c.id=b.counter_id
                   WHERE 1=1{sb}
                   ORDER BY b.id DESC LIMIT 100""",
                sbp,
            )
        else:
            rows = await db.fetchall(
                f"""SELECT b.*, s.name AS staff_name, c.name AS counter_name
                   FROM bill b
                   LEFT JOIN staff s ON s.id=b.staff_id
                   LEFT JOIN counter c ON c.id=b.counter_id
                   WHERE b.staff_id=?{sb}
                   ORDER BY b.id DESC LIMIT 100""",
                (u["id"], *sbp),
            )
    return templates.TemplateResponse(
        "bills.html", tctx(request, user=u, bills=rows, active="bills")
    )


@app.get("/bills/{bid}", response_class=HTMLResponse)
async def bill_view(request: Request, bid: int):
    u, redir = require_page(request, "bills")
    if redir:
        return redir
    async with await get_conn() as db:
        sb, sbp = sql_shop_prefixed(u, "b")
        bill = await db.fetchone(
            f"""SELECT b.*, s.name AS staff_name, c.name AS counter_name, c.code AS counter_code
               FROM bill b
               LEFT JOIN staff s ON s.id=b.staff_id
               LEFT JOIN counter c ON c.id=b.counter_id
               WHERE b.id=?{sb}""",
            (bid, *sbp),
        )
        if not bill:
            raise HTTPException(404)
        if not is_admin(u) and bill.get("staff_id") != u["id"]:
            return RedirectResponse("/bills")
        items = await db.fetchall("SELECT * FROM bill_item WHERE bill_id=? ORDER BY id", (bid,))
    greeting = d(_get("bill_greeting", "Welcome! Thank you for shopping with us."), get_lang(request))
    thanks = d(_get("bill_thanks", "Thank you! Please visit again."), get_lang(request))
    return templates.TemplateResponse(
        "bill_view.html",
        tctx(
            request, user=u, bill=bill, items=items, active="bills",
            bill_greeting=greeting, bill_thanks=thanks,
        ),
    )


@app.get("/bills/{bid}/edit", response_class=HTMLResponse)
async def bill_edit_page(request: Request, bid: int):
    u, redir = require_page(request, "bills")
    if redir:
        return redir
    async with await get_conn() as db:
        sb, sbp = sql_shop_prefixed(u, "b")
        bill = await db.fetchone(
            f"""SELECT b.*, s.name AS staff_name, c.name AS counter_name
               FROM bill b
               LEFT JOIN staff s ON s.id=b.staff_id
               LEFT JOIN counter c ON c.id=b.counter_id
               WHERE b.id=?{sb}""",
            (bid, *sbp),
        )
        if not bill:
            raise HTTPException(404)
        if not is_admin(u) and bill.get("staff_id") != u["id"]:
            return RedirectResponse("/bills")
        items = await db.fetchall("SELECT * FROM bill_item WHERE bill_id=? ORDER BY id", (bid,))
    # Prepare cart JSON for editor (discount stored as line total saving → per-unit for UI)
    cart = []
    for it in items:
        qty = money(it["qty"]) or 1
        line_disc = money(it.get("discount") or 0)
        disc_unit = money(line_disc / qty) if qty else 0
        cart.append({
            "product_id": it.get("product_id"),
            "sku": it.get("sku") or "",
            "name": it.get("name") or "",
            "mrp": money(it.get("mrp") or it.get("unit_price")),
            "discount": disc_unit,
            "rate": money(it.get("unit_price")),
            "unit_price": money(it.get("unit_price")),
            "qty": qty,
            "gst_pct": money(it.get("gst_pct") or 0),
            "cost": money(it.get("cost") or 0),
        })
    return templates.TemplateResponse(
        "bill_edit.html",
        tctx(
            request, user=u, bill=bill, active="bills",
            cart_json=Markup(json.dumps(cart)),
        ),
    )


@app.post("/api/bills/{bid}")
async def update_bill(request: Request, bid: int):
    """Replace bill lines; restore old stock then deduct new (correct stock)."""
    u = require_login(request)
    if not u:
        return JSONResponse({"ok": False, "error": tr(request, "err_not_logged_in")}, 401)
    body = await request.json()
    items = body.get("items") or []
    lines, totals = build_bill_lines(items)
    if not lines:
        return JSONResponse({"ok": False, "error": tr(request, "err_cart_empty")}, 400)

    customer_name = str(body.get("customer_name") or "").strip()
    customer_mobile = "".join(ch for ch in str(body.get("customer_mobile") or "") if ch.isdigit())
    if len(customer_mobile) != 10:
        return JSONResponse({"ok": False, "error": tr(request, "err_mobile_required")}, 400)
    payment_mode = str(body.get("payment_mode") or "cash").lower().strip()
    if payment_mode not in ("cash", "upi", "card"):
        payment_mode = "cash"
    card_last4 = parse_card_last4(body.get("card_last4"))
    if payment_mode == "card" and len(card_last4) != 4:
        return JSONResponse({"ok": False, "error": tr(request, "err_card_last4")}, 400)
    if payment_mode != "card":
        card_last4 = ""

    class _Abort(Exception):
        def __init__(self, msg: str, status: int = 400):
            self.msg, self.status = msg, status

    try:
        async with await get_conn() as db:
            bill = await db.fetchone("SELECT * FROM bill WHERE id=?" + sql_shop(u)[0], (bid, *sql_shop(u)[1]))
            if not bill:
                raise _Abort(tr(request, "err_bill_not_found"), 404)
            if not is_admin(u) and bill.get("staff_id") != u["id"]:
                raise _Abort(tr(request, "err_not_allowed"), 403)

            old_items = await db.fetchall(
                "SELECT product_id, qty FROM bill_item WHERE bill_id=?", (bid,)
            )
            # Restore stock from old lines
            for oi in old_items:
                if oi.get("product_id"):
                    await db.execute(
                        "UPDATE product SET stock = stock + ? WHERE id=?",
                        (money(oi["qty"]), int(oi["product_id"])),
                    )

            # Validate new stock after restore
            for ln in lines:
                if not ln["product_id"]:
                    continue
                prod = await db.fetchone(
                    "SELECT id,name,stock FROM product WHERE id=? AND active=1",
                    (int(ln["product_id"]),),
                )
                if not prod:
                    raise _Abort(tr(request, "err_product_not_found", name=ln["name"]))
                if money(prod["stock"]) < ln["qty"]:
                    raise _Abort(tr(
                        request, "err_insufficient_stock",
                        name=prod["name"], available=money(prod["stock"]), needed=ln["qty"],
                    ))

            customer_id = bill.get("customer_id")
            shc, spc = sql_shop(u)
            sid = require_shop_id(u)
            existing = await db.fetchone(
                f"SELECT id FROM customer WHERE mobile=?{shc}", (customer_mobile, *spc)
            )
            if existing:
                customer_id = existing["id"]
                if customer_name:
                    await db.execute(
                        "UPDATE customer SET name=? WHERE id=?",
                        (customer_name, customer_id),
                    )
            else:
                await db.execute(
                    "INSERT INTO customer (name,mobile,shop_id) VALUES (?,?,?)",
                    (customer_name or customer_mobile, customer_mobile, sid),
                )
                customer_id = await db.lastrowid()

            await db.execute("DELETE FROM bill_item WHERE bill_id=?", (bid,))
            for ln in lines:
                await db.execute(
                    """INSERT INTO bill_item
                       (bill_id,product_id,sku,name,qty,unit_price,discount,gst_pct,gst_amt,cgst_amt,sgst_amt,cost,mrp,customer_saving,line_total)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (bid, ln["product_id"], ln["sku"], ln["name"], ln["qty"],
                     ln["unit_price"], ln["discount"], ln["gst_pct"], ln["gst_amt"],
                     ln["cgst_amt"], ln["sgst_amt"], ln["cost"], ln["mrp"],
                     ln["customer_saving"], ln["line_total"]),
                )
                if ln["product_id"]:
                    await db.execute(
                        "UPDATE product SET stock = GREATEST(stock - ?, 0) WHERE id=?",
                        (ln["qty"], int(ln["product_id"])),
                    )

            await db.execute(
                """UPDATE bill SET customer_name=?, customer_mobile=?, customer_id=?,
                   subtotal=?, discount=?, tax=?, cgst=?, sgst=?, total=?, customer_saving=?,
                   payment_mode=?, card_last4=? WHERE id=?""",
                (customer_name, customer_mobile, customer_id,
                 totals["subtotal"], totals["discount"], totals["tax"],
                 totals["cgst"], totals["sgst"], totals["total"], totals["customer_saving"],
                 payment_mode, card_last4, bid),
            )
            await db.commit()
            return JSONResponse({"ok": True, "bill_id": bid, "bill_no": bill["bill_no"], "total": totals["total"]})
    except _Abort as e:
        return JSONResponse({"ok": False, "error": e.msg}, e.status)


# ═══════════════════════════════════════════════════════════════════════════
# STOCK
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/stock", response_class=HTMLResponse)
async def stock_page(request: Request, q: str = ""):
    u, redir = require_page(request, "stock")
    if redir:
        return redir
    async with await get_conn() as db:
        sh, sp = sql_shop(u)
        if q.strip():
            like = f"%{q.strip()}%"
            rows = await db.fetchall(
                f"""SELECT id,sku,name,stock,unit,mrp,price,discount,gst_pct,category
                   FROM product WHERE active=1 AND (name ILIKE ? OR sku ILIKE ?){sh}
                   ORDER BY
                     CASE WHEN sku ILIKE ? THEN 0 WHEN name ILIKE ? THEN 1 ELSE 2 END,
                     name LIMIT 200""",
                (like, like, *sp, q.strip() + "%", q.strip() + "%"),
            )
        else:
            rows = await db.fetchall(
                f"""SELECT id,sku,name,stock,unit,mrp,price,discount,gst_pct,category
                   FROM product WHERE active=1{sh} ORDER BY name LIMIT 200""",
                sp,
            )
        low = await db.fetchone(
            f"SELECT COUNT(*) AS c FROM product WHERE active=1 AND stock <= 5{sh}", sp
        )
    return templates.TemplateResponse(
        "stock.html",
        tctx(
            request, user=u, products=rows, q=q, active="stock",
            low_count=low["c"] if low else 0,
            saved=request.query_params.get("saved"),
            error=request.query_params.get("error"),
        ),
    )


@app.post("/stock/{pid}/adjust")
async def stock_adjust(
    request: Request, pid: int,
    mode: str = Form("set"), qty: str = Form("0"),
):
    u, redir = require_page(request, "stock")
    if redir:
        return redir
    amount = money(qty)
    async with await get_conn() as db:
        sh, sp = sql_shop(u)
        prod = await db.fetchone(
            f"SELECT id,stock FROM product WHERE id=? AND active=1{sh}", (pid, *sp)
        )
        if not prod:
            return RedirectResponse("/stock?error=not_found", 303)
        if mode == "add":
            new_stock = money(prod["stock"]) + amount
        elif mode == "remove":
            new_stock = max(0.0, money(prod["stock"]) - amount)
        else:
            new_stock = max(0.0, amount)
        await db.execute(
            f"UPDATE product SET stock=? WHERE id=?{sh}", (new_stock, pid, *sp)
        )
        await db.commit()
    ref = request.headers.get("referer") or "/stock"
    if "saved=" not in ref:
        sep = "&" if "?" in ref else "?"
        return RedirectResponse(f"{ref.split('?')[0]}?saved=1", 303)
    return RedirectResponse("/stock?saved=1", 303)


# ═══════════════════════════════════════════════════════════════════════════
# COUNTERS + STAFF
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/counters", response_class=HTMLResponse)
async def counters_list(request: Request):
    u, redir = require_page(request, "counters")
    if redir:
        return redir
    async with await get_conn() as db:
        sh, sp = sql_shop(u)
        rows = await db.fetchall(f"SELECT * FROM counter WHERE 1=1{sh} ORDER BY name", sp)
    return templates.TemplateResponse(
        "counters.html",
        tctx(request, user=u, counters=rows, active="counters",
             saved=request.query_params.get("saved"),
             error=request.query_params.get("error")),
    )


@app.post("/counters")
async def counters_save(
    request: Request, name: str = Form(...), code: str = Form(...),
    location: str = Form(""), cid: str = Form(""),
):
    u, redir = require_page(request, "counters")
    if redir:
        return redir
    async with await get_conn() as db:
        sh, sp = sql_shop(u)
        if cid.strip():
            await db.execute(
                f"UPDATE counter SET name=?,code=?,location=? WHERE id=?{sh}",
                (name.strip(), code.strip().upper(), location.strip(), int(cid), *sp),
            )
        else:
            await db.execute(
                "INSERT INTO counter (name,code,location,shop_id,active) VALUES (?,?,?,?,1)",
                (name.strip(), code.strip().upper(), location.strip(), require_shop_id(u)),
            )
        await db.commit()
    return RedirectResponse("/counters?saved=1", 302)


@app.post("/counters/{cid}/delete")
async def counters_delete(request: Request, cid: int):
    u, redir = require_page(request, "counters")
    if redir:
        return redir
    async with await get_conn() as db:
        sh, sp = sql_shop(u)
        await db.execute(
            f"UPDATE counter SET active=0 WHERE id=?{sh}", (cid, *sp)
        )
        await db.commit()
    return RedirectResponse("/counters?saved=deleted", 302)


@app.get("/employees", response_class=HTMLResponse)
async def employees_list(request: Request):
    u, redir = require_page(request, "employees")
    if redir:
        return redir
    async with await get_conn() as db:
        if is_superadmin(u):
            rows = await db.fetchall(
                """SELECT s.id,s.name,s.username,s.role,s.active,s.counter_id,s.shop_id,
                          c.name AS counter_name, c.code AS counter_code
                   FROM staff s
                   LEFT JOIN counter c ON c.id=s.counter_id
                   WHERE s.role!='superadmin' OR s.id=?
                   ORDER BY s.name""",
                (u["id"],),
            )
        else:
            rows = await db.fetchall(
                """SELECT s.id,s.name,s.username,s.role,s.active,s.counter_id,s.shop_id,
                          c.name AS counter_name, c.code AS counter_code
                   FROM staff s
                   LEFT JOIN counter c ON c.id=s.counter_id
                   WHERE s.role!='superadmin' AND (s.shop_id=? OR ? IS NULL)
                   ORDER BY s.name""",
                (u.get("shop_id"), u.get("shop_id")),
            )
        counters = await db.fetchall(
            "SELECT id,name,code FROM counter WHERE active=1" + sql_shop(u)[0] + " ORDER BY name",
            sql_shop(u)[1],
        )
    return templates.TemplateResponse(
        "employees.html",
        tctx(
            request, user=u, employees=rows, counters=counters, active="employees",
            saved=request.query_params.get("saved"),
            error=request.query_params.get("error"),
        ),
    )


@app.post("/employees")
async def employees_save(
    request: Request, name: str = Form(...), username: str = Form(...),
    password: str = Form(""), role: str = Form("cashier"), eid: str = Form(""),
    counter_id: str = Form(""), theme_preset: str = Form(""),
):
    u, redir = require_page(request, "employees")
    if redir:
        return redir
    uname = username.strip().lower()
    c_id = int(counter_id) if counter_id.strip().isdigit() else None
    if role not in ("admin", "cashier"):
        role = "cashier"
    shop_id = require_shop_id(u)
    pages = DEFAULT_ADMIN_PAGES if role == "admin" else DEFAULT_CASHIER_PAGES
    theme = theme_preset.strip()
    if theme and theme not in THEME_PRESETS:
        theme = ""
    async with await get_conn() as db:
        # Counter must belong to this shop
        if c_id and not is_superadmin(u):
            okc = await db.fetchone(
                "SELECT id FROM counter WHERE id=? AND shop_id=?", (c_id, shop_id)
            )
            if not okc:
                c_id = None
        try:
            if eid.strip():
                # Can only edit staff in own shop
                if not is_superadmin(u):
                    own = await db.fetchone(
                        "SELECT id FROM staff WHERE id=? AND shop_id=?",
                        (int(eid), shop_id),
                    )
                    if not own:
                        return RedirectResponse("/employees", 303)
                if password.strip():
                    await db.execute(
                        """UPDATE staff SET name=?,username=?,password=?,role=?,counter_id=?,theme_preset=?
                           WHERE id=? AND role!='superadmin'""",
                        (name.strip(), uname, hash_pw(password), role, c_id, theme, int(eid)),
                    )
                else:
                    await db.execute(
                        """UPDATE staff SET name=?,username=?,role=?,counter_id=?,theme_preset=?
                           WHERE id=? AND role!='superadmin'""",
                        (name.strip(), uname, role, c_id, theme, int(eid)),
                    )
            else:
                dup = await db.fetchone("SELECT id FROM staff WHERE username=?", (uname,))
                if dup:
                    return RedirectResponse("/employees?error=username_exists", 303)
                await db.execute(
                    """INSERT INTO staff (name,username,password,role,counter_id,shop_id,pages,theme_preset,active)
                       VALUES (?,?,?,?,?,?,?,?,1)""",
                    (name.strip(), uname, hash_pw(password or "pass123"), role, c_id, shop_id, pages, theme),
                )
            await db.commit()
        except Exception:
            return RedirectResponse("/employees?error=save_failed", 303)
    return RedirectResponse("/employees?saved=1", 302)


@app.post("/employees/{eid}/delete")
async def employees_delete(request: Request, eid: int):
    u, redir = require_page(request, "employees")
    if redir:
        return redir
    if eid == u["id"]:
        return RedirectResponse("/employees?error=cannot_delete_self", 303)
    async with await get_conn() as db:
        if not is_superadmin(u):
            row = await db.fetchone(
                "SELECT id FROM staff WHERE id=? AND shop_id=? AND role!='superadmin'",
                (eid, u.get("shop_id")),
            )
            if not row:
                return RedirectResponse("/employees", 303)
        await db.execute(
            "UPDATE staff SET active=0 WHERE id=? AND role!='superadmin'", (eid,)
        )
        await db.commit()
    return RedirectResponse("/employees?saved=deleted", 302)


# ═══════════════════════════════════════════════════════════════════════════
# REPORTS (admin)
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    u, redir = require_page(request, "reports")
    if redir:
        return redir

    async with await get_conn() as db:
        sh, sp = sql_shop(u)
        sb, sbp = sql_shop_prefixed(u, "b")
        totals = await db.fetchone(
            f"""SELECT COALESCE(SUM(total),0) AS revenue,
                      COALESCE(SUM(discount),0) AS discount,
                      COALESCE(SUM(tax),0) AS tax,
                      COUNT(*) AS bills
               FROM bill WHERE 1=1{sh}""",
            sp,
        )
        profit_row = await db.fetchone(
            f"""SELECT COALESCE(SUM(bi.line_total - (COALESCE(bi.cost,0) * bi.qty)),0) AS profit
               FROM bill_item bi
               JOIN bill b ON b.id=bi.bill_id
               WHERE 1=1{sb}""",
            sbp,
        )
        best_buyer = await db.fetchone(
            f"""SELECT COALESCE(NULLIF(customer_name,''), customer_mobile, 'Walk-in') AS buyer,
                      COALESCE(customer_mobile,'') AS mobile,
                      COUNT(*) AS bills, COALESCE(SUM(total),0) AS spent
               FROM bill
               WHERE (COALESCE(customer_mobile,'') <> '' OR COALESCE(customer_name,'') <> ''){sh}
               GROUP BY 1, 2
               ORDER BY spent DESC LIMIT 1""",
            sp,
        )
        best_product = await db.fetchone(
            f"""SELECT COALESCE(bi.name, bi.sku, '—') AS product, bi.sku,
                      COALESCE(SUM(bi.qty),0) AS qty_sold,
                      COALESCE(SUM(bi.line_total),0) AS amount
               FROM bill_item bi
               JOIN bill b ON b.id=bi.bill_id
               WHERE 1=1{sb}
               GROUP BY bi.name, bi.sku
               ORDER BY qty_sold DESC LIMIT 1""",
            sbp,
        )
        best_biller = await db.fetchone(
            f"""SELECT s.name AS biller, COUNT(b.id) AS bills, COALESCE(SUM(b.total),0) AS amount
               FROM bill b
               JOIN staff s ON s.id=b.staff_id
               WHERE 1=1{sb}
               GROUP BY s.id, s.name
               ORDER BY amount DESC LIMIT 1""",
            sbp,
        )
        top_products = await db.fetchall(
            f"""SELECT COALESCE(bi.name, bi.sku) AS product, bi.sku,
                      COALESCE(SUM(bi.qty),0) AS qty_sold,
                      COALESCE(SUM(bi.line_total),0) AS amount
               FROM bill_item bi
               JOIN bill b ON b.id=bi.bill_id
               WHERE 1=1{sb}
               GROUP BY bi.name, bi.sku
               ORDER BY qty_sold DESC LIMIT 8""",
            sbp,
        )
        top_billers = await db.fetchall(
            f"""SELECT s.name AS biller, COUNT(b.id) AS bills, COALESCE(SUM(b.total),0) AS amount
               FROM bill b
               JOIN staff s ON s.id=b.staff_id
               WHERE 1=1{sb}
               GROUP BY s.id, s.name
               ORDER BY amount DESC LIMIT 8""",
            sbp,
        )
        top_buyers = await db.fetchall(
            f"""SELECT COALESCE(NULLIF(customer_name,''), customer_mobile, 'Walk-in') AS buyer,
                      COALESCE(customer_mobile,'') AS mobile,
                      COUNT(*) AS bills, COALESCE(SUM(total),0) AS spent
               FROM bill
               WHERE 1=1{sh}
               GROUP BY 1, 2
               ORDER BY spent DESC LIMIT 8""",
            sp,
        )
        today = date.today().isoformat()
        today_row = await db.fetchone(
            f"""SELECT COALESCE(SUM(total),0) AS revenue, COUNT(*) AS bills
               FROM bill WHERE bill_date=?{sh}""",
            (today, *sp),
        )

    return templates.TemplateResponse(
        "reports.html",
        tctx(
            request, user=u, active="reports",
            totals=totals, profit=money(profit_row["profit"] if profit_row else 0),
            best_buyer=best_buyer, best_product=best_product, best_biller=best_biller,
            top_products=top_products, top_billers=top_billers, top_buyers=top_buyers,
            today_row=today_row,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# MY THEME (per-user — every store user can set their own)
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/my-theme", response_class=HTMLResponse)
async def my_theme_get(request: Request):
    u = require_login(request)
    if not u:
        return RedirectResponse("/login")
    shop_default = _get("theme_preset", "default")
    current = (u.get("theme_preset") or request.session.get("theme_preset") or "").strip()
    presets_json = json.dumps({
        k: {"label": v["label"], "mode": v["mode"], "colors": v["colors"]}
        for k, v in THEME_PRESETS.items()
    })
    return templates.TemplateResponse(
        "my_theme.html",
        tctx(
            request, user=u, active="my_theme",
            current_preset=current,
            shop_default=shop_default,
            theme_presets=THEME_PRESETS,
            theme_presets_json=presets_json,
            saved=request.query_params.get("saved"),
        ),
    )


@app.post("/my-theme")
async def my_theme_post(request: Request):
    u = require_login(request)
    if not u:
        return RedirectResponse("/login")
    form = await request.form()
    preset = str(form.get("theme_preset", "")).strip()
    if preset == "__shop__":
        preset = ""
    elif preset and preset not in THEME_PRESETS:
        preset = ""
    async with await get_conn() as db:
        await db.execute(
            "UPDATE staff SET theme_preset=? WHERE id=?",
            (preset, u["id"]),
        )
        await db.commit()
        row = await db.fetchone("SELECT * FROM staff WHERE id=?", (u["id"],))
    if row:
        request.session["user"] = session_user_from_row(row)
    request.session["theme_preset"] = preset
    return RedirectResponse("/my-theme?saved=1", 303)


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS / THEMES
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/settings", response_class=HTMLResponse)
async def settings_get(request: Request):
    u, redir = require_page(request, "settings")
    if redir:
        return redir
    s = dict(DEFAULT_THEME)
    s.update(_SETTINGS)
    presets_json = json.dumps({
        k: {"label": v["label"], "mode": v["mode"], "colors": v["colors"]}
        for k, v in THEME_PRESETS.items()
    })
    return templates.TemplateResponse(
        "settings.html",
        tctx(
            request, user=u, s=s, active="settings",
            theme_presets=THEME_PRESETS, theme_presets_json=presets_json,
            saved=request.query_params.get("saved"),
            reset_done=request.query_params.get("reset"),
            gst_all=request.query_params.get("gst_all"),
        ),
    )


@app.post("/settings")
async def settings_post(request: Request):
    u, redir = require_page(request, "settings")
    if redir:
        return redir
    form = await request.form()

    def fv(k, d=""):
        return str(form.get(k, d)).strip() or d

    preset = fv("theme_preset", "custom")
    if preset in THEME_PRESETS:
        colors = dict(THEME_PRESETS[preset]["colors"])
        for ck in THEME_COLOR_KEYS:
            posted = fv(ck, "")
            if posted:
                colors[ck] = posted
    else:
        preset = "custom"
        colors = {ck: fv(ck, DEFAULT_THEME[ck]) for ck in THEME_COLOR_KEYS}

    lang = get_lang(request)
    pairs = [
        ("app_name", fv("app_name", "BillingPro")),
        ("app_tagline", und(fv("app_tagline", APP_TAGLINE), lang)),
        ("theme_preset", preset),
        ("default_lang", fv("default_lang", "en")),
        ("default_gst_pct", str(money(fv("default_gst_pct", "18")))),
        ("bill_greeting", und(fv("bill_greeting", "Welcome! Thank you for shopping with us."), lang)),
        ("bill_thanks", und(fv("bill_thanks", "Thank you! Please visit again."), lang)),
    ] + list(colors.items())

    # Branding uploads
    logo_url = _get("app_logo", "")
    bg_url = _get("app_bg_image", "")
    if form.get("clear_logo"):
        _clear_brand_file(logo_url)
        logo_url = ""
    if form.get("clear_bg"):
        _clear_brand_file(bg_url)
        bg_url = ""
    new_logo = await _save_brand_upload(form.get("app_logo_file"), "logo")
    if new_logo:
        if logo_url and logo_url != new_logo:
            _clear_brand_file(logo_url)
        logo_url = new_logo
    new_bg = await _save_brand_upload(form.get("app_bg_file"), "background")
    if new_bg:
        if bg_url and bg_url != new_bg:
            _clear_brand_file(bg_url)
        bg_url = new_bg
    pairs.extend([
        ("app_logo", logo_url),
        ("app_bg_image", bg_url),
    ])

    async with await get_conn() as db:
        for k, v in pairs:
            await db.execute(
                "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                (k, v),
            )
        await db.commit()
    await reload_settings()

    # Keep products that follow default GST in sync with the new default
    new_gst = default_gst_pct()
    sh, sp = sql_shop(u)
    async with await get_conn() as db:
        await db.execute(
            f"UPDATE product SET gst_pct=? WHERE COALESCE(gst_override,0)=0{sh}",
            (new_gst, *sp),
        )
        await db.commit()

    return RedirectResponse("/settings?saved=1", 302)


@app.post("/settings/gst-apply-all")
async def settings_gst_apply_all(request: Request):
    """Set default GST % on ALL products in this shop (clears individual overrides)."""
    u, redir = require_page(request, "settings")
    if redir:
        return redir
    form = await request.form()
    gst = money(form.get("default_gst_pct") or _get("default_gst_pct", "18"))
    async with await get_conn() as db:
        await db.execute(
            "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
            ("default_gst_pct", str(gst)),
        )
        sh, sp = sql_shop(u)
        await db.execute(
            f"UPDATE product SET gst_pct=?, gst_override=0 WHERE 1=1{sh}",
            (gst, *sp),
        )
        await db.commit()
    await reload_settings()
    return RedirectResponse("/settings?saved=1&gst_all=1", 302)


@app.post("/settings/reset")
async def settings_reset(request: Request):
    u, redir = require_page(request, "settings")
    if redir:
        return redir
    async with await get_conn() as db:
        await db.execute(
            "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
            ("theme_preset", "default"),
        )
        for k in THEME_COLOR_KEYS:
            await db.execute(
                "INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                (k, DEFAULT_THEME[k]),
            )
        await db.commit()
    await reload_settings()
    return RedirectResponse("/settings?saved=1&reset=1", 302)


# ── Data Assistant (superadmin + store admin; shop-scoped) ───────────────────

@app.get("/api/assistant/suggestions")
async def assistant_suggestions(request: Request):
    u = cur_user(request)
    if not u:
        return JSONResponse({"error": "not logged in"}, 401)
    if not can_use_assistant(u):
        return JSONResponse({"error": DENY_MSG}, 403)
    shops = []
    scope = "your shop only"
    async with await get_conn() as db:
        if is_superadmin(u):
            scope = "all shops"
            rows = await db.fetchall(
                "SELECT id, name, code FROM shop WHERE active=1 ORDER BY name"
            )
            shops = [{"id": r["id"], "name": r["name"], "code": r.get("code") or ""} for r in rows]
        elif u.get("shop_id"):
            row = await db.fetchone("SELECT id, name, code FROM shop WHERE id=?", (u["shop_id"],))
            if row:
                shops = [{"id": row["id"], "name": row["name"], "code": row.get("code") or ""}]
    return JSONResponse({
        "chips": chips_for_user(u),
        "shops": shops,
        "scope": scope,
        "is_superadmin": is_superadmin(u),
    })


async def _assistant_run(u, question: str, shop_filter: str | None):
    qkey, params = match_intent(question)
    deny = detect_out_of_scope(u, question, qkey, shop_filter)
    if deny:
        raise PermissionError(deny)
    async with await get_conn() as db:
        return await run_query(db, qkey, params, u, shop_filter)


@app.post("/api/assistant/query")
async def assistant_query(request: Request):
    u = cur_user(request)
    if not u:
        return JSONResponse({"error": "not logged in"}, 401)
    if not can_use_assistant(u):
        return JSONResponse({"error": DENY_MSG}, 403)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, 400)
    question = str(body.get("question", "")).strip()
    shop_filter = str(body.get("shop_filter", "") or "").strip() or None
    if not question:
        return JSONResponse({"error": "Please enter a question"}, 400)
    try:
        result = await _assistant_run(u, question, shop_filter)
        return JSONResponse({
            "title": result["title"],
            "columns": result["columns"],
            "rows": result["rows"],
            "row_count": len(result["rows"]),
            "sql_hint": result.get("sql_hint", ""),
            "query_key": result.get("query_key", ""),
            "question": question,
        })
    except PermissionError as e:
        return JSONResponse({"error": str(e) or DENY_MSG}, 403)
    except Exception as e:
        return JSONResponse({"error": f"Query failed: {e}"}, 500)


@app.post("/api/assistant/csv")
async def assistant_csv(request: Request):
    u = cur_user(request)
    if not u:
        return JSONResponse({"error": "not logged in"}, 401)
    if not can_use_assistant(u):
        return JSONResponse({"error": DENY_MSG}, 403)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, 400)
    question = str(body.get("question", "")).strip()
    shop_filter = str(body.get("shop_filter", "") or "").strip() or None
    if not question:
        return JSONResponse({"error": "Please enter a question"}, 400)
    try:
        result = await _assistant_run(u, question, shop_filter)
        csv_text = rows_to_csv(result["columns"], result["rows"])
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="billingpro_query.csv"'},
        )
    except PermissionError as e:
        return JSONResponse({"error": str(e) or DENY_MSG}, 403)
    except Exception as e:
        return JSONResponse({"error": f"CSV export failed: {e}"}, 500)


# Register advanced feature routes
from advanced import register_advanced
from i18n import d as _d_fn

register_advanced(app, {
    "get_conn": get_conn,
    "templates": templates,
    "tctx": tctx,
    "require_login": require_login,
    "is_admin": is_admin,
    "tr": tr,
    "get_lang": get_lang,
    "d": _d_fn,
    "parse_card_last4": parse_card_last4,
    "build_bill_lines": build_bill_lines,
    "_get": _get,
    "ensure_column": ensure_column,
    "hash_pw": hash_pw,
    "require_page": require_page,
    "default_gst_pct": default_gst_pct,
    "product_effective_gst": product_effective_gst,
})
