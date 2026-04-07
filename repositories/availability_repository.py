from sqlalchemy.orm import Session
from models.db_models import DoctorAvailabilitySlot, DoctorBlockedDate
from datetime import datetime


class AvailabilityRepository:
    
    @staticmethod
    def get_doctor_slots(db: Session, doctor_id: str):
        """Get all availability slots for a doctor"""
        return db.query(DoctorAvailabilitySlot).filter(
            DoctorAvailabilitySlot.doctor_id == doctor_id
        ).all()
    
    @staticmethod
    def create_slot(db: Session, doctor_id: str, day_of_week: str, start_time: str, 
                   end_time: str, max_appointments: int):
        """Create a new availability slot"""
        slot = DoctorAvailabilitySlot(
            doctor_id=doctor_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            max_appointments=str(max_appointments)
        )
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot
    
    @staticmethod
    def delete_slot(db: Session, slot_id: str, doctor_id: str):
        """Delete an availability slot"""
        slot = db.query(DoctorAvailabilitySlot).filter(
            DoctorAvailabilitySlot.id == slot_id,
            DoctorAvailabilitySlot.doctor_id == doctor_id
        ).first()
        
        if slot:
            db.delete(slot)
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_blocked_dates(db: Session, doctor_id: str):
        """Get all blocked dates for a doctor"""
        return db.query(DoctorBlockedDate).filter(
            DoctorBlockedDate.doctor_id == doctor_id,
            DoctorBlockedDate.date >= datetime.utcnow()
        ).order_by(DoctorBlockedDate.date).all()
    
    @staticmethod
    def block_date(db: Session, doctor_id: str, date: datetime, reason: str = None):
        """Block a specific date"""
        blocked = DoctorBlockedDate(
            doctor_id=doctor_id,
            date=date,
            reason=reason
        )
        db.add(blocked)
        db.commit()
        db.refresh(blocked)
        return blocked
    
    @staticmethod
    def unblock_date(db: Session, blocked_id: str, doctor_id: str):
        """Unblock a date"""
        blocked = db.query(DoctorBlockedDate).filter(
            DoctorBlockedDate.id == blocked_id,
            DoctorBlockedDate.doctor_id == doctor_id
        ).first()
        
        if blocked:
            db.delete(blocked)
            db.commit()
            return True
        return False
    
    @staticmethod
    def is_date_blocked(db: Session, doctor_id: str, date: datetime):
        """Check if a specific date is blocked"""
        blocked = db.query(DoctorBlockedDate).filter(
            DoctorBlockedDate.doctor_id == doctor_id,
            DoctorBlockedDate.date == date.date()
        ).first()
        return blocked is not None
    
    @staticmethod
    def get_doctor_availability_for_day(db: Session, doctor_id: str, day_of_week: str):
        """Get availability slots for a specific day"""
        return db.query(DoctorAvailabilitySlot).filter(
            DoctorAvailabilitySlot.doctor_id == doctor_id,
            DoctorAvailabilitySlot.day_of_week == day_of_week
        ).all()
