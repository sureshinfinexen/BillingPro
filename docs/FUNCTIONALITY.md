# BillingPro — Complete Functionality

This document describes what the application does and how **Super Admin**, **Store Admin**, and **Cashier** access works.

---

## 1. Roles overview

```
Super Admin (platform)
   └── enables feature packs per Shop
   └── creates Store Admin per shop
         └── Store Admin
               └── assigns pages/screens to Cashiers (and optionally other admins)
                     └── Cashier uses only assigned + enabled screens
```

| Role | Scope | Typical tasks |
|------|--------|----------------|
| **Super Admin** | All shops | Create shops, toggle modules (sell packs), create store admins, full access |
| **Store Admin** (`admin`) | One shop | Products, staff, counters, reports (if enabled), **Assign pages** |
| **Cashier** | One shop + counter | Billing and other screens assigned by store admin |

Access rule for every screen:

1. User role allows the page, **and**
2. Page is in the user’s **assigned pages**, **and**
3. The shop has that module **enabled** in its feature pack  
   (Super Admin bypasses all checks.)

---

## 2. Feature packs (selling to a store)

Managed by Super Admin: **Shops → Features & admin**.

| Feature key | What it unlocks |
|-------------|-----------------|
| `billing` *(core)* | New bill, bills list/view/edit |
| `stock` *(core)* | Stock view & adjust |
| `products` *(core)* | Product master + CSV |
| `holds` | Hold / recall bills |
| `returns` | Returns / credit notes |
| `credit` | Credit sales (Udhaar) + payments |
| `loyalty` | Loyalty points |
| `coupons` | Coupons / promotions |
| `reorder` | Low-stock reorder list |
| `purchases` | Purchases / GRN |
| `warehouses` | Warehouses & transfers |
| `batches` | Batch / expiry |
| `day_close` | Day-end closing |
| `shifts` | Shift / counter sales reports |
| `reports` | Dashboard + sales reports |
| `gst_export` | GST CSV export |
| `audit` | Audit log |
| `offline` | Offline mode helper |
| `multi_shop` | Reserved for multi-branch packs |

Core modules always stay available for a licensed shop.

---

## 3. Page assignment (store admin)

**Administration → Assign pages**

For each employee, tick screens they may open. Only pages whose **feature is enabled** for the shop appear.

Default cashier pages: billing, bills, holds, stock, returns, credit, day_close, reorder.  
Default store admin pages: all admin-capable pages except Super-Admin-only feature management.

After changing pages, the user should **log out and log in** so the session refreshes (shop features are loaded at login).

---

## 4. Module catalogue

### Overview
- **Dashboard** — today’s sales, product count, recent bills  
- **Reports** — revenue, tax, profit, best buyer/product  
- **Shifts** — sales by counter / staff  
- **Day close** — expected vs actual cash/UPI/card  

### Billing
- **New bill** — SKU/name search, barcode, MRP/discount/rate, GST (CGST/SGST), customer mobile, cash/UPI/card (card last 4 required), hold, coupons, loyalty, credit, split concepts where enabled  
- **Held bills** — recall or delete holds  
- **Bills** — list, view, print/thermal, WhatsApp link, edit (stock restore + re-deduct)  
- **Returns** — return against a bill  
- **Credit (Udhaar)** — outstanding + record payment  

### Inventory
- **Stock** — search, set/add/remove qty  
- **Reorder** — below reorder level  
- **Products** — CRUD, HSN, GST%, CSV upload  
- **Purchases / GRN** — receive stock  
- **Warehouses** — locations + transfer  
- **Batches** — batch/expiry tracking  

### Customers
- **Loyalty** — points ledger  
- **Coupons** — e.g. sample `SAVE10`  

### Reports & tax
- **GST export** — CSV for a date range  
- **Audit log** — staff actions  

### Administration
- **Shops** — list; Super Admin adds shops + feature packs + store admins  
- **Counters** — POS counters  
- **Employees** — admin/cashier users (tied to shop)  
- **Assign pages** — per-user screens  
- **Offline** — offline cache helper  
- **Settings** — app name, languages, theme presets/colours, bill greeting/thanks  

### Languages
English, Tamil, Hindi (UI labels; known seed names localized; user-typed data stays as entered).

---

## 5. Typical workflows

### A. Platform owner onboards a new paying store
1. Login `superadmin`  
2. Add shop + select paid features  
3. Create store admin account for that shop  
4. Hand credentials + SETUP.md to the store  

### B. Store admin goes live
1. Login as store admin  
2. Settings (name, theme, language)  
3. Counters + products (or CSV)  
4. Employees (cashiers)  
5. Assign pages per cashier  
6. Train cashiers on New Bill  

### C. Daily cashier
1. Login → New Bill  
2. Scan/search items → pay → print  
3. Optional: hold, returns, day close (if assigned)  

---

## 6. Default seed data

- Shop: **Main Shop** (`S1`) — all features enabled  
- Counters: Counter 1 (`C1`), Counter 2 (`C2`)  
- Sample grocery products + coupon `SAVE10`  
- Users: `superadmin`, `admin`, `cashier` (see SETUP.md)  

---

## 7. Technical notes

| Piece | Location |
|-------|----------|
| Access rules | `access.py` |
| Main app / POS | `app.py` |
| Advanced modules | `advanced.py` |
| Translations | `i18n.py` |
| Config | `config.py`, `.env` |
| Launcher | `run.py`, `START_BILLINGPRO.bat` |

Shop features are stored as JSON on `shop.features`.  
User screens are stored on `staff.pages` (and mirrored to `permissions` for compatibility).

Restart the app after code updates. Schema migrations run automatically on startup (`ensure_column` / `ensure_advanced_schema`).

---

## 8. Security recommendations

- Change all default passwords immediately  
- Change `SECRET_KEY` in `.env`  
- Do not expose PostgreSQL to the public internet  
- Give cashiers only the pages they need  
- Use Super Admin only on the vendor/owner machine  

---

For install order, see **[SETUP.md](SETUP.md)**.
