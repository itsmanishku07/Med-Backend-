import uuid
from datetime import datetime
from config.database import SessionLocal
from models.db_models import PushSubscription


class PushSubscriptionRepository:

    def _resolve_db_id(self, user_id: str) -> str | None:
        from repositories.user_repository import UserRepository
        repo = UserRepository()
        user = repo.find_by_firebase_uid(user_id)
        if user:
            return user['id']
        user = repo.find_by_id(user_id)
        return user['id'] if user else None

    def save(self, user_id: str, endpoint: str, p256dh: str, auth: str) -> dict:
        db_id = self._resolve_db_id(user_id)
        if not db_id:
            raise ValueError(f'User {user_id} not found')
        with SessionLocal() as session:
            existing = session.query(PushSubscription).filter_by(endpoint=endpoint).first()
            if existing:
                existing.p256dh = p256dh
                existing.auth = auth
                existing.user_id = db_id
                session.commit()
                return {'id': existing.id, 'endpoint': existing.endpoint}
            sub = PushSubscription(
                id=str(uuid.uuid4()),
                user_id=db_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                created_at=datetime.utcnow(),
            )
            session.add(sub)
            session.commit()
            return {'id': sub.id, 'endpoint': sub.endpoint}

    def get_by_user(self, user_id: str) -> list[dict]:
        db_id = self._resolve_db_id(user_id)
        if not db_id:
            return []
        with SessionLocal() as session:
            subs = session.query(PushSubscription).filter_by(user_id=db_id).all()
            return [{'endpoint': s.endpoint, 'p256dh': s.p256dh, 'auth': s.auth} for s in subs]

    def delete_by_endpoint(self, endpoint: str) -> None:
        with SessionLocal() as session:
            session.query(PushSubscription).filter_by(endpoint=endpoint).delete()
            session.commit()

    def get_all_active_subscriptions(self) -> list[dict]:
        """Returns all subscriptions joined with user db id."""
        with SessionLocal() as session:
            subs = session.query(PushSubscription).all()
            return [{'user_id': s.user_id, 'endpoint': s.endpoint,
                     'p256dh': s.p256dh, 'auth': s.auth} for s in subs]
