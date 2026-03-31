import os
import firebase_admin
from firebase_admin import credentials
from dotenv import load_dotenv

load_dotenv()


def init_firebase():
    """Initialize Firebase Admin SDK exactly once."""
    if firebase_admin._apps:
        return

    project_id = os.getenv('FIREBASE_PROJECT_ID', '')
    private_key_id = os.getenv('FIREBASE_PRIVATE_KEY_ID', '')
    private_key = os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
    client_email = os.getenv('FIREBASE_CLIENT_EMAIL', '')
    client_id = os.getenv('FIREBASE_CLIENT_ID', '')

    if project_id and private_key and client_email:
        cred_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": private_key_id,
            "private_key": private_key,
            "client_email": client_email,
            "client_id": client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    else:
        # Initialize with no credentials (dev/test mode — token verification will fail gracefully)
        firebase_admin.initialize_app()
