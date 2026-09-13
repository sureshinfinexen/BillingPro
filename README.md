# BillingPro

Point-of-sale & billing for retail. Themes follow the FactPro model. UI: **English**, **Tamil**, **Hindi**.

## Roles

- **Super Admin** — all shops; enable feature packs when selling to a store; create store admins  
- **Store Admin** — run one shop; assign screens/pages to cashiers  
- **Cashier** — only assigned pages for enabled features  

## Quick start

See **[docs/SETUP.md](docs/SETUP.md)** (full step-by-step). Short version:

```bash
createdb -h localhost -p 5433 -U postgres billingpro
cd D:\Source\BillingPro
copy .env.example .env
python run.py
```

Open http://localhost:8003

| User | Password |
|------|----------|
| `superadmin` | `superadmin123` |
| `admin` | `admin123` |
| `cashier` | `cashier123` |

## Documentation

- [docs/SETUP.md](docs/SETUP.md) — install from zero  
- [docs/FUNCTIONALITY.md](docs/FUNCTIONALITY.md) — complete features & access model  

## Features (summary)

Products, POS billing (GST, card last-4), bills, stock, counters/employees, holds/returns/credit, loyalty/coupons, purchases/warehouses/batches, day-close/shifts, GST export, audit, offline helper, multi-shop feature packs, page assignment.
