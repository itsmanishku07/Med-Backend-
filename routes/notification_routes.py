from flask import Blueprint, request, jsonify
from utils.auth_utils import get_current_user
from repositories.notification_repository import NotificationRepository

notification_bp = Blueprint('notifications', __name__)
notif_repo = NotificationRepository()


def _require_auth():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None


@notification_bp.route('/', methods=['GET'])
def get_notifications():
    user, err = _require_auth()
    if err:
        return err

    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 50))

    notifications = notif_repo.get_user_notifications(
        user_id=user['uid'],
        limit=limit,
        unread_only=unread_only,
    )
    return jsonify({'success': True, 'notifications': notifications})


@notification_bp.route('/unread-count', methods=['GET'])
def unread_count():
    user, err = _require_auth()
    if err:
        return err

    count = notif_repo.get_unread_count(user['uid'])
    return jsonify({'success': True, 'count': count})


@notification_bp.route('/<notif_id>/read', methods=['PUT'])
def mark_read(notif_id):
    user, err = _require_auth()
    if err:
        return err

    success = notif_repo.mark_as_read(notif_id)
    if not success:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404
    return jsonify({'success': True, 'message': 'Marked as read'})


@notification_bp.route('/mark-all-read', methods=['PUT'])
def mark_all_read():
    user, err = _require_auth()
    if err:
        return err

    count = notif_repo.mark_all_as_read(user['uid'])
    return jsonify({'success': True, 'message': f'{count} notifications marked as read'})


@notification_bp.route('/<notif_id>', methods=['DELETE'])
def delete_notification(notif_id):
    user, err = _require_auth()
    if err:
        return err

    notif = notif_repo.get_notification_by_id(notif_id)
    if not notif:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404

    from repositories.user_repository import UserRepository
    db_user = UserRepository().find_by_firebase_uid(user['uid'])
    if not db_user or notif['user_id'] != db_user['id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    notif_repo.delete_notification(notif_id)
    return jsonify({'success': True, 'message': 'Notification deleted'})
