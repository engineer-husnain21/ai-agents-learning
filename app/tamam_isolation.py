"""
tamam_isolation.py — the core safety guarantee for the Tamam Living
assistant: "a tenant must never, ever see another tenant's data."

Design: instead of trusting a model-generated SQL query to include the
right WHERE clause, we build a FRESH, TEMPORARY, in-memory SQLite
database for every single request, containing ONLY that tenant's own
rows. Other tenants' rows are never copied in — they don't exist in
this database at all. Even a query with no WHERE clause, or a wrong
one, cannot leak another tenant's data, because there is nothing there
to leak. This is a stronger guarantee than "the query is well-formed"
— it's "the data structurally isn't present."

Same lesson as task 15's read-only connection and task 11's blast
radius: code enforces isolation, the model is never trusted to.
"""

import sqlite3

MAIN_DB_PATH = "tamam.db"


def build_tenant_scoped_db(tenant_id):
    """
    Returns a fresh in-memory sqlite3.Connection containing ONLY this
    tenant's own rows, in the same table shapes as the main database.
    """
    main_conn = sqlite3.connect(f"file:{MAIN_DB_PATH}?mode=ro", uri=True)

    tenant_row = main_conn.execute(
        "SELECT tenant_id, full_name, unit_id, lease_start, lease_end FROM tenants WHERE tenant_id = ?",
        (tenant_id,)
    ).fetchone()

    if tenant_row is None:
        main_conn.close()
        return None

    unit_id = tenant_row[2]
    unit_row = main_conn.execute(
        "SELECT unit_id, building_id, unit_number, bedrooms, monthly_rent FROM units WHERE unit_id = ?",
        (unit_id,)
    ).fetchone()
    building_id = unit_row[1]
    building_row = main_conn.execute(
        "SELECT building_id, building_name, area FROM buildings WHERE building_id = ?",
        (building_id,)
    ).fetchone()

    ticket_rows = main_conn.execute(
        "SELECT ticket_id, unit_id, category, opened_date, closed_date, status FROM tickets WHERE unit_id = ?",
        (unit_id,)
    ).fetchall()

    payment_rows = main_conn.execute(
        "SELECT payment_id, tenant_id, due_date, paid_date, amount FROM payments WHERE tenant_id = ?",
        (tenant_id,)
    ).fetchall()

    main_conn.close()

    # Build the scoped in-memory database — same schema, only this
    # tenant's rows exist in it.
    scoped_conn = sqlite3.connect(":memory:")
    scoped_conn.executescript("""
        CREATE TABLE buildings (building_id INTEGER PRIMARY KEY, building_name TEXT, area TEXT);
        CREATE TABLE units (unit_id INTEGER PRIMARY KEY, building_id INTEGER, unit_number TEXT, bedrooms INTEGER, monthly_rent REAL);
        CREATE TABLE tenants (tenant_id INTEGER PRIMARY KEY, full_name TEXT, unit_id INTEGER, lease_start TEXT, lease_end TEXT);
        CREATE TABLE tickets (ticket_id INTEGER PRIMARY KEY, unit_id INTEGER, category TEXT, opened_date TEXT, closed_date TEXT, status TEXT);
        CREATE TABLE payments (payment_id INTEGER PRIMARY KEY, tenant_id INTEGER, due_date TEXT, paid_date TEXT, amount REAL);
    """)

    scoped_conn.execute("INSERT INTO buildings VALUES (?, ?, ?)", building_row)
    scoped_conn.execute("INSERT INTO units VALUES (?, ?, ?, ?, ?)", unit_row)
    scoped_conn.execute("INSERT INTO tenants VALUES (?, ?, ?, ?, ?)", tenant_row)
    for row in ticket_rows:
        scoped_conn.execute("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)", row)
    for row in payment_rows:
        scoped_conn.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?)", row)

    scoped_conn.commit()
    return scoped_conn


def build_manager_scoped_db(building_id):
    """
    For building managers (per the client's request: 'building managers
    keep asking for tenants to see how their building is doing overall
    — open maintenance jobs, that kind of thing'). Scoped to ONE
    building's aggregate ticket data — never individual tenant payment
    amounts or names, to stay consistent with the isolation guarantee.
    """
    main_conn = sqlite3.connect(f"file:{MAIN_DB_PATH}?mode=ro", uri=True)

    building_row = main_conn.execute(
        "SELECT building_id, building_name, area FROM buildings WHERE building_id = ?",
        (building_id,)
    ).fetchone()

    unit_rows = main_conn.execute(
        "SELECT unit_id, building_id, unit_number, bedrooms, monthly_rent FROM units WHERE building_id = ?",
        (building_id,)
    ).fetchall()

    unit_ids = [r[0] for r in unit_rows]
    placeholders = ",".join("?" * len(unit_ids))
    ticket_rows = main_conn.execute(
        f"SELECT ticket_id, unit_id, category, opened_date, closed_date, status FROM tickets WHERE unit_id IN ({placeholders})",
        unit_ids
    ).fetchall()

    main_conn.close()

    scoped_conn = sqlite3.connect(":memory:")
    scoped_conn.executescript("""
        CREATE TABLE buildings (building_id INTEGER PRIMARY KEY, building_name TEXT, area TEXT);
        CREATE TABLE units (unit_id INTEGER PRIMARY KEY, building_id INTEGER, unit_number TEXT, bedrooms INTEGER, monthly_rent REAL);
        CREATE TABLE tickets (ticket_id INTEGER PRIMARY KEY, unit_id INTEGER, category TEXT, opened_date TEXT, closed_date TEXT, status TEXT);
    """)
    scoped_conn.execute("INSERT INTO buildings VALUES (?, ?, ?)", building_row)
    for row in unit_rows:
        scoped_conn.execute("INSERT INTO units VALUES (?, ?, ?, ?, ?)", row)
    for row in ticket_rows:
        scoped_conn.execute("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)", row)

    scoped_conn.commit()
    return scoped_conn