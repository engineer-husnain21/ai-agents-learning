"""
tamam_isolation_check.py — deterministic proof of the isolation guarantee.

No AI involved. For EVERY tenant in tamam.db, build the same scoped database
the /ask endpoint uses, then run the worst queries a model could generate
(no WHERE clause at all) and check that nothing belonging to anyone else
comes back.

Usage:  python tamam_isolation_check.py
Writes: evidence/isolation_check.json
"""

import json
import os
import sqlite3
from datetime import datetime

from app.tamam_isolation import build_tenant_scoped_db, MAIN_DB_PATH

HOSTILE_QUERIES = {
    "all_tenants": "SELECT tenant_id, full_name FROM tenants",
    "all_units": "SELECT unit_id, monthly_rent FROM units",
    "all_payments": "SELECT DISTINCT tenant_id FROM payments",
    "all_tickets": "SELECT DISTINCT unit_id FROM tickets",
    "all_buildings": "SELECT building_id FROM buildings",
}


def main():
    main_conn = sqlite3.connect(f"file:{MAIN_DB_PATH}?mode=ro", uri=True)
    tenants = main_conn.execute(
        "SELECT t.tenant_id, t.unit_id, u.building_id FROM tenants t JOIN units u USING(unit_id)"
    ).fetchall()
    main_conn.close()

    failures = []
    for tenant_id, unit_id, building_id in tenants:
        conn = build_tenant_scoped_db(tenant_id)
        rows = {name: conn.execute(q).fetchall() for name, q in HOSTILE_QUERIES.items()}
        conn.close()

        checks = {
            "only own tenant row": rows["all_tenants"] and all(r[0] == tenant_id for r in rows["all_tenants"]) and len(rows["all_tenants"]) == 1,
            "only own unit": [r[0] for r in rows["all_units"]] == [unit_id],
            "only own payments": all(r[0] == tenant_id for r in rows["all_payments"]),
            "only own unit's tickets": all(r[0] == unit_id for r in rows["all_tickets"]),
            "only own building": [r[0] for r in rows["all_buildings"]] == [building_id],
        }
        for name, ok in checks.items():
            if not ok:
                failures.append({"tenant_id": tenant_id, "check": name})

    result = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "tenants_checked": len(tenants),
        "queries_per_tenant": len(HOSTILE_QUERIES),
        "hostile_queries": HOSTILE_QUERIES,
        "failures": failures,
        "passed": not failures,
    }
    os.makedirs("evidence", exist_ok=True)
    with open(os.path.join("evidence", "isolation_check.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    status = "PASS" if result["passed"] else "FAIL"
    print(f"[{status}] {len(tenants)} tenants x {len(HOSTILE_QUERIES)} unfiltered queries - "
          f"{len(failures)} leak(s). Saved evidence/isolation_check.json")
    if failures:
        for f_ in failures:
            print("  LEAK:", f_)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
