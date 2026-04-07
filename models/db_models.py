import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, JSON,
    Enum as SAEnum, ForeignKey, UniqueConstraint, LargeBinary
)
from sqlalchemy.orm import relationship
import enum

from config.database import Base


class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    PATIENT = "PATIENT"


class ReportStatus(enum.Enum):
    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    ANALYZED = "ANALYZED"
    REVIEWED = "REVIEWED"
    FAILED = "FAILED"


class AppointmentStatus(enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class NotificationType(enum.Enum):
    REPORT_UPLOADED = "REPORT_UPLOADED"
    REPORT_ANALYZED = "REPORT_ANALYZED"
    DOCTOR_ASSIGNED = "DOCTOR_ASSIGNED"
    DOCTOR_REVIEWED = "DOCTOR_REVIEWED"
    NEW_MESSAGE = "NEW_MESSAGE"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    DOCTOR_ACCEPTED = "DOCTOR_ACCEPTED"
    MEDICINE_REMINDER = "MEDICINE_REMINDER"
    APPOINTMENT_REQUESTED = "APPOINTMENT_REQUESTED"
    APPOINTMENT_ACCEPTED = "APPOINTMENT_ACCEPTED"


class MessageType(enum.Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"


class SeverityLevel(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class User(Base):
    __tablename__ = 'users'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    firebase_uid = Column(String(128), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.PATIENT)
    phone = Column(String(20), nullable=True)
    specializations = Column(JSON, nullable=True)
    profile_picture = Column(Text, nullable=True)
    profile = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reports_as_patient = relationship('MedicalReport', foreign_keys='MedicalReport.patient_id', back_populates='patient')
    reports_as_doctor = relationship('MedicalReport', foreign_keys='MedicalReport.assigned_doctor_id', back_populates='assigned_doctor')
    notifications = relationship('Notification', back_populates='user')
    appointments_as_patient = relationship('Appointment', foreign_keys='Appointment.patient_id', back_populates='patient')
    appointments_as_doctor = relationship('Appointment', foreign_keys='Appointment.doctor_id', back_populates='doctor')


class MedicalReport(Base):
    __tablename__ = 'medical_reports'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    assigned_doctor_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=True)
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(50))
    file_size = Column(String(50))
    status = Column(SAEnum(ReportStatus), default=ReportStatus.PENDING, index=True)
    medical_specialty = Column(String(255), nullable=True)
    suggested_doctors = Column(JSON, nullable=True)
    ai_analysis = Column(JSON, nullable=True)
    doctor_notes = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, index=True)
    analyzed_at = Column(DateTime, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, default=False, index=True)
    doctor_edit_permission = Column(Boolean, default=False)
    extracted_text = Column(Text, nullable=True)
    file_content = Column(LargeBinary, nullable=True)

    patient = relationship('User', foreign_keys=[patient_id], back_populates='reports_as_patient')
    assigned_doctor = relationship('User', foreign_keys=[assigned_doctor_id], back_populates='reports_as_doctor')
    chat = relationship('Chat', back_populates='report', uselist=False)


class Chat(Base):
    __tablename__ = 'chats'
    __table_args__ = (UniqueConstraint('report_id', name='uq_chat_report_id'),)

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(128), ForeignKey('medical_reports.id'), unique=True, index=True, nullable=False)
    patient_id = Column(String(128), ForeignKey('users.id'), nullable=False)
    doctor_id = Column(String(128), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)

    report = relationship('MedicalReport', back_populates='chat')
    patient = relationship('User', foreign_keys=[patient_id])
    doctor = relationship('User', foreign_keys=[doctor_id])
    messages = relationship('ChatMessage', back_populates='chat', order_by='ChatMessage.timestamp')


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(128), ForeignKey('chats.id'), index=True, nullable=False)
    sender_id = Column(String(128), ForeignKey('users.id'), nullable=False)
    sender_role = Column(SAEnum(UserRole), nullable=False)
    message_type = Column(SAEnum(MessageType), default=MessageType.TEXT)
    content = Column(Text, nullable=True)
    image_data = Column(Text, nullable=True)
    file_name = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    read = Column(Boolean, default=False)

    chat = relationship('Chat', back_populates='messages')
    sender = relationship('User', foreign_keys=[sender_id])


class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    notification_type = Column(SAEnum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    related_id = Column(String(128), nullable=True)
    data = Column(JSON, nullable=True)
    read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship('User', back_populates='notifications')


class MedicineReminder(Base):
    __tablename__ = 'medicine_reminders'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    medicine_name = Column(String(255), nullable=False)
    dosage = Column(String(100), nullable=True)
    reminder_time = Column(String(5), nullable=False)   # "HH:MM" 24h format
    days = Column(JSON, nullable=True)                  # ["Mon","Tue",...] or null = every day
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    ai_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship('User', foreign_keys=[user_id])


class PushSubscription(Base):
    __tablename__ = 'push_subscriptions'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship('User', foreign_keys=[user_id])


class MedicalReportAIChat(Base):
    __tablename__ = 'medical_report_ai_chats'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(128), ForeignKey('medical_reports.id'), index=True, nullable=False)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    report = relationship('MedicalReport')


class Appointment(Base):
    __tablename__ = 'appointments'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    doctor_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    status = Column(SAEnum(AppointmentStatus), default=AppointmentStatus.PENDING, index=True)
    requested_at = Column(DateTime, default=datetime.utcnow)
    preferred_time = Column(DateTime, nullable=True) # Suggested by patient
    scheduled_at = Column(DateTime, nullable=True)  # Set by doctor upon acceptance
    notes = Column(Text, nullable=True)              # Patient's message
    doctor_notes = Column(Text, nullable=True)       # Doctor's response
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship('User', foreign_keys=[patient_id], back_populates='appointments_as_patient')
    doctor = relationship('User', foreign_keys=[doctor_id], back_populates='appointments_as_doctor')


class PendingRegistration(Base):
    __tablename__ = 'pending_registrations'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_encrypted = Column(Text, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DoctorAvailabilitySlot(Base):
    __tablename__ = 'doctor_availability_slots'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    day_of_week = Column(String(20), nullable=False)  # Monday, Tuesday, etc.
    start_time = Column(String(5), nullable=False)    # HH:MM format (24h)
    end_time = Column(String(5), nullable=False)      # HH:MM format (24h)
    max_appointments = Column(String(10), default='10')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    doctor = relationship('User', foreign_keys=[doctor_id])


class DoctorBlockedDate(Base):
    __tablename__ = 'doctor_blocked_dates'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    date = Column(DateTime, nullable=False, index=True)  # Specific date to block
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    doctor = relationship('User', foreign_keys=[doctor_id])


class DoctorReview(Base):
    __tablename__ = 'doctor_reviews'

    id = Column(String(128), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    patient_id = Column(String(128), ForeignKey('users.id'), index=True, nullable=False)
    rating = Column(String(10), nullable=False)  # 1-5 stars
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    doctor = relationship('User', foreign_keys=[doctor_id])
    patient = relationship('User', foreign_keys=[patient_id])
    
    __table_args__ = (
        UniqueConstraint('doctor_id', 'patient_id', name='uq_doctor_patient_review'),
    )
