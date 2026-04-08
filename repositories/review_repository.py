from sqlalchemy.orm import Session
from sqlalchemy import func
from models.db_models import DoctorReview, User
from datetime import datetime
import uuid


class ReviewRepository:
    
    @staticmethod
    def create_review(db: Session, doctor_id: str, patient_id: str, rating: int, comment: str = None):
        """Create or update a review"""
        existing = db.query(DoctorReview).filter(
            DoctorReview.doctor_id == doctor_id,
            DoctorReview.patient_id == patient_id
        ).first()
        
        if existing:
            existing.rating = str(rating)
            existing.comment = comment
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            review = DoctorReview(
                id=str(uuid.uuid4()),
                doctor_id=doctor_id,
                patient_id=patient_id,
                rating=str(rating),
                comment=comment,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(review)
            db.commit()
            db.refresh(review)
            return review
    
    @staticmethod
    def get_doctor_reviews(db: Session, doctor_id: str):
        """Get all reviews for a doctor with patient info"""
        reviews = db.query(DoctorReview, User).join(
            User, DoctorReview.patient_id == User.id
        ).filter(
            DoctorReview.doctor_id == doctor_id
        ).order_by(DoctorReview.created_at.desc()).all()
        
        result = []
        for review, patient in reviews:
            result.append({
                'id': review.id,
                'rating': int(review.rating) if review.rating else 0,
                'comment': review.comment,
                'created_at': review.created_at.isoformat() if review.created_at else None,
                'updated_at': review.updated_at.isoformat() if review.updated_at else None,
                'patient': {
                    'id': patient.id,
                    'name': patient.name,
                    'profile_picture': patient.profile_picture
                }
            })
        return result
    
    @staticmethod
    def get_doctor_rating_stats(db: Session, doctor_id: str):
        """Get average rating and count for a doctor"""
        from sqlalchemy import Integer
        
        stats = db.query(
            func.avg(func.cast(DoctorReview.rating, Integer)).label('average'),
            func.count(DoctorReview.id).label('count')
        ).filter(
            DoctorReview.doctor_id == doctor_id
        ).first()
        
        return {
            'average_rating': round(float(stats.average), 1) if stats.average else 0.0,
            'total_reviews': stats.count or 0
        }
    
    @staticmethod
    def get_patient_review(db: Session, doctor_id: str, patient_id: str):
        """Get a specific patient's review for a doctor"""
        review = db.query(DoctorReview).filter(
            DoctorReview.doctor_id == doctor_id,
            DoctorReview.patient_id == patient_id
        ).first()
        
        if not review:
            return None
        
        return {
            'id': review.id,
            'rating': int(review.rating) if review.rating else 0,
            'comment': review.comment,
            'created_at': review.created_at.isoformat() if review.created_at else None,
            'updated_at': review.updated_at.isoformat() if review.updated_at else None
        }
    
    @staticmethod
    def delete_review(db: Session, review_id: str, patient_id: str):
        """Delete a review (only by the patient who created it)"""
        review = db.query(DoctorReview).filter(
            DoctorReview.id == review_id,
            DoctorReview.patient_id == patient_id
        ).first()
        
        if review:
            db.delete(review)
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_all_doctors_rating_stats(db: Session):
        """Get rating stats for all doctors"""
        from sqlalchemy import Integer
        
        stats = db.query(
            DoctorReview.doctor_id,
            func.avg(func.cast(DoctorReview.rating, Integer)).label('average'),
            func.count(DoctorReview.id).label('count')
        ).group_by(DoctorReview.doctor_id).all()
        
        result = {}
        for stat in stats:
            result[stat.doctor_id] = {
                'average_rating': round(float(stat.average), 1) if stat.average else 0.0,
                'total_reviews': stat.count or 0
            }
        return result
