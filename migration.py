"""
FinTracker — one-shot SQLite migration script.

Safely adds:
  • New TABLES: income, savings_goal
  • Defensive ALTER TABLE for any column the running models.py expects
    that an older DB might be missing (user.currency, user.theme, expense.*)

Usage:
    python migration.py

It is idempotent — re-running on an already-migrated DB is a no-op.
"""

import os
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Resolve the DB path the same way the Flask app does:
#   SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
# Flask resolves this to instance/database.db by default.
# We check both common locations.
# ---------------------------------------------------------------------------
CANDIDATES = [
    os.path.join('instance', 'database.db'),
    'database.db',
]


def find_db():
    for p in CANDIDATES:
        if os.path.exists(p):
            return p
    # Default — let the user know we'll create it via Flask if missing.
    return None


def column_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())


def table_exists(cur, table):
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cur.fetchone() is not None


def add_column_if_missing(cur, table, col, ddl):
    if not table_exists(cur, table):
        print(f"  · skipping {table}.{col} — table not yet created")
        return
    if column_exists(cur, table, col):
        print(f"  ✓ {table}.{col} already exists")
        return
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
    print(f"  + added {table}.{col}")


def create_table(cur, name, ddl):
    if table_exists(cur, name):
        print(f"  ✓ table {name} already exists")
        return
    cur.execute(ddl)
    print(f"  + created table {name}")


def main():
    db_path = find_db()
    if not db_path:
        print("✗ database.db not found in `instance/` or project root.")
        print("  Start the Flask app once first (so db.create_all() runs),")
        print("  then re-run this migration.")
        sys.exit(1)

    print(f"→ Migrating {db_path}")
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # ------------------------------------------------------------------
    # Defensive ALTERs — columns added in earlier feature rounds.
    # Each is a no-op if the column already exists.
    # ------------------------------------------------------------------
    print("\n[1/2] Existing tables — safety ALTERs")

    add_column_if_missing(cur, 'user', 'currency',
        "currency VARCHAR(10) DEFAULT '$'")
    add_column_if_missing(cur, 'user', 'theme',
        "theme VARCHAR(10) DEFAULT 'light'")

    add_column_if_missing(cur, 'expense', 'receipt',
        "receipt VARCHAR(300)")
    add_column_if_missing(cur, 'expense', 'upi_ref',
        "upi_ref VARCHAR(100)")
    add_column_if_missing(cur, 'expense', 'is_recurring',
        "is_recurring BOOLEAN DEFAULT 0")
    add_column_if_missing(cur, 'expense', 'notes',
        "notes VARCHAR(300)")

    # ------------------------------------------------------------------
    # New tables for income tracking + savings goals.
    # ------------------------------------------------------------------
    print("\n[2/2] New tables")

    create_table(cur, 'income', """
        CREATE TABLE income (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     VARCHAR(100) NOT NULL,
            user_id   INTEGER NOT NULL,
            amount    FLOAT NOT NULL,
            date      VARCHAR(20) NOT NULL,
            category  VARCHAR(100),
            notes     VARCHAR(300),
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
    """)

    create_table(cur, 'savings_goal', """
        CREATE TABLE savings_goal (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           VARCHAR(100) NOT NULL,
            target_amount  FLOAT NOT NULL,
            saved_amount   FLOAT DEFAULT 0,
            user_id        INTEGER NOT NULL,
            deadline       VARCHAR(20),
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
    """)

    conn.commit()
    conn.close()
    print("\n✓ Migration complete.")


if __name__ == '__main__':
    main()
