import uuid
from datetime import datetime
from config.database import SessionLocal
from models.db_models import MedicineReminder


class MedicineReminderRepository:

    def _to_dict(self, r: MedicineReminder) -> dict:
        return {
            'id': r.id,
            'user_id': r.user_id,
            'medicine_name': r.medicine_name,
            'dosage': r.dosage,
            'reminder_time': r.reminder_time,
            'days': r.days,
            'is_active': r.is_active,
            'notes': r.notes,
            'ai_info': r.ai_info,
            'created_at': r.created_at.isoformat() if r.created_at else None,
        }

    def _resolve_db_id(self, user_id: str) -> str | None:
        from repositories.user_repository import UserRepository
        repo = UserRepository()
        user = repo.find_by_firebase_uid(user_id)
        if user:
            return user['id']
        user = repo.find_by_id(user_id)
        return user['id'] if user else None

    def create(self, user_id: str, medicine_name: str, reminder_time: str,
               dosage: str = None, days: list = None, notes: str = None) -> dict:
        db_id = self._resolve_db_id(user_id)
        if not db_id:
            raise ValueError(f'User {user_id} not found')
        with SessionLocal() as session:
            reminder = MedicineReminder(
                id=str(uuid.uuid4()),
                user_id=db_id,
                medicine_name=medicine_name,
                dosage=dosage,
                reminder_time=reminder_time,
                days=days,
                notes=notes,
                is_active=True,
                created_at=datetime.utcnow(),
            )
            session.add(reminder)
            session.commit()
            session.refresh(reminder)
            return self._to_dict(reminder)

    def get_by_user(self, user_id: str) -> list[dict]:
        db_id = self._resolve_db_id(user_id)
        if not db_id:
            return []
        with SessionLocal() as session:
            reminders = (session.query(MedicineReminder)
                         .filter_by(user_id=db_id)
                         .order_by(MedicineReminder.reminder_time)
                         .all())
            return [self._to_dict(r) for r in reminders]

    def update(self, reminder_id: str, user_id: str, updates: dict) -> dict | None:
        db_id = self._resolve_db_id(user_id)
        with SessionLocal() as session:
            r = session.query(MedicineReminder).filter_by(id=reminder_id, user_id=db_id).first()
            if not r:
                return None
            for k, v in updates.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            session.commit()
            session.refresh(r)
            return self._to_dict(r)

    def delete(self, reminder_id: str, user_id: str) -> bool:
        db_id = self._resolve_db_id(user_id)
        with SessionLocal() as session:
            r = session.query(MedicineReminder).filter_by(id=reminder_id, user_id=db_id).first()
            if not r:
                return False
            session.delete(r)
            session.commit()
            return True

    def find_by_id(self, reminder_id: str, user_id: str) -> dict | None:
        db_id = self._resolve_db_id(user_id)
        with SessionLocal() as session:
            r = session.query(MedicineReminder).filter_by(id=reminder_id, user_id=db_id).first()
            return self._to_dict(r) if r else None

    def update_ai_info(self, reminder_id: str, ai_info: dict) -> dict | None:
        with SessionLocal() as session:
            r = session.query(MedicineReminder).filter_by(id=reminder_id).first()
            if not r:
                return None
            r.ai_info = ai_info
            session.commit()
            session.refresh(r)
            return self._to_dict(r)
