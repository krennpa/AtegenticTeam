#!/usr/bin/env python3
"""
Migration script to add team preference and profile preference event tables.
"""

import sqlite3
from pathlib import Path
import sys


def migrate_add_profile_team_preferences(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Starting migration: add profile/team preference tables...")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='team_preferences'"
        )
        if not cursor.fetchone():
            print("Creating team_preferences table...")
            cursor.execute(
                """
                CREATE TABLE team_preferences (
                    id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL UNIQUE,
                    budget_preference TEXT NOT NULL DEFAULT 'medium',
                    allergies TEXT NOT NULL DEFAULT '[]',
                    dietary_restrictions TEXT NOT NULL DEFAULT '[]',
                    other_preferences TEXT NOT NULL DEFAULT '{}',
                    member_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (team_id) REFERENCES teams(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_team_preferences_team_id
                ON team_preferences(team_id)
                """
            )
            print("[OK] team_preferences table created")
        else:
            print("[OK] team_preferences table already exists")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='profile_preference_events'"
        )
        if not cursor.fetchone():
            print("Creating profile_preference_events table...")
            cursor.execute(
                """
                CREATE TABLE profile_preference_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    team_id TEXT,
                    event_type TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    answer TEXT,
                    weight REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL DEFAULT 'user_gameplay',
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (team_id) REFERENCES teams(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_profile_preference_events_user_id
                ON profile_preference_events(user_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_profile_preference_events_team_id
                ON profile_preference_events(team_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_profile_preference_events_event_type
                ON profile_preference_events(event_type)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_profile_preference_events_question_key
                ON profile_preference_events(question_key)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_profile_preference_events_source
                ON profile_preference_events(source)
                """
            )
            print("[OK] profile_preference_events table created")
        else:
            print("[OK] profile_preference_events table already exists")

        conn.commit()
        print("[OK] Migration completed successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
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
    success = migrate_add_profile_team_preferences(str(db_path))
    sys.exit(0 if success else 1)
