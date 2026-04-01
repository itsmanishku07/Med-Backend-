from flask import Blueprint, request, jsonify
from utils.auth_utils import get_current_user
from repositories.medicine_reminder_repository import MedicineReminderRepository

reminder_bp = Blueprint('medicine_reminders', __name__)
reminder_repo = MedicineReminderRepository()


def _require_auth():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None


@reminder_bp.route('/', methods=['GET'])
def get_reminders():
    user, err = _require_auth()
    if err:
        return err
    reminders = reminder_repo.get_by_user(user['uid'])
    return jsonify({'success': True, 'reminders': reminders})


@reminder_bp.route('/', methods=['POST'])
def create_reminder():
    user, err = _require_auth()
    if err:
        return err

    data = request.get_json() or {}
    medicine_name = (data.get('medicine_name') or '').strip()
    reminder_time = (data.get('reminder_time') or '').strip()

    if not medicine_name:
        return jsonify({'success': False, 'message': 'medicine_name is required'}), 400
    if not reminder_time or len(reminder_time) != 5:
        return jsonify({'success': False, 'message': 'reminder_time must be HH:MM'}), 400

    try:
        reminder = reminder_repo.create(
            user_id=user['uid'],
            medicine_name=medicine_name,
            reminder_time=reminder_time,
            dosage=data.get('dosage'),
            days=data.get('days'),
            notes=data.get('notes'),
        )
        return jsonify({'success': True, 'reminder': reminder}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@reminder_bp.route('/<reminder_id>', methods=['PUT'])
def update_reminder(reminder_id):
    user, err = _require_auth()
    if err:
        return err

    data = request.get_json() or {}
    allowed = {'medicine_name', 'dosage', 'reminder_time', 'days', 'is_active', 'notes'}
    updates = {k: v for k, v in data.items() if k in allowed}

    updated = reminder_repo.update(reminder_id, user['uid'], updates)
    if not updated:
        return jsonify({'success': False, 'message': 'Reminder not found'}), 404
    return jsonify({'success': True, 'reminder': updated})


@reminder_bp.route('/<reminder_id>', methods=['DELETE'])
def delete_reminder(reminder_id):
    user, err = _require_auth()
    if err:
        return err

    deleted = reminder_repo.delete(reminder_id, user['uid'])
    if not deleted:
        return jsonify({'success': False, 'message': 'Reminder not found'}), 404
    return jsonify({'success': True, 'message': 'Reminder deleted'})
