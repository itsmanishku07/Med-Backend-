import uuid
from datetime import datetime
from config.database import SessionLocal
from models.db_models import Notification, NotificationType


class NotificationRepository:

    def _to_dict(self, n: Notification) -> dict:
        return {
            'id': n.id,
            'user_id': n.user_id,
            'notification_type': n.notification_type.value if n.notification_type else None,
            'title': n.title,
            'message': n.message,
            'related_id': n.related_id,
            'data': n.data,
            'read': n.read,
            'created_at': n.created_at.isoformat() if n.created_at else None,
        }

    def _resolve_user_db_id(self, user_id: str) -> str | None:
        """Accept either firebase_uid or db UUID, return db UUID."""
        from repositories.user_repository import UserRepository
        repo = UserRepository()
        # Try as db UUID first
        user = repo.find_by_id(user_id)
        if user:
            return user['id']
        # Try as firebase_uid
        user = repo.find_by_firebase_uid(user_id)
        if user:
            return user['id']
        return None

    def create_notification(self, user_id: str, notification_type: str,
                            title: str, message: str,
                            related_id: str = None, data: dict = None) -> dict:
        db_user_id = self._resolve_user_db_id(user_id)
        if not db_user_id:
            raise ValueError(f"User {user_id} not found")
        with SessionLocal() as session:
            notif = Notification(
                id=str(uuid.uuid4()),
                user_id=db_user_id,
                notification_type=NotificationType[notification_type],
                title=title,
                message=message,
                related_id=related_id,
                data=data,
                read=False,
                created_at=datetime.utcnow(),
            )
            session.add(notif)
            session.commit()
            session.refresh(notif)
            return self._to_dict(notif)

    def get_user_notifications(self, user_id: str, limit: int = 50,
                               unread_only: bool = False) -> list[dict]:
        db_user_id = self._resolve_user_db_id(user_id)
        if not db_user_id:
            return []
        with SessionLocal() as session:
            q = session.query(Notification).filter_by(user_id=db_user_id)
            if unread_only:
                q = q.filter_by(read=False)
            notifications = q.order_by(Notification.created_at.desc()).limit(limit).all()
            return [self._to_dict(n) for n in notifications]

    def get_unread_count(self, user_id: str) -> int:
        db_user_id = self._resolve_user_db_id(user_id)
        if not db_user_id:
            return 0
        with SessionLocal() as session:
            return session.query(Notification).filter_by(user_id=db_user_id, read=False).count()

    def mark_as_read(self, notification_id: str) -> bool:
        with SessionLocal() as session:
            notif = session.query(Notification).filter_by(id=notification_id).first()
            if not notif:
                return False
            notif.read = True
            session.commit()
            return True

    def mark_all_as_read(self, user_id: str) -> int:
        db_user_id = self._resolve_user_db_id(user_id)
        if not db_user_id:
            return 0
        with SessionLocal() as session:
            count = (session.query(Notification)
                     .filter_by(user_id=db_user_id, read=False)
                     .update({'read': True}))
            session.commit()
            return count

    def delete_notification(self, notification_id: str) -> bool:
        with SessionLocal() as session:
            notif = session.query(Notification).filter_by(id=notification_id).first()
            if not notif:
                return False
            session.delete(notif)
            session.commit()
            return True

    def get_notification_by_id(self, notification_id: str) -> dict | None:
        with SessionLocal() as session:
            notif = session.query(Notification).filter_by(id=notification_id).first()
            return self._to_dict(notif) if notif else None
