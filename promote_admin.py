import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.db_models import User, UserRole

def promote_user(email):
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL not found in .env file")
        return

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        user = session.query(User).filter(User.email == email.lower()).first()
        
        if not user:
            print(f"Error: No user found with email '{email}'")
            print("Make sure you have signed up in the app first!")
            return

        user.role = UserRole.ADMIN
        session.commit()
        
        print(f"Success! User '{user.name}' ({email}) has been promoted to ADMIN.")
        print("Please log out and log back in on the website to see the Admin Dashboard.")
        
    except Exception as e:
        session.rollback()
        print(f"Error occurred: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python promote_admin.py your_email@example.com")
    else:
        email_to_promote = sys.argv[1]
        promote_user(email_to_promote)
