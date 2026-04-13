"""
Migration: Add is_private column to medical_reports table
Run with: python migrations/add_private_report.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from config.database import engine


def run_migration():
    sql = """
    ALTER TABLE medical_reports
    ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE;
    """
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
        print("[SUCCESS] Migration complete: added is_private to medical_reports")


if __name__ == "__main__":
    print("Running migration: Add is_private to medical_reports")
    print("-" * 60)
    run_migration()
    print("-" * 60)
