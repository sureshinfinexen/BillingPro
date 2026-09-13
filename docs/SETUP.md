# BillingPro — Setup Guide

Follow these steps in order. Anyone with this document should be able to install and run BillingPro.

---

## 1. What you need

| Item | Notes |
|------|--------|
| Windows / Mac / Linux | Tested on Windows 10+ |
| Python 3.9+ | 3.11+ recommended |
| PostgreSQL | Same style as FactPro; default port **5433** |
| Disk | ~200 MB for venv + app |

---

## 2. Create the database (once)

```bash
# Option A — createdb
createdb -h localhost -p 5433 -U postgres billingpro

# Option B — psql
psql -h localhost -p 5433 -U postgres -c "CREATE DATABASE billingpro;"
```

If PostgreSQL uses another host/port/password, note them for the `.env` step.

---

## 3. Get the application files

Copy or clone the `BillingPro` folder (example: `D:\Source\BillingPro`).

---

## 4. Configure environment

```bash
cd D:\Source\BillingPro
copy .env.example .env
```

Edit `.env`:

```env
POSTGRES_DSN=postgresql://postgres:YOUR_PASSWORD@localhost:5433/billingpro
SECRET_KEY=change-this-to-a-long-random-string
PORT=8003
```

---

## 5. Install and start (easiest)

**Windows:** double-click `START_BILLINGPRO.bat`  
(or run `START_BILLINGPRO.cmd`)

**Any OS:**

```bash
cd D:\Source\BillingPro
python run.py
```

`run.py` creates a virtualenv if needed, installs `requirements.txt`, and starts the server.

Open: **http://localhost:8003**

Tables, sample products, counters, and default users are created automatically on first start.

---

## 6. Manual install (optional)

```bash
cd D:\Source\BillingPro
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
python run.py
```

---

## 7. First logins

| Role | Username | Password | Purpose |
|------|----------|----------|---------|
| **Super Admin** | `superadmin` | `superadmin123` | Platform owner: all shops, enable/disable feature packs, create store admins |
| **Store Admin** | `admin` | `admin123` | Default Main Shop admin: products, employees, assign pages |
| **Cashier** | `cashier` | `cashier123` | Counter 1 billing |

**Change these passwords after first login in production.**

---

## 8. Selling BillingPro to another store (checklist)

1. Login as **superadmin**.
2. Go to **Shops / branches** → **Add shop** (name, code, address).
3. Tick only the **feature pack** modules that store paid for (billing/stock/products stay on).
4. Open **Features & admin** for that shop → **Create store admin** (username/password for the buyer).
5. Tell the store admin to:
   - Login and set theme/language under **Settings**
   - Add **Counters** and **Employees** (cashiers)
   - Open **Assign pages** and tick screens each cashier may use
6. Cashiers login and only see assigned screens that are also enabled for the shop.

---

## 9. Languages

English (default), Tamil, Hindi — switch from the top bar after login.

---

## 10. Stop / restart

- Stop: close the terminal or press `Ctrl+C`
- Restart: run `START_BILLINGPRO.bat` or `python run.py` again

---

## 11. Troubleshooting

| Problem | Fix |
|---------|-----|
| Cannot connect to database | Check PostgreSQL is running; verify `POSTGRES_DSN` in `.env` |
| Port already in use | Change `PORT=8003` in `.env` or free port 8003 |
| Blank / login fails | Confirm DB `billingpro` exists; delete bad rows or recreate DB if needed |
| Menu missing for cashier | Store admin → **Assign pages**; Super Admin → shop **Features** |
| Import errors | Re-run `python run.py` so dependencies install |

---

## 12. Related docs

- **[FUNCTIONALITY.md](FUNCTIONALITY.md)** — full feature list and roles
- **[../README.md](../README.md)** — short project overview
