from flask import Blueprint, request, jsonify
from utils.auth_utils import get_current_user
from repositories.user_repository import UserRepository
from repositories.medical_report_repository import MedicalReportRepository
from repositories.chat_repository import ChatRepository

admin_bp = Blueprint('admin', __name__)
user_repo = UserRepository()
report_repo = MedicalReportRepository()
chat_repo = ChatRepository()


def _require_admin():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    if user.get('role') != 'ADMIN':
        return None, (jsonify({'success': False, 'message': 'Admin access required'}), 403)
    return user, None


@admin_bp.route('/dashboard', methods=['GET'])
def dashboard():
    _, err = _require_admin()
    if err:
        return err

    try:
        all_users = user_repo.get_all_users()
        all_reports = report_repo.get_all_reports()

        total_users = len(all_users)
        total_doctors = sum(1 for u in all_users if u.get('role') == 'DOCTOR')
        total_patients = sum(1 for u in all_users if u.get('role') == 'PATIENT')
        total_reports = len(all_reports)
        pending_reports = sum(1 for r in all_reports if r.get('status') in ('PENDING', 'ANALYZING'))
        analyzed_reports = sum(1 for r in all_reports if r.get('status') == 'ANALYZED')
        critical_cases = sum(1 for r in all_reports
                             if r.get('ai_analysis') and
                             r['ai_analysis'].get('severity_level') == 'CRITICAL')

        from config.database import SessionLocal
        from models.db_models import Chat
        with SessionLocal() as session:
            active_chats = session.query(Chat).count()

        return jsonify({'success': True, 'stats': {
            'totalUsers': total_users,
            'totalDoctors': total_doctors,
            'totalPatients': total_patients,
            'totalReports': total_reports,
            'pendingReports': pending_reports,
            'analyzedReports': analyzed_reports,
            'criticalCases': critical_cases,
            'activeChats': active_chats,
        }})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/users', methods=['GET'])
def get_users():
    _, err = _require_admin()
    if err:
        return err

    users = user_repo.get_all_users()
    return jsonify({'success': True, 'users': users})


@admin_bp.route('/users/<firebase_uid>/role', methods=['PUT'])
def update_user_role(firebase_uid):
    _, err = _require_admin()
    if err:
        return err

    data = request.get_json() or {}
    role = data.get('role', '').upper()
    if role not in ('ADMIN', 'DOCTOR', 'PATIENT'):
        return jsonify({'success': False, 'message': 'Invalid role'}), 400

    db_user = user_repo.find_by_firebase_uid(firebase_uid)
    if not db_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    try:
        updated = user_repo.update_user(db_user['id'], {'role': role})
        return jsonify({'success': True, 'message': 'Role updated', 'user': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/users/<firebase_uid>/status', methods=['PUT'])
def update_user_status(firebase_uid):
    _, err = _require_admin()
    if err:
        return err

    data = request.get_json() or {}
    active = data.get('active')
    if active is None:
        return jsonify({'success': False, 'message': 'active field is required'}), 400

    db_user = user_repo.find_by_firebase_uid(firebase_uid)
    if not db_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    try:
        updated = user_repo.update_user(db_user['id'], {'is_active': bool(active)})
        return jsonify({'success': True, 'message': 'Status updated', 'user': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
