from flask import request
import firebase_admin.auth


def verify_firebase_token(token: str) -> dict | None:
    """Verify Firebase ID token. Returns {uid, email, name} or None on any error."""
    try:
        decoded = firebase_admin.auth.verify_id_token(token)
        return {
            'uid': decoded.get('uid'),
            'email': decoded.get('email', ''),
            'name': decoded.get('name', decoded.get('email', ''))
        }
    except Exception:
        return None


def get_current_user() -> dict | None:
    """
    Extract Bearer token, verify it, look up user in PostgreSQL.
    Auto-creates as PATIENT if token is valid but user not in DB yet.
    Attaches role from DB. Returns None only if token is invalid/missing.
    """
    from repositories.user_repository import UserRepository

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ', 1)[1].strip()
    if not token:
        return None

    token_data = verify_firebase_token(token)
    if not token_data:
        return None

    repo = UserRepository()
    db_user = repo.find_by_firebase_uid(token_data['uid'])

    if not db_user:
        # Auto-create as PATIENT if token is valid but user not in DB yet
        db_user = repo.create_user(
            firebase_uid=token_data['uid'],
            email=token_data.get('email', ''),
            name=token_data.get('name', 'New Account')
        )

    token_data['role'] = db_user.get('role', 'PATIENT')
    token_data['db_id'] = db_user.get('id')
    token_data['name'] = db_user.get('name', token_data.get('name', ''))
    token_data['email'] = db_user.get('email', token_data.get('email', ''))
    return token_data
