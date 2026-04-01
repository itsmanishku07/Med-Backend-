import os
from flask import Blueprint, request, jsonify
from utils.auth_utils import get_current_user
from repositories.push_subscription_repository import PushSubscriptionRepository

push_bp = Blueprint('push', __name__)
sub_repo = PushSubscriptionRepository()


def _require_auth():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None


@push_bp.route('/vapid-public-key', methods=['GET'])
def vapid_public_key():
    return jsonify({'success': True, 'publicKey': os.getenv('VAPID_PUBLIC_KEY', '')})


@push_bp.route('/subscribe', methods=['POST'])
def subscribe():
    user, err = _require_auth()
    if err:
        return err
    data = request.get_json() or {}
    endpoint = data.get('endpoint')
    keys = data.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')
    if not endpoint or not p256dh or not auth:
        return jsonify({'success': False, 'message': 'endpoint, keys.p256dh and keys.auth required'}), 400
    try:
        sub_repo.save(user['uid'], endpoint, p256dh, auth)
        return jsonify({'success': True, 'message': 'Subscribed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@push_bp.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    user, err = _require_auth()
    if err:
        return err
    data = request.get_json() or {}
    endpoint = data.get('endpoint')
    if endpoint:
        sub_repo.delete_by_endpoint(endpoint)
    return jsonify({'success': True})
