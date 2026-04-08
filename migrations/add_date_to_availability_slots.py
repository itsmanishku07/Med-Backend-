"""
Migration script to add 'date' column to doctor_availability_slots table
Run this script to update your existing database schema
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from config.database import engine

def run_migration():
    """Add date column to doctor_availability_slots table"""
    
    migration_sql = """
    -- Add date column (nullable for backward compatibility)
    ALTER TABLE doctor_availability_slots 
    ADD COLUMN IF NOT EXISTS date TIMESTAMP;
    
    -- Add index on date column for better query performance
    CREATE INDEX IF NOT EXISTS idx_doctor_availability_slots_date 
    ON doctor_availability_slots(date);
    
    -- Make day_of_week nullable (since date-specific slots may not need it)
    ALTER TABLE doctor_availability_slots 
    ALTER COLUMN day_of_week DROP NOT NULL;
    """
    
    try:
        with engine.connect() as conn:
            # Execute migration
            conn.execute(text(migration_sql))
            conn.commit()
            print("✅ Migration completed successfully!")
            print("   - Added 'date' column to doctor_availability_slots")
            print("   - Added index on 'date' column")
            print("   - Made 'day_of_week' column nullable")
            
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        raise

if __name__ == "__main__":
    print("Running migration: Add date column to doctor_availability_slots")
    print("-" * 60)
    run_migration()
    print("-" * 60)
    print("Migration complete!")
