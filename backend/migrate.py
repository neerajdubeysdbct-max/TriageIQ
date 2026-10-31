"""
Bring a database up to date: create the tables from models.py, then apply every
SQL file in migrations/ in name order. All migrations are idempotent
(IF NOT EXISTS), so this is safe to run on every start.

    python migrate.py
"""

import glob
import os

from sqlalchemy import text

from models import engine  # importing models creates missing tables

MIGRATIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")


def main():
    files = sorted(glob.glob(os.path.join(MIGRATIONS, "*.sql")))
    with engine.begin() as conn:
        for path in files:
            with open(path, encoding="utf-8") as f:
                conn.execute(text(f.read()))
            print(f"applied {os.path.basename(path)}")
    print(f"database up to date ({len(files)} migrations)")


if __name__ == "__main__":
    main()
