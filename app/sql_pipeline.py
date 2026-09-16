"""
sql_pipeline.py — Task 15: generates a SQL query from a natural-language
question, verifies it can only READ (never write), executes it against
a read-only connection, and distinguishes "no data exists" from a
genuine measured zero on aggregate queries.

Two independent safety layers, per plan:
  1. Code-level validation: query must start with SELECT, must not
     contain any write/DDL keyword. This is a filter — it can be
     talked around by a cleverly-worded query in theory.
  2. Read-only database connection (SQLite mode=ro URI): this is the
     layer that actually can't be bypassed — even if a write-shaped
     query somehow got past layer 1, the connection itself refuses to
     execute any write at the database engine level.
Both are tested, not just asserted (see eval_set.json's destructive
query test case).
"""

import sqlite3
from app.rewriting_lc import chat_model

DB_PATH = "noor_market.db"

SCHEMA = """
Tables:
  stores(store_id INTEGER, store_name TEXT)
  products(product_id INTEGER, product_name TEXT, category TEXT, unit_price REAL)
  sales(sale_id INTEGER, sale_date TEXT (format YYYY-MM-DD), store_id INTEGER, product_id INTEGER, quantity INTEGER)

Notes:
  - sales.quantity is units sold, not revenue. Revenue = quantity * unit_price (join products).
  - All sale_date values are in July 2026 (2026-07-01 to 2026-07-28). There is NO data for any other month or year.
"""

FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "ATTACH", "PRAGMA"]

GENERATE_PROMPT = """You write ONE SQLite SELECT query to answer the question below, using only this schema:
{schema}

Rules:
- Only a single SELECT statement. No explanations, no markdown, just the raw SQL.
- If your query uses an aggregate function (SUM, AVG, COUNT, MAX, MIN) filtered by a condition (like a date range), ALSO include a separate COUNT(*) column named matched_rows in the SELECT, counting how many raw sales rows matched that same filter. This lets the caller tell "no matching data" apart from a genuine zero/null aggregate.

Question: {question}

SQL query:"""

REPAIR_PROMPT = """Your previous SQL query failed with this error:
{error}

Original query:
{query}

Question: {question}

Schema:
{schema}

Write a corrected SQLite SELECT query (same rules: single SELECT, include matched_rows alongside any filtered aggregate). SQL query:"""

MAX_REPAIR_ATTEMPTS = 2


def validate_query_is_read_only(query):
    """Layer 1: code-level check, not the model's word for it."""
    stripped = query.strip().upper()
    if not stripped.startswith("SELECT"):
        return False, "Query does not start with SELECT."
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in stripped:
            return False, f"Query contains forbidden keyword: {keyword}"
    return True, None


def execute_readonly(query):
    """Layer 2: the connection itself is opened read-only. Even if a
    write-shaped query somehow passed layer 1, SQLite's engine refuses
    to execute a write against a mode=ro connection."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cursor = conn.execute(query)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows
    finally:
        conn.close()


def generate_and_run_sql(question):
    """
    Returns a dict: {
        "query": final SQL that ran (or last attempted),
        "columns": [...], "rows": [...],
        "attempts": int,
        "input_tokens": int, "output_tokens": int,
        "no_data": bool,   # True if an aggregate's matched_rows was 0
        "error": str or None
    }
    """
    total_input_tokens = 0
    total_output_tokens = 0

    prompt = GENERATE_PROMPT.format(schema=SCHEMA, question=question)
    response = chat_model.invoke(prompt)
    query = response.content.strip().strip("`").replace("sql\n", "", 1) if response.content.strip().startswith("```") else response.content.strip()
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
            columns, rows = execute_readonly(query)

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
        except sqlite3.Error as e:
            last_error = str(e)
            if attempts > MAX_REPAIR_ATTEMPTS:
                break
            repair_prompt = REPAIR_PROMPT.format(error=last_error, query=query, question=question, schema=SCHEMA)
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