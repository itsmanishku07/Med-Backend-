from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import verify_firebase_token, get_current_user
from repositories.user_repository import UserRepository
from services.email_service import send_verification_email
from itsdangerous import URLSafeTimedSerializer
from passlib.context import CryptContext
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import base64
import hashlib
import sqlalchemy
import os
import firebase_admin.auth as firebase_auth

auth_bp = Blueprint('auth', __name__)
user_repo = UserRepository()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_serializer():
    return URLSafeTimedSerializer(os.getenv('SECRET_KEY', 'default-secret-key'))

def get_encryption_key():
    # Fernet requires a 32-byte base64 encoded key.
    # We derive it from our SECRET_KEY for consistency.
    secret = os.getenv('SECRET_KEY', 'default-secret-key')
    key = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key)

def encrypt_password(password):
    f = Fernet(get_encryption_key())
    return f.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password):
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_password.encode()).decode()


def _require_auth():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None


def _extract_token():
    header = request.headers.get('Authorization', '') or ''
    return header.replace('Bearer ', '').strip()


@auth_bp.route('/register', methods=['POST'])
def register():
    token_data = verify_firebase_token(_extract_token())
    if not token_data:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    role = data.get('role', 'PATIENT').upper()

    if not name or not email:
        return jsonify({'success': False, 'message': 'name and email are required'}), 400

    if role not in ('ADMIN', 'DOCTOR', 'PATIENT'):
        return jsonify({'success': False, 'message': 'Invalid role'}), 400

    try:
        existing = user_repo.find_by_firebase_uid(token_data['uid'])
        if existing:
            # User exists — check if the email changed and if it collides with another account
            if existing['email'].lower() != email:
                email_user = user_repo.find_by_email(email)
                if email_user and email_user['firebase_uid'] != token_data['uid']:
                     return jsonify({'success': False, 'message': 'Email already in use by another account'}), 409

            # Update existing user (e.g. upgrading PATIENT to DOCTOR)
            updates = {'role': role, 'name': name, 'email': email}
            updated = user_repo.update_user(existing['id'], updates)
            return jsonify({'success': True, 'message': 'User updated', 'user': updated}), 200

        # New Firebase UID — check email collision
        email_user = user_repo.find_by_email(email)
        if email_user:
            return jsonify({'success': False, 'message': 'Email already in use by another account'}), 409

        new_user = user_repo.create_user(
            firebase_uid=token_data['uid'],
            email=email,
            name=name,
            role=role,
        )
        return jsonify({'success': True, 'message': 'User registered', 'user': new_user}), 201
    except sqlalchemy.exc.IntegrityError as e:
        return jsonify({'success': False, 'message': 'Email already exists. Please login with your existing account.'}), 409
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@auth_bp.route('/auto-register', methods=['POST'])
def auto_register():
    token_data = verify_firebase_token(_extract_token())
    if not token_data:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    data = request.get_json() or {}
    # Allow role to be passed — defaults to PATIENT
    role = data.get('role', 'PATIENT').upper()
    if role not in ('ADMIN', 'DOCTOR', 'PATIENT'):
        role = 'PATIENT'

    email = token_data.get('email', '').lower()

    existing = user_repo.find_by_firebase_uid(token_data['uid'])
    if existing:
        # If a specific non-PATIENT role is requested and current role differs, update it
        if role != 'PATIENT' and existing.get('role') != role:
            updated = user_repo.update_user(existing['id'], {'role': role})
            return jsonify({'success': True, 'message': 'User role updated', 'user': updated})
        return jsonify({'success': True, 'message': 'User already exists', 'user': existing})

    # New UID — check for email collision before creating
    if email:
        email_user = user_repo.find_by_email(email)
        if email_user:
            return jsonify({'success': False, 'message': 'Email already in use by another account'}), 409

    try:
        new_user = user_repo.create_user(
            firebase_uid=token_data['uid'],
            email=email,
            name=data.get('name') or token_data.get('name') or email or 'User',
            role=role,
        )
        return jsonify({'success': True, 'message': 'User created', 'user': new_user})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    return jsonify({'success': True, 'user': user})


