from flask import Blueprint, request, jsonify
from utils.auth_utils import get_current_user
from repositories.chat_repository import ChatRepository
from repositories.medical_report_repository import MedicalReportRepository
from repositories.user_repository import UserRepository
from repositories.notification_repository import NotificationRepository

chat_bp = Blueprint('chats', __name__)
chat_repo = ChatRepository()
report_repo = MedicalReportRepository()
user_repo = UserRepository()
notif_repo = NotificationRepository()


def _require_auth():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None


def _can_access_chat(user: dict, chat: dict) -> bool:
    db_user = user_repo.find_by_firebase_uid(user['uid'])
    if not db_user:
        return False
    db_id = db_user['id']
    role = user.get('role', 'PATIENT')
    if role == 'ADMIN':
        return True
    if role == 'PATIENT':
        return chat['patient_id'] == db_id
    if role == 'DOCTOR':
        return chat['doctor_id'] == db_id
    return False


@chat_bp.route('/report/<report_id>', methods=['GET'])
def get_or_create_chat(report_id):
    user, err = _require_auth()
    if err:
        return err

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    db_user = user_repo.find_by_firebase_uid(user['uid'])
    if not db_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    db_id = db_user['id']
    role = user.get('role', 'PATIENT')

    if role == 'PATIENT' and report['patient_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    if role == 'DOCTOR' and report['assigned_doctor_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    chat = chat_repo.find_by_report_id(report_id)
    if not chat:
        if not report.get('assigned_doctor_id'):
            return jsonify({'success': False, 'message': 'No doctor assigned to this report yet'}), 400
        try:
            chat = chat_repo.create_chat(
                report_id=report_id,
                patient_id=report['patient_id'],
                doctor_id=report['assigned_doctor_id'],
            )
        except Exception:
            chat = chat_repo.find_by_report_id(report_id)
            if not chat:
                return jsonify({'success': False, 'message': 'Failed to create chat'}), 500

    messages = chat_repo.get_messages(chat['id'])
    chat_repo.mark_messages_as_read(chat['id'], role)

    return jsonify({'success': True, 'chat': chat, 'messages': messages})


@chat_bp.route('/', methods=['GET'])
def get_chats():
    user, err = _require_auth()
    if err:
        return err

    chats = chat_repo.get_user_chats(user['uid'], user.get('role', 'PATIENT'))
    return jsonify({'success': True, 'chats': chats})


@chat_bp.route('/<chat_id>/messages', methods=['GET'])
def get_messages(chat_id):
    user, err = _require_auth()
    if err:
        return err

    chat = chat_repo.find_by_id(chat_id)
    if not chat:
        return jsonify({'success': False, 'message': 'Chat not found'}), 404

    if not _can_access_chat(user, chat):
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    messages = chat_repo.get_messages(chat_id)
    chat_repo.mark_messages_as_read(chat_id, user.get('role', 'PATIENT'))
    return jsonify({'success': True, 'messages': messages})


@chat_bp.route('/<chat_id>/messages', methods=['POST'])
def send_message(chat_id):
    user, err = _require_auth()
    if err:
        return err

    chat = chat_repo.find_by_id(chat_id)
    if not chat:
        return jsonify({'success': False, 'message': 'Chat not found'}), 404

    if not _can_access_chat(user, chat):
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    data = request.get_json() or {}
    content = data.get('message') or data.get('content')
    message_type = data.get('message_type', 'TEXT').upper()
    image_data = data.get('image_data')
    file_name = data.get('file_name')

    try:
        msg = chat_repo.send_message(
            chat_id=chat_id,
            sender_firebase_uid=user['uid'],
            sender_role=user.get('role', 'PATIENT'),
            content=content,
            message_type=message_type,
            image_data=image_data,
            file_name=file_name,
        )

        role = user.get('role', 'PATIENT')
        db_user = user_repo.find_by_firebase_uid(user['uid'])
        if role == 'PATIENT':
            recipient_id = chat['doctor_id']
        else:
            recipient_id = chat['patient_id']

        try:
            notif_repo.create_notification(
                user_id=recipient_id,
                notification_type='NEW_MESSAGE',
                title='New Message',
                message=f'You have a new message from {db_user["name"] if db_user else "a user"}.',
                related_id=chat_id,
            )
        except Exception:
            pass

        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@chat_bp.route('/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    user, err = _require_auth()
    if err:
        return err

    chat = chat_repo.find_by_id(chat_id)
    if not chat:
        return jsonify({'success': False, 'message': 'Chat not found'}), 404

    if not _can_access_chat(user, chat):
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    try:
        chat_repo.delete_chat(chat_id)
        return jsonify({'success': True, 'message': 'Chat deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
