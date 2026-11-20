"""Data Q&A chatbot core: understands simple questions and answers them with SQL.

No API key needed. Uses SQLite (built into Python) and keyword/intent matching.
"""
import random
import re
import sqlite3
from datetime import date, timedelta

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Laptop", "Phone", "Tablet", "Headphones"]


def build_database(path=":memory:"):
    """Create a sample sales database so the bot has data to answer from."""
    random.seed(42)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sales ("
        "id INTEGER PRIMARY KEY, sale_date TEXT, region TEXT, "
        "product TEXT, units INTEGER, revenue REAL)"
    )
    if conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0:
        start = date(2026, 1, 1)
        price = {"Laptop": 60000, "Phone": 30000, "Tablet": 25000, "Headphones": 3000}
        rows = []
        for i in range(400):
            product = random.choice(PRODUCTS)
            units = random.randint(1, 10)
            rows.append((
                (start + timedelta(days=random.randint(0, 300))).isoformat(),
                random.choice(REGIONS), product, units, units * price[product],
            ))
        conn.executemany(
            "INSERT INTO sales (sale_date, region, product, units, revenue) VALUES (?,?,?,?,?)",
            rows,
        )
        conn.commit()
    return conn


def _find(text, options):
    for opt in options:
        if opt.lower() in text:
            return opt
    return None


def answer(question, conn):
    """Return (reply_text, sql_used_or_None)."""
    q = question.lower().strip()
    region = _find(q, REGIONS)
    product = _find(q, PRODUCTS)

    filters, params = [], []
    if region:
        filters.append("region = ?")
        params.append(region)
    if product:
        filters.append("product = ?")
        params.append(product)
    where = (" WHERE " + " AND ".join(filters)) if filters else ""
    scope = " ".join(x for x in [product, f"in {region}" if region else ""] if x) or "all sales"

    if re.search(r"\b(hi|hello|hey|help)\b", q):
        return (
            "Hi! Ask me about the sales data. Try: 'total revenue', "
            "'revenue in South', 'top product', 'best region', "
            "'units sold for Phone', 'monthly revenue', 'how many records'.",
            None,
        )

    if re.search(r"(top|best|highest).*(product)|which product", q):
        sql = f"SELECT product, SUM(revenue) FROM sales{where} GROUP BY product ORDER BY 2 DESC LIMIT 1"
        name, rev = conn.execute(sql, params).fetchone()
        return f"Top product ({scope}): {name} with revenue Rs {rev:,.0f}.", sql

    if re.search(r"(top|best|highest).*(region)|which region", q):
        sql = f"SELECT region, SUM(revenue) FROM sales{where} GROUP BY region ORDER BY 2 DESC LIMIT 1"
        name, rev = conn.execute(sql, params).fetchone()
        return f"Best region ({scope}): {name} with revenue Rs {rev:,.0f}.", sql

    if "month" in q:
        sql = (
            "SELECT substr(sale_date,1,7) AS month, SUM(revenue) FROM sales"
            f"{where} GROUP BY month ORDER BY month"
        )
        rows = conn.execute(sql, params).fetchall()
        lines = [f"{m}: Rs {r:,.0f}" for m, r in rows]
        return f"Monthly revenue ({scope}):\n" + "\n".join(lines), sql

    if re.search(r"unit|quantity|sold", q):
        sql = f"SELECT SUM(units) FROM sales{where}"
        total = conn.execute(sql, params).fetchone()[0] or 0
        return f"Units sold ({scope}): {total:,}.", sql

    if re.search(r"revenue|sales|total|earn", q):
        sql = f"SELECT SUM(revenue) FROM sales{where}"
        total = conn.execute(sql, params).fetchone()[0] or 0
        return f"Total revenue ({scope}): Rs {total:,.0f}.", sql

    if re.search(r"how many|count|records|rows", q):
        sql = f"SELECT COUNT(*) FROM sales{where}"
        total = conn.execute(sql, params).fetchone()[0]
        return f"Number of sales records ({scope}): {total}.", sql

    return (
        "Sorry, I didn't get that. Try 'total revenue', 'top product', "
        "'best region' or 'monthly revenue in West'.",
        None,
    )
