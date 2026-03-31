import uuid
from datetime import datetime
from config.database import SessionLocal
from models.db_models import Chat, ChatMessage, UserRole, MessageType


class ChatRepository:

    def _chat_to_dict(self, chat: Chat) -> dict:
        return {
            'id': chat.id,
            'report_id': chat.report_id,
            'patient_id': chat.patient_id,
            'doctor_id': chat.doctor_id,
            'created_at': chat.created_at.isoformat() if chat.created_at else None,
            'last_message_at': chat.last_message_at.isoformat() if chat.last_message_at else None,
        }

    def _message_to_dict(self, msg: ChatMessage) -> dict:
        return {
            'id': msg.id,
            'chat_id': msg.chat_id,
            'sender_id': msg.sender_id,
            'sender_role': msg.sender_role.value if msg.sender_role else None,
            'message_type': msg.message_type.value if msg.message_type else 'TEXT',
            'content': msg.content,
            'image_data': msg.image_data,
            'file_name': msg.file_name,
            'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
            'read': msg.read,
        }

    def _resolve_firebase_uid(self, firebase_uid: str) -> str | None:
        from repositories.user_repository import UserRepository
        user = UserRepository().find_by_firebase_uid(firebase_uid)
        return user['id'] if user else None

    def create_chat(self, report_id: str, patient_id: str, doctor_id: str) -> dict:
        with SessionLocal() as session:
            chat = Chat(
                id=str(uuid.uuid4()),
                report_id=report_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                created_at=datetime.utcnow(),
            )
            session.add(chat)
            session.commit()
            session.refresh(chat)
            return self._chat_to_dict(chat)

    def find_by_id(self, chat_id: str) -> dict | None:
        with SessionLocal() as session:
            chat = session.query(Chat).filter_by(id=chat_id).first()
            return self._chat_to_dict(chat) if chat else None

    def find_by_report_id(self, report_id: str) -> dict | None:
        with SessionLocal() as session:
            chat = session.query(Chat).filter_by(report_id=report_id).first()
            return self._chat_to_dict(chat) if chat else None

    def get_user_chats(self, firebase_uid: str, role: str) -> list[dict]:
        db_id = self._resolve_firebase_uid(firebase_uid)
        if not db_id:
            return []
        with SessionLocal() as session:
            if role == 'PATIENT':
                chats = session.query(Chat).filter_by(patient_id=db_id).all()
            elif role == 'DOCTOR':
                chats = session.query(Chat).filter_by(doctor_id=db_id).all()
            else:
                chats = session.query(Chat).all()
            return [self._chat_to_dict(c) for c in chats]

    def get_messages(self, chat_id: str, limit: int = 100) -> list[dict]:
        with SessionLocal() as session:
            messages = (session.query(ChatMessage)
                        .filter_by(chat_id=chat_id)
                        .order_by(ChatMessage.timestamp.asc())
                        .limit(limit)
                        .all())
            return [self._message_to_dict(m) for m in messages]

    def send_message(self, chat_id: str, sender_firebase_uid: str, sender_role: str,
                     content: str = None, message_type: str = 'TEXT',
                     image_data: str = None, file_name: str = None) -> dict:
        sender_db_id = self._resolve_firebase_uid(sender_firebase_uid)
        if not sender_db_id:
            raise ValueError(f"Sender {sender_firebase_uid} not found")
        with SessionLocal() as session:
            msg = ChatMessage(
                id=str(uuid.uuid4()),
                chat_id=chat_id,
                sender_id=sender_db_id,
                sender_role=UserRole[sender_role],
                message_type=MessageType[message_type],
                content=content,
                image_data=image_data,
                file_name=file_name,
                timestamp=datetime.utcnow(),
                read=False,
            )
            session.add(msg)
            # Update last_message_at on chat
            chat = session.query(Chat).filter_by(id=chat_id).first()
            if chat:
                chat.last_message_at = datetime.utcnow()
            session.commit()
            session.refresh(msg)
            return self._message_to_dict(msg)

    def mark_messages_as_read(self, chat_id: str, reader_role: str) -> None:
        with SessionLocal() as session:
            if reader_role == 'PATIENT':
                # Patient reads → mark doctor's messages as read
                (session.query(ChatMessage)
                 .filter_by(chat_id=chat_id, read=False)
                 .filter(ChatMessage.sender_role == UserRole.DOCTOR)
                 .update({'read': True}))
            elif reader_role == 'DOCTOR':
                # Doctor reads → mark patient's messages as read
                (session.query(ChatMessage)
                 .filter_by(chat_id=chat_id, read=False)
                 .filter(ChatMessage.sender_role == UserRole.PATIENT)
                 .update({'read': True}))
            session.commit()
