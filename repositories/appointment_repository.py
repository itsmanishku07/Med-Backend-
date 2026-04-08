from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from config.database import SessionLocal
from models.db_models import Appointment, AppointmentStatus, User

class AppointmentRepository:
    def create_appointment(self, patient_id: str, doctor_id: str, notes: str = None, preferred_time: datetime = None) -> Dict[str, Any]:
        with SessionLocal() as session:
            appointment = Appointment(
                patient_id=patient_id,
                doctor_id=doctor_id,
                notes=notes,
                preferred_time=preferred_time,
                status=AppointmentStatus.PENDING
            )
            session.add(appointment)
            session.commit()
            session.refresh(appointment)
            return self._to_dict(appointment)

    def get_by_id(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        with SessionLocal() as session:
            appointment = session.query(Appointment).filter(Appointment.id == appointment_id).first()
            return self._to_dict(appointment) if appointment else None

    def get_patient_appointments(self, patient_id: str) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            appointments = session.query(Appointment)\
                .filter(Appointment.patient_id == patient_id)\
                .order_by(Appointment.requested_at.desc())\
                .all()
            return [self._to_dict(a) for a in appointments]

    def get_doctor_appointments(self, doctor_id: str) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            appointments = session.query(Appointment)\
                .filter(Appointment.doctor_id == doctor_id)\
                .order_by(Appointment.requested_at.desc())\
                .all()
            return [self._to_dict(a) for a in appointments]

    def update_appointment(self, appointment_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with SessionLocal() as session:
            appointment = session.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                return None
            
            for key, value in updates.items():
                if hasattr(appointment, key):
                    if key == 'status' and isinstance(value, str):
                        value = AppointmentStatus(value)
                    setattr(appointment, key, value)
            
            session.commit()
            session.refresh(appointment)
            return self._to_dict(appointment)

    def _to_dict(self, appointment: Appointment) -> Dict[str, Any]:
        if not appointment:
            return None
        
        data = {
            'id': appointment.id,
            'patient_id': appointment.patient_id,
            'doctor_id': appointment.doctor_id,
            'status': appointment.status.value,
            'requested_at': appointment.requested_at.isoformat() if appointment.requested_at else None,
            'preferred_time': appointment.preferred_time.isoformat() if appointment.preferred_time else None,
            'scheduled_at': appointment.scheduled_at.isoformat() if appointment.scheduled_at else None,
            'notes': appointment.notes,
            'doctor_notes': appointment.doctor_notes,
            'created_at': appointment.created_at.isoformat() if appointment.created_at else None
        }

        with SessionLocal() as session:
            patient = session.query(User).filter(User.id == appointment.patient_id).first()
            doctor = session.query(User).filter(User.id == appointment.doctor_id).first()
            data['patient_name'] = patient.name if patient else 'Unknown'
            data['doctor_name'] = doctor.name if doctor else 'Unknown'
            data['doctor_email'] = doctor.email if doctor else ''
            
        return data