@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    user, err = _require_auth()
    if err:
        return err

    data = request.get_json() or {}
    updates = {}
    if 'name' in data:
        updates['name'] = data['name']
    if 'phone' in data:
        updates['phone'] = data['phone']
    if 'specializations' in data:
        updates['specializations'] = data['specializations']
    if 'profile_picture' in data:
        updates['profile_picture'] = data['profile_picture']
    if 'profile' in data:
        updates['profile'] = data['profile']
    # Allow role update via profile PUT (frontend doctor registration flow uses this)
    if 'role' in data:
        role = data['role'].upper()
        if role in ('DOCTOR', 'PATIENT'):   # ADMIN only via admin panel
            updates['role'] = role

    if not updates:
        # Nothing to update is fine — just return current profile
        db_user = user_repo.find_by_firebase_uid(user['uid'])
        return jsonify({'success': True, 'message': 'No changes', 'user': db_user})

    try:
        updated = user_repo.update_user(user['db_id'], updates)
        return jsonify({'success': True, 'message': 'Profile updated', 'user': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@auth_bp.route('/validate', methods=['GET'])
def validate():
    user, err = _require_auth()
    if err:
        return err
    return jsonify({'valid': True, 'uid': user['uid'], 'email': user['email'], 'role': user['role']})


@auth_bp.route('/signup/request', methods=['POST'])
def signup_request():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    name = data.get('name', '').strip()
    role = data.get('role', 'PATIENT').upper()

    if not email or not password or not name:
        return jsonify({'success': False, 'message': 'Email, password and name are required'}), 400

    if user_repo.find_by_email(email):
        return jsonify({'success': False, 'message': 'Email already registered'}), 409

    # Generate verification token
    serializer = get_serializer()
    token = serializer.dumps(email, salt='email-confirm')
    
    # Store pending registration
    expires_at = datetime.utcnow() + timedelta(hours=24)
    encrypted_password = encrypt_password(password)
    
    try:
        user_repo.create_pending_registration(
            email=email,
            password_encrypted=encrypted_password,
            name=name,
            role=role,
            token=token,
            expires_at=expires_at
        )
        
        # Send Email
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        verification_link = f"{frontend_url}/verify-email?token={token}"
        
        if send_verification_email(email, name, verification_link):
            return jsonify({'success': True, 'message': 'Verification email sent successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send verification email'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@auth_bp.route('/signup/verify', methods=['POST'])
def signup_verify():
    data = request.get_json() or {}
    token = data.get('token')
    
    if not token:
        return jsonify({'success': False, 'message': 'Token is required'}), 400

    try:
        # 1. Find pending registration by token
        pending = user_repo.find_pending_by_token(token)
        if not pending:
            return jsonify({'success': False, 'message': 'Invalid or expired verification link'}), 400
        
        if pending.expires_at < datetime.utcnow():
            user_repo.delete_pending_registration(pending.id)
            return jsonify({'success': False, 'message': 'Verification link has expired'}), 400

        # 2. Check if user already exists in local DB
        existing_local = user_repo.find_by_email(pending.email)
        
        # 3. Finalize User Creation / Synchronization
        firebase_uid = None
        try:
            # Try to create Firebase account
            password_plain = decrypt_password(pending.password_encrypted)
            try:
                firebase_user = firebase_auth.create_user(
                    email=pending.email,
                    password=password_plain,
                    display_name=pending.name
                )
                firebase_uid = firebase_user.uid
            except firebase_auth.EmailAlreadyExistsError:
                # If already exists in Firebase, just get their UID
                firebase_user = firebase_auth.get_user_by_email(pending.email)
                firebase_uid = firebase_user.uid

            if not existing_local:
                # Create local database account if missing
                try:
                    new_user = user_repo.create_user(
                        firebase_uid=firebase_uid,
                        email=pending.email,
                        name=pending.name,
                        role=pending.role.name
                    )
                except sqlalchemy.exc.IntegrityError:
                    # Race condition: another thread created the user
                    new_user = user_repo.find_by_email(pending.email)
                    if not new_user:
                        raise # Re-raise if it was some other integrity error
            else:
                # Update UID if it doesn't match
                if existing_local['firebase_uid'] != firebase_uid:
                    new_user = user_repo.update_user(existing_local['id'], {'firebase_uid': firebase_uid})
                else:
                    new_user = existing_local
            
            # Cleanup pending registration
            user_repo.delete_pending_registration(pending.id)
            
            return jsonify({
                'success': True, 
                'message': 'Email verified and account successfully activated! You can now log in.',
                'user': new_user
            })
            
        except Exception as fe:
            # If we encountered an error but the user actually exists, we should probably still clean up
            # but for now, let's return the error. 
            # Note: We handled EmailAlreadyExistsError above, so this is for other issues.
            return jsonify({'success': False, 'message': f"Account activation failed: {str(fe)}"}), 500

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
