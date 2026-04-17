#!/usr/bin/env python3
"""
Migration script to add cache-related fields to Restaurant table.
Run this once to update existing databases.
"""

import sqlite3
from pathlib import Path
import sys

def migrate_add_cache_fields(db_path: str):
    """Add cache_strategy, cache_duration_hours, and next_scrape_at to restaurants table."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(restaurants)")
        columns = [row[1] for row in cursor.fetchall()]
        
        migrations_needed = []
        
        if 'cache_strategy' not in columns:
            migrations_needed.append(
                "ALTER TABLE restaurants ADD COLUMN cache_strategy VARCHAR NOT NULL DEFAULT 'auto'"
            )
        
        if 'cache_duration_hours' not in columns:
            migrations_needed.append(
                "ALTER TABLE restaurants ADD COLUMN cache_duration_hours INTEGER"
            )
        
        if 'next_scrape_at' not in columns:
            migrations_needed.append(
                "ALTER TABLE restaurants ADD COLUMN next_scrape_at DATETIME"
            )
        
        if not migrations_needed:
            print("✓ All cache fields already exist. No migration needed.")
            return True
        
        # Apply migrations
        print(f"Applying {len(migrations_needed)} migration(s)...")
        for sql in migrations_needed:
            print(f"  Executing: {sql}")
            cursor.execute(sql)
        
        conn.commit()
        print("✓ Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path
    db_path = Path(__file__).parent.parent.parent.parent / "dynalunch.db"
    
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    
    if not db_path.exists():
        print(f"✗ Database not found at: {db_path}")
        print("  Creating new database with create_db_and_tables() instead.")
        sys.exit(1)
    
    print(f"Migrating database: {db_path}")
    success = migrate_add_cache_fields(str(db_path))
    sys.exit(0 if success else 1)
