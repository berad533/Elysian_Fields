"""
Database Migration Script
Adds latitude and longitude fields to Cemetery table
"""

import sqlite3
import os

def migrate_database():
    """Add latitude and longitude fields to Cemetery table"""
    db_path = "backend/elysian_fields.db"
    
    # Check if we're in the right directory
    if not os.path.exists(db_path):
        # Try from backend directory
        db_path = "elysian_fields.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found. Please run the backend first to create the database.")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(cemetery)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'latitude' not in columns:
            print("Adding latitude column to cemetery table...")
            cursor.execute("ALTER TABLE cemetery ADD COLUMN latitude REAL")
            print("✅ Added latitude column")
        else:
            print("✅ Latitude column already exists")
        
        if 'longitude' not in columns:
            print("Adding longitude column to cemetery table...")
            cursor.execute("ALTER TABLE cemetery ADD COLUMN longitude REAL")
            print("✅ Added longitude column")
        else:
            print("✅ Longitude column already exists")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("✅ Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    migrate_database()
