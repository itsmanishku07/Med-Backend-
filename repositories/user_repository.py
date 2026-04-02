import uuid
from datetime import datetime
from config.database import SessionLocal
from models.db_models import User, UserRole


class UserRepository:

    def _to_dict(self, user: User) -> dict:
        return {
            'id': user.id,
            'firebase_uid': user.firebase_uid,
            'email': user.email,
            'name': user.name,
            'role': user.role.value if user.role else 'PATIENT',
            'phone': user.phone,
            'specializations': user.specializations or [],
            'profile_picture': user.profile_picture,
            'profile': user.profile or {},
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() + 'Z' if user.created_at else None,
            'updated_at': user.updated_at.isoformat() + 'Z' if user.updated_at else None,
        }

    def find_by_firebase_uid(self, firebase_uid: str) -> dict | None:
        with SessionLocal() as session:
            user = session.query(User).filter_by(firebase_uid=firebase_uid).first()
            return self._to_dict(user) if user else None

    def find_by_email(self, email: str) -> dict | None:
        with SessionLocal() as session:
            # Query by lowercase email
            user = session.query(User).filter(User.email.ilike(email)).first()
            return self._to_dict(user) if user else None

    def find_by_id(self, user_id: str) -> dict | None:
        with SessionLocal() as session:
            user = session.query(User).filter_by(id=user_id).first()
            return self._to_dict(user) if user else None

    def create_user(self, firebase_uid: str, email: str, name: str,
                    role: str = 'PATIENT', phone: str = None, 
                    profile_picture: str = None, profile: dict = None) -> dict:
        with SessionLocal() as session:
            user = User(
                id=str(uuid.uuid4()),
                firebase_uid=firebase_uid,
                email=email.lower() if email else '',
                name=name,
                role=UserRole[role],
                phone=phone,
                profile_picture=profile_picture,
                profile=profile,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return self._to_dict(user)

    def update_user(self, user_id: str, updates: dict) -> dict:
        with SessionLocal() as session:
            # Support both db UUID and firebase_uid
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                user = session.query(User).filter_by(firebase_uid=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            for key, value in updates.items():
                if key == 'role':
                    if isinstance(value, UserRole):
                        setattr(user, key, value)
                    else:
                        setattr(user, key, UserRole[str(value).upper()])
                elif hasattr(user, key):
                    setattr(user, key, value)
            user.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(user)
            return self._to_dict(user)

    def get_all_users(self) -> list[dict]:
        with SessionLocal() as session:
            users = session.query(User).all()
            return [self._to_dict(u) for u in users]

    def get_all_doctors(self) -> list[dict]:
        with SessionLocal() as session:
            doctors = session.query(User).filter_by(role=UserRole.DOCTOR, is_active=True).all()
            return [self._to_dict(d) for d in doctors]
