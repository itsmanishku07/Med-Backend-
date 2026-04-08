from sqlalchemy.orm import Session
from models.db_models import DoctorAvailabilitySlot, DoctorBlockedDate
from datetime import datetime, timedelta


class AvailabilityRepository:
    
    @staticmethod
    def get_doctor_slots(db: Session, doctor_id: str):
        """Get all weekly template slots for a doctor (slots without specific dates)"""
        return db.query(DoctorAvailabilitySlot).filter(
            DoctorAvailabilitySlot.doctor_id == doctor_id,
            DoctorAvailabilitySlot.date.is_(None)
        ).all()
    
    @staticmethod
    def create_slot(db: Session, doctor_id: str, day_of_week: str, start_time: str, 
                   end_time: str, max_appointments: int):
        """Create a new weekly template slot (no specific date)"""
        slot = DoctorAvailabilitySlot(
            doctor_id=doctor_id,
            day_of_week=day_of_week,
            date=None,  # Weekly template has no specific date
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

    @staticmethod
    def get_calendar_slots(db: Session, doctor_id: str, start_date: str = None, end_date: str = None):
        """Get availability slots for calendar view - returns date-specific slots and weekly template"""
        query = db.query(DoctorAvailabilitySlot).filter(
            DoctorAvailabilitySlot.doctor_id == doctor_id
        )
        
        # If date range provided, filter date-specific slots
        if start_date and end_date:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            query = query.filter(
                DoctorAvailabilitySlot.date.between(start, end)
            )
        
        return query.all()
    
    @staticmethod
    def create_calendar_slot(db: Session, doctor_id: str, date: str, start_time: str, 
                            end_time: str, max_appointments: int):
        """Create availability slot for a specific date"""
        date_obj = datetime.fromisoformat(date)
        day_of_week = date_obj.strftime('%A')
        
        slot = DoctorAvailabilitySlot(
            doctor_id=doctor_id,
            date=date_obj,
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
    def delete_calendar_slot(db: Session, slot_id: str, doctor_id: str):
        """Delete a calendar availability slot"""
        return AvailabilityRepository.delete_slot(db, slot_id, doctor_id)
    
    @staticmethod
    def apply_weekly_template(db: Session, doctor_id: str, start_date: str, weeks: int):
        """Apply weekly template to multiple weeks"""
        # Get the weekly template (slots without specific dates)
        template_slots = db.query(DoctorAvailabilitySlot).filter(
            DoctorAvailabilitySlot.doctor_id == doctor_id,
            DoctorAvailabilitySlot.date.is_(None)
        ).all()
        
        if not template_slots:
            return 0
        
        start_date_obj = datetime.fromisoformat(start_date)
        slots_created = 0
        
        # For each week
        for week in range(weeks):
            # For each day in the week
            for day_offset in range(7):
                current_date = start_date_obj + timedelta(days=(week * 7) + day_offset)
                day_name = current_date.strftime('%A')
                
                # Find template slots for this day
                day_slots = [s for s in template_slots if s.day_of_week == day_name]
                
                # Create slots for this specific date
                for template_slot in day_slots:
                    slot = DoctorAvailabilitySlot(
                        doctor_id=doctor_id,
                        date=current_date,
                        day_of_week=day_name,
                        start_time=template_slot.start_time,
                        end_time=template_slot.end_time,
                        max_appointments=template_slot.max_appointments
                    )
                    
                    db.add(slot)
                    slots_created += 1
        
        db.commit()
        return slots_created
