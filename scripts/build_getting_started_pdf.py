"""Build BillingPro Getting Started PDF guide."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

OUT = Path(__file__).resolve().parents[1] / "docs" / "BillingPro_Getting_Started_Guide.pdf"
TEAL = HexColor("#0F766E")


def bullets(items, styles):
    return ListFlowable(
        [ListItem(Paragraph(i, styles["BodyText"]), leftIndent=8, bulletColor=TEAL) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        bulletFontSize=10,
    )


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="BillingPro Getting Started Guide",
        author="Infinexen Technologies",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBP", parent=styles["Title"], textColor=TEAL, fontSize=20, spaceAfter=6))
    styles.add(ParagraphStyle(name="HBP", parent=styles["Heading2"], textColor=TEAL, fontSize=13, spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="SubBP", parent=styles["Normal"], fontSize=10, textColor=HexColor("#5D6D7E"), spaceAfter=10))

    story = []
    story.append(Paragraph("BillingPro", styles["TitleBP"]))
    story.append(Paragraph("Getting Started Guide — simple steps in order", styles["SubBP"]))
    story.append(Paragraph(
        "Point of Sale &amp; billing · Infinexen Technologies · 2026<br/>"
        "Use this checklist when setting up a shop and training staff.",
        styles["BodyText"],
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("0. Start the application", styles["HBP"]))
    story.append(bullets([
        "Windows: double-click START_BILLINGPRO.bat (or run python run.py).",
        "Open http://localhost:8003 in a browser.",
        "Default logins — Super Admin: superadmin / superadmin123; Store Admin: admin / admin123; Cashier: cashier / cashier123.",
        "Change these passwords before real use.",
    ], styles))

    story.append(Paragraph("1. Super Admin — shop &amp; features", styles["HBP"]))
    story.append(bullets([
        "Shops / branches — add the store (name, code, address).",
        "Features &amp; admin — enable only the modules that shop paid for.",
        "Create store admin — username/password for the shop owner/manager.",
    ], styles))

    story.append(Paragraph("2. Store Admin — setup (strict order)", styles["HBP"]))
    story.append(bullets([
        "Settings — shop branding, default GST %, bill messages, theme.",
        "Counters — create billing counters (Counter 1, Counter 2, …).",
        "Employees — add cashiers; assign each to a counter.",
        "Assign pages — tick which screens each user may open, then Save (menu updates on next click).",
        "Suppliers — add vendors you purchase from.",
        "Products — add catalogue (single form or Excel/CSV upload); set MRP, cost, GST, stock.",
        "Purchases / GRN — receive goods: choose supplier, product, qty, purchase rate (stock increases).",
        "Supplier templates (optional) — save recurring lists; download Excel sample; upload; Receive into stock.",
        "Stock — check quantities; adjust only when needed.",
        "Warehouses / Batches (optional) — if those features are enabled.",
        "Loyalty / Coupons (optional) — customer rewards and promos.",
        "Barcode labels — print from Products when ready to tag shelves.",
    ], styles))

    story.append(Paragraph("3. Daily billing (cashier)", styles["HBP"]))
    story.append(bullets([
        "New Bill — search or scan SKU → add lines → take payment (cash / card / UPI / split).",
        "Held bills — pause a bill and recall later.",
        "Bills — find, view, reprint, or edit (if allowed).",
        "Returns — process returns / credit notes.",
        "Credit (Udhaar) — credit sales and collections.",
        "Day close — close the counter day and record cash.",
    ], styles))

    story.append(Paragraph("4. Reports &amp; tax", styles["HBP"]))
    story.append(bullets([
        "Dashboard / Reports — sales and profit overview.",
        "Shifts — sales by counter / staff.",
        "GST export — download CSV for tax filing.",
        "Audit log — track important changes.",
        "Reorder — products below reorder level.",
    ], styles))

    story.append(Paragraph("5. Menu layout (left sidebar)", styles["HBP"]))
    story.append(bullets([
        "Overview — Dashboard, Reports, Shifts, Day close.",
        "Billing — New Bill, Holds, Bills, Returns, Credit.",
        "Inventory — Suppliers → Products → Purchases → Templates → Stock → Reorder → Warehouses → Batches.",
        "Customers — Loyalty, Coupons.",
        "Reports &amp; tax — GST export, Audit.",
        "Administration — Settings, Counters, Employees, Assign pages, Shops, Offline.",
        "Help — on-screen guide and this PDF.",
    ], styles))

    story.append(Paragraph("6. Quick tips", styles["HBP"]))
    story.append(bullets([
        "If a menu item is missing: Super Admin must enable the feature for the shop, and Store Admin must Assign pages for that user.",
        "Stock should normally increase via Purchases (GRN), not only by editing product stock.",
        "Profit = sale ex-GST − purchase cost; GST collected is tracked separately.",
        "Languages: English / Tamil / Hindi from the top bar.",
    ], styles))

    doc.build(story)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
