#!/usr/bin/env python3
"""
Migration script to add TeamRestaurant table and migrate existing Restaurant cache data.

This migration:
1. Creates the team_restaurants table
2. Removes cache-related columns from restaurants table (they're now in team_restaurants)
3. Note: Existing cache data will be lost as we don't have team context for old restaurants
"""

import sqlite3
from pathlib import Path
import sys


def migrate_add_team_restaurants(db_path: str):
    """Add TeamRestaurant table and remove cache fields from Restaurant table."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting migration: Add TeamRestaurant table...")
        
        # Check if team_restaurants table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_restaurants'")
        if cursor.fetchone():
            print("✓ team_restaurants table already exists. No migration needed.")
            return True
        
        # 1. Create team_restaurants table
        print("Creating team_restaurants table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_restaurants (
                id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                restaurant_id TEXT NOT NULL,
                display_name TEXT,
                cache_strategy TEXT NOT NULL DEFAULT 'auto',
                cache_duration_hours INTEGER,
                next_scrape_at TIMESTAMP,
                last_scraped_at TIMESTAMP,
                is_active INTEGER NOT NULL DEFAULT 1,
                added_by_user_id TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY (team_id) REFERENCES teams(id),
                FOREIGN KEY (restaurant_id) REFERENCES restaurants(id),
                FOREIGN KEY (added_by_user_id) REFERENCES users(id)
            )
        """)
        
        # 2. Create indexes
        print("Creating indexes on team_restaurants...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_team_restaurants_team_id 
            ON team_restaurants(team_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_team_restaurants_restaurant_id 
            ON team_restaurants(restaurant_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_team_restaurants_added_by_user_id 
            ON team_restaurants(added_by_user_id)
        """)
        
        # 3. Create unique constraint on team_id + restaurant_id
        print("Creating unique constraint on team_id + restaurant_id...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_team_restaurants_team_restaurant 
            ON team_restaurants(team_id, restaurant_id)
        """)
        
        # 4. Check if restaurants table has cache columns
        cursor.execute("PRAGMA table_info(restaurants)")
        columns = [row[1] for row in cursor.fetchall()]
        
        has_cache_columns = any(col in columns for col in ['cache_strategy', 'cache_duration_hours', 'next_scrape_at', 'last_scraped_at'])
        
        if has_cache_columns:
            # Remove cache columns from restaurants table
            # SQLite doesn't support DROP COLUMN, so we need to recreate the table
            print("Recreating restaurants table without cache columns...")
            
            # Create new restaurants table
            cursor.execute("""
                CREATE TABLE restaurants_new (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    display_name TEXT,
                    meta TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            
            # Copy data from old table (excluding cache columns)
            cursor.execute("""
                INSERT INTO restaurants_new (id, url, display_name, meta, created_at, updated_at)
                SELECT id, url, display_name, meta, created_at, updated_at
                FROM restaurants
            """)
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE restaurants")
            cursor.execute("ALTER TABLE restaurants_new RENAME TO restaurants")
            
            # Recreate indexes
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ix_restaurants_url 
                ON restaurants(url)
            """)
            print("✓ Removed cache columns from restaurants table")
        else:
            print("✓ Restaurants table already has correct schema")
        
        conn.commit()
        print("✓ Migration completed successfully!")
        print("\nNOTE: Existing cache data has been removed.")
        print("Teams will need to re-add their restaurant sources.")
        return True


    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path
    db_path = Path(__file__).parent.parent.parent / "data" / "dynalunch.db"
    
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    
    if not db_path.exists():
        print(f"✗ Database not found at: {db_path}")
        print("  Creating new database with create_db_and_tables() instead.")
        sys.exit(1)
    
    print(f"Migrating database: {db_path}")
    success = migrate_add_team_restaurants(str(db_path))
    sys.exit(0 if success else 1)
