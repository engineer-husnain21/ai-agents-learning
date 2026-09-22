"""
tamam_sql_pipeline.py — generates and runs SQL against an ALREADY
TENANT-SCOPED connection (see tamam_isolation.py). Even though the
data is structurally isolated before this file ever runs, this module
still validates the query is read-only as defense in depth — the same
two-layer pattern as task 15 (code validation + connection can't write),
because a security guarantee should never depend on only one layer
holding.
"""

from app.rewriting_lc import chat_model

FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "ATTACH", "PRAGMA"]

TENANT_SCHEMA = """
Tables (already scoped to only THIS ONE tenant's own data - there is no
other tenant's data in this database, only this one person's rows):
  buildings(building_id, building_name, area)
  units(unit_id, building_id, unit_number, bedrooms, monthly_rent)
  tenants(tenant_id, full_name, unit_id, lease_start, lease_end)
  tickets(ticket_id, unit_id, category, opened_date, closed_date, status)
  payments(payment_id, tenant_id, due_date, paid_date, amount)

IMPORTANT: this database contains ONLY the current tenant's own record.
You cannot see any other tenant, so NEVER claim a comparison across
tenants (e.g. "you pay the highest rent," "you're the only one with
this issue") - you have no visibility into anyone else's data to
support that claim. If asked to compare against other tenants, answer
only with the tenant's own value and say you don't have visibility
into other tenants' information to compare.

Exact tickets.status values: 'Open', 'Closed' (case-sensitive, capitalized)
Exact tickets.category values: 'Electrical', 'AC', 'Appliance', 'Plumbing', 'Pest Control', 'Common Area'
  (there is no generic "maintenance" category - "maintenance" in a question usually means ANY of these categories, i.e. all open tickets regardless of category, unless the tenant names a specific one)

Notes:
  - tickets.status is 'Open' or 'Closed'.
  - payments.paid_date is NULL if unpaid. Late = paid_date is NULL AND due_date has passed, or paid_date > due_date + 5 days (grace period per handbook).
"""

BUILDING_SCHEMA = """
Tables (scoped to one building's aggregate data only - no individual
tenant names or payment amounts are present):
  buildings(building_id, building_name, area)
  units(unit_id, building_id, unit_number, bedrooms, monthly_rent)
  tickets(ticket_id, unit_id, category, opened_date, closed_date, status)

Exact tickets.status values: 'Open', 'Closed' (case-sensitive, capitalized)
Exact tickets.category values: 'Electrical', 'AC', 'Appliance', 'Plumbing', 'Pest Control', 'Common Area'
  (there is no generic "maintenance" category - "maintenance" in a question means ANY of these categories, i.e. count tickets across all categories, unless a specific one is named)
"""

MAX_REPAIR_ATTEMPTS = 2

GENERATE_PROMPT = """You write ONE SQLite SELECT query to answer the question below, using only this schema:
{schema}

Rules:
- Only a single SELECT statement. No explanations, no markdown, just raw SQL.
- If your query uses an aggregate function (SUM, AVG, COUNT, MAX, MIN) filtered by a condition, ALSO include a separate COUNT(*) column named matched_rows counting how many raw rows matched that same filter.

Question: {question}

SQL query:"""

REPAIR_PROMPT = """Your previous SQL query failed with this error:
{error}

Original query:
{query}

Question: {question}

Schema:
{schema}

Write a corrected SQLite SELECT query. SQL query:"""


def validate_query_is_read_only(query):
    stripped = query.strip().upper()
    if not stripped.startswith("SELECT"):
        return False, "Query does not start with SELECT."
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in stripped:
            return False, f"Query contains forbidden keyword: {keyword}"
    return True, None


def generate_and_run_sql(question, scoped_conn, schema):
    """
    scoped_conn: an already-isolated sqlite3.Connection (from
    tamam_isolation.py) — never the raw main database.
    """
    total_input_tokens = 0
    total_output_tokens = 0

    prompt = GENERATE_PROMPT.format(schema=schema, question=question)
    response = chat_model.invoke(prompt)
    query = response.content.strip().strip("`")
    if query.lower().startswith("sql"):
        query = query[3:].strip()
    total_input_tokens += response.usage_metadata["input_tokens"]
    total_output_tokens += response.usage_metadata["output_tokens"]

    attempts = 1
    last_error = None

    while attempts <= MAX_REPAIR_ATTEMPTS + 1:
        is_valid, reason = validate_query_is_read_only(query)
        if not is_valid:
            return {
                "query": query, "columns": [], "rows": [], "attempts": attempts,
                "input_tokens": total_input_tokens, "output_tokens": total_output_tokens,
                "no_data": False, "error": f"Blocked by safety check: {reason}"
            }
        try:
            cursor = scoped_conn.execute(query)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchall()

            no_data = False
            if "matched_rows" in columns:
                idx = columns.index("matched_rows")
                if rows and rows[0][idx] == 0:
                    no_data = True

            return {
                "query": query, "columns": columns, "rows": rows, "attempts": attempts,
                "input_tokens": total_input_tokens, "output_tokens": total_output_tokens,
                "no_data": no_data, "error": None
            }
        except Exception as e:
            last_error = str(e)
            if attempts > MAX_REPAIR_ATTEMPTS:
                break
            repair_prompt = REPAIR_PROMPT.format(error=last_error, query=query, question=question, schema=schema)
            repair_response = chat_model.invoke(repair_prompt)
            query = repair_response.content.strip().strip("`")
            total_input_tokens += repair_response.usage_metadata["input_tokens"]
            total_output_tokens += repair_response.usage_metadata["output_tokens"]
            attempts += 1

    return {
        "query": query, "columns": [], "rows": [], "attempts": attempts,
        "input_tokens": total_input_tokens, "output_tokens": total_output_tokens,
        "no_data": False, "error": f"Query failed after {attempts} attempts: {last_error}"
    }