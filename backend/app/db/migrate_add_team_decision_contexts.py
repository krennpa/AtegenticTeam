#!/usr/bin/env python3
"""
Migration script to add the team_decision_contexts table.
"""

import sqlite3
from pathlib import Path
import sys


def migrate_add_team_decision_contexts(db_path: str) -> bool:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Starting migration: add team_decision_contexts table...")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='team_decision_contexts'"
        )
        if not cursor.fetchone():
            print("Creating team_decision_contexts table...")
            cursor.execute(
                """
                CREATE TABLE team_decision_contexts (
                    id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL UNIQUE,
                    schema_version TEXT NOT NULL DEFAULT 'v1',
                    context_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (team_id) REFERENCES teams(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_team_decision_contexts_team_id
                ON team_decision_contexts(team_id)
                """
            )
            print("[OK] team_decision_contexts table created")
        else:
            print("[OK] team_decision_contexts table already exists")

        conn.commit()
        print("[OK] Migration completed successfully")
        return True
    except Exception as exc:
        print(f"[ERROR] Migration failed: {exc}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = Path(__file__).parent.parent.parent / "data" / "umamimatch.db"

    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])

    if not db_path.exists():
        print(f"[ERROR] Database not found at: {db_path}")
        print("  Creating new database with create_db_and_tables() instead.")
        sys.exit(1)

    print(f"Migrating database: {db_path}")
    success = migrate_add_team_decision_contexts(str(db_path))
    sys.exit(0 if success else 1)

