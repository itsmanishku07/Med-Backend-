from flask import Blueprint, request, jsonify
from utils.auth_utils import verify_firebase_token, get_current_user
from repositories.user_repository import UserRepository

auth_bp = Blueprint('auth', __name__)
user_repo = UserRepository()


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
    email = data.get('email', '').strip()
    role = data.get('role', 'PATIENT').upper()

    if not name or not email:
        return jsonify({'success': False, 'message': 'name and email are required'}), 400

    if role not in ('ADMIN', 'DOCTOR', 'PATIENT'):
        return jsonify({'success': False, 'message': 'Invalid role'}), 400

    try:
        existing = user_repo.find_by_firebase_uid(token_data['uid'])
        if existing:
            # User exists — update their role and name so doctor registration works
            # even if they were previously auto-created as PATIENT
            updates = {'role': role, 'name': name}
            updated = user_repo.update_user(existing['id'], updates)
            return jsonify({'success': True, 'message': 'User updated', 'user': updated}), 200

        # Check email collision from a different firebase account
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

    existing = user_repo.find_by_firebase_uid(token_data['uid'])
    if existing:
        # If a specific non-PATIENT role is requested and current role differs, update it
        if role != 'PATIENT' and existing.get('role') != role:
            updated = user_repo.update_user(existing['id'], {'role': role})
            return jsonify({'success': True, 'message': 'User role updated', 'user': updated})
        return jsonify({'success': True, 'message': 'User already exists', 'user': existing})

    try:
        new_user = user_repo.create_user(
            firebase_uid=token_data['uid'],
            email=token_data.get('email', ''),
            name=data.get('name') or token_data.get('name') or token_data.get('email', 'User'),
            role=role,
        )
        return jsonify({'success': True, 'message': 'User created', 'user': new_user})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    token_data = verify_firebase_token(_extract_token())
    if not token_data:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    db_user = user_repo.find_by_firebase_uid(token_data['uid'])
    if not db_user:
        try:
            db_user = user_repo.create_user(
                firebase_uid=token_data['uid'],
                email=token_data.get('email', ''),
                name=token_data.get('name') or token_data.get('email', 'User'),
                role='PATIENT',
            )
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    return jsonify({'success': True, 'user': db_user})


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
