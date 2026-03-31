import logging
from flask_socketio import emit, join_room, leave_room, disconnect

logger = logging.getLogger(__name__)

# sid → {user_id (firebase_uid), user_role, user_name, db_id}
active_users = {}


def register_socket_events(socketio):

    @socketio.on('connect')
    def on_connect(auth):
        from utils.auth_utils import verify_firebase_token
        from repositories.user_repository import UserRepository

        token = (auth or {}).get('token', '')
        if not token:
            return False

        token_data = verify_firebase_token(token)
        if not token_data:
            return False

        user_repo = UserRepository()
        db_user = user_repo.find_by_firebase_uid(token_data['uid'])
        if not db_user:
            return False

        from flask import request as flask_request
        sid = flask_request.sid

        active_users[sid] = {
            'user_id': token_data['uid'],
            'user_role': db_user.get('role', 'PATIENT'),
            'user_name': db_user.get('name', ''),
            'db_id': db_user.get('id'),
        }

        join_room(f"user_{token_data['uid']}")
        emit('connected', {
            'message': 'Connected successfully',
            'user_id': token_data['uid'],
        })

    @socketio.on('disconnect')
    def on_disconnect():
        from flask import request as flask_request
        sid = flask_request.sid
        active_users.pop(sid, None)

    @socketio.on('join_chat')
    def on_join_chat(data):
        from flask import request as flask_request
        from repositories.chat_repository import ChatRepository
        from repositories.user_repository import UserRepository

        sid = flask_request.sid
        user_info = active_users.get(sid)
        if not user_info:
            return

        chat_id = (data or {}).get('chat_id')
        if not chat_id:
            return

        chat_repo = ChatRepository()
        chat = chat_repo.find_by_id(chat_id)
        if not chat:
            return

        # Access check
        db_id = user_info['db_id']
        role = user_info['user_role']
        if role == 'PATIENT' and chat['patient_id'] != db_id:
            return
        if role == 'DOCTOR' and chat['doctor_id'] != db_id:
            return

        join_room(chat_id)
        messages = chat_repo.get_messages(chat_id)

        emit('joined_chat', {
            'chat_id': chat_id,
            'messages': messages,
            'chat': chat,
        })

        emit('user_joined', {
            'user_id': user_info['user_id'],
            'user_name': user_info['user_name'],
            'user_role': role,
        }, to=chat_id, skip_sid=sid)

    @socketio.on('leave_chat')
    def on_leave_chat(data):
        from flask import request as flask_request

        sid = flask_request.sid
        user_info = active_users.get(sid)
        if not user_info:
            return

        chat_id = (data or {}).get('chat_id')
        if not chat_id:
            return

        leave_room(chat_id)
        emit('user_left', {
            'user_id': user_info['user_id'],
            'user_name': user_info['user_name'],
        }, to=chat_id, skip_sid=sid)

    @socketio.on('send_message')
    def on_send_message(data):
        from flask import request as flask_request
        from repositories.chat_repository import ChatRepository
        from repositories.notification_repository import NotificationRepository
        from repositories.user_repository import UserRepository

        sid = flask_request.sid
        user_info = active_users.get(sid)
        if not user_info:
            return

        data = data or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return

        chat_repo = ChatRepository()
        chat = chat_repo.find_by_id(chat_id)
        if not chat:
            return

        db_id = user_info['db_id']
        role = user_info['user_role']
        if role == 'PATIENT' and chat['patient_id'] != db_id:
            return
        if role == 'DOCTOR' and chat['doctor_id'] != db_id:
            return

        try:
            msg = chat_repo.send_message(
                chat_id=chat_id,
                sender_firebase_uid=user_info['user_id'],
                sender_role=role,
                content=data.get('message'),
                message_type=data.get('message_type', 'TEXT'),
                image_data=data.get('image_data'),
                file_name=data.get('file_name'),
            )

            emit('new_message', msg, to=chat_id, skip_sid=sid)

            # Notify recipient
            notif_repo = NotificationRepository()
            recipient_db_id = chat['doctor_id'] if role == 'PATIENT' else chat['patient_id']
            try:
                notif = notif_repo.create_notification(
                    user_id=recipient_db_id,
                    notification_type='NEW_MESSAGE',
                    title='New Message',
                    message=f'New message from {user_info["user_name"]}',
                    related_id=chat_id,
                )
                # Find recipient firebase_uid to emit to their personal room
                user_repo = UserRepository()
                recipient = user_repo.find_by_id(recipient_db_id)
                if recipient:
                    emit('new_notification', notif,
                         to=f"user_{recipient['firebase_uid']}", skip_sid=sid)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")

        except Exception as e:
            logger.error(f"send_message error: {e}")

    @socketio.on('typing')
    def on_typing(data):
        from flask import request as flask_request

        sid = flask_request.sid
        user_info = active_users.get(sid)
        if not user_info:
            return

        data = data or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return

        emit('user_typing', {
            'user_id': user_info['user_id'],
            'user_name': user_info['user_name'],
            'is_typing': data.get('is_typing', False),
        }, to=chat_id, skip_sid=sid)

    @socketio.on('mark_read')
    def on_mark_read(data):
        from flask import request as flask_request
        from repositories.chat_repository import ChatRepository

        sid = flask_request.sid
        user_info = active_users.get(sid)
        if not user_info:
            return

        data = data or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return

        chat_repo = ChatRepository()
        chat_repo.mark_messages_as_read(chat_id, user_info['user_role'])

        emit('messages_read', {
            'chat_id': chat_id,
            'read_by': user_info['user_id'],
        }, to=chat_id, skip_sid=sid)
