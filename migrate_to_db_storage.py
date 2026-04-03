import os
import sqlite3
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load database URL
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

def migrate():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in .env")
        return

    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # 1. Add file_content column if it doesn't exist
        print("Checking for file_content column...")
        try:
            # For PostgreSQL / SQLite compatible check
            # We'll just try to add it and catch the error if it exists
            # Or better, check column names
            if "postgresql" in DATABASE_URL:
                check_query = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='medical_reports' AND column_name='file_content';
                """)
                result = conn.execute(check_query).fetchone()
                if not result:
                    print("Adding column 'file_content' to 'medical_reports' table...")
                    conn.execute(text("ALTER TABLE medical_reports ADD COLUMN file_content BYTEA;"))
                    conn.commit()
                else:
                    print("Column 'file_content' already exists.")
            else:
                # Fallback for SQLite (if user is using it for local dev)
                try:
                    conn.execute(text("ALTER TABLE medical_reports ADD COLUMN file_content BLOB;"))
                    conn.commit()
                    print("Added column 'file_content' (BLOB).")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        print("Column 'file_content' already exists.")
                    else:
                        raise e

        except Exception as e:
            print(f"Error checking/adding column: {e}")
            return

        # 2. Migrate existing files to DB
        print("\nChecking for existing files to migrate...")
        select_query = text("SELECT id, file_path, file_name FROM medical_reports WHERE file_content IS NULL;")
        reports = conn.execute(select_query).fetchall()

        if not reports:
            print("No reports found needing migration.")
            return

        print(f"Found {len(reports)} reports to migrate.")
        count = 0
        for report_id, file_path, file_name in reports:
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    update_query = text("UPDATE medical_reports SET file_content = :content WHERE id = :id")
                    conn.execute(update_query, {"content": content, "id": report_id})
                    conn.commit()
                    count += 1
                    print(f"Migrated report {report_id} ({file_name})")
                except Exception as e:
                    print(f"Failed to migrate report {report_id}: {e}")
            else:
                print(f"Skip report {report_id}: File not found at {file_path}")

        print(f"\nMigration complete. {count} files imported into database.")

if __name__ == "__main__":
    migrate()
