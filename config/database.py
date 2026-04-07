import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://user:password@localhost:5432/medical_db')

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Create all tables."""
    from models.db_models import (
        User, MedicalReport, Chat, ChatMessage,
        Notification, MedicalReportAIChat, MedicineReminder, PushSubscription,
        Appointment, DoctorAvailabilitySlot, DoctorBlockedDate, DoctorReview
    )  # noqa: F401
    Base.metadata.create_all(bind=engine)
