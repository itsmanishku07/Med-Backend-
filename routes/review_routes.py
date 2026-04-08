from flask import Blueprint, request, jsonify
from config.database import SessionLocal
from repositories.review_repository import ReviewRepository
from utils.auth_utils import get_current_user

review_bp = Blueprint('reviews', __name__)


def _require_auth():
    """Helper to check authentication and return user or error response"""
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None


@review_bp.route('/doctor/<doctor_id>', methods=['GET'])
def get_doctor_reviews(doctor_id):
    """Get all reviews for a doctor (public endpoint)"""
    try:
        with SessionLocal() as db:
            reviews = ReviewRepository.get_doctor_reviews(db, doctor_id)
            stats = ReviewRepository.get_doctor_rating_stats(db, doctor_id)
        
        return jsonify({
            'success': True,
            'reviews': reviews,
            'stats': stats
        }), 200
        
    except Exception as e:
        import traceback
        print(f"Error fetching reviews: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': 'Failed to fetch reviews',
            'error': str(e)
        }), 500


@review_bp.route('/doctor/<doctor_id>/my-review', methods=['GET'])
def get_my_review(doctor_id):
    """Get current patient's review for a doctor"""
    user, err = _require_auth()
    if err: return err
    
    try:
        with SessionLocal() as db:
            review = ReviewRepository.get_patient_review(db, doctor_id, user['id'])
        
        return jsonify({
            'success': True,
            'review': review
        }), 200
        
    except Exception as e:
        print(f"Error fetching review: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch review'
        }), 500


@review_bp.route('/doctor/<doctor_id>', methods=['POST'])
def create_review(doctor_id):
    """Create or update a review for a doctor"""
    user, err = _require_auth()
    if err: return err
    
    try:
        data = request.get_json()
        
        rating = data.get('rating')
        comment = data.get('comment', '').strip()
        
        if not rating or rating < 1 or rating > 5:
            return jsonify({
                'success': False,
                'message': 'Rating must be between 1 and 5'
            }), 400
        
        with SessionLocal() as db:
            review = ReviewRepository.create_review(
                db, doctor_id, user['id'], rating, comment
            )
            
            stats = ReviewRepository.get_doctor_rating_stats(db, doctor_id)
        
        return jsonify({
            'success': True,
            'message': 'Review submitted successfully',
            'review': {
                'id': review.id,
                'rating': int(review.rating),
                'comment': review.comment,
                'created_at': review.created_at.isoformat() if review.created_at else None
            },
            'stats': stats
        }), 201
        
    except Exception as e:
        print(f"Error creating review: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to submit review'
        }), 500


@review_bp.route('/<review_id>', methods=['DELETE'])
def delete_review(review_id):
    """Delete a review"""
    user, err = _require_auth()
    if err: return err
    
    try:
        with SessionLocal() as db:
            success = ReviewRepository.delete_review(db, review_id, user['id'])
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Review deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Review not found or unauthorized'
            }), 404
            
    except Exception as e:
        print(f"Error deleting review: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete review'
        }), 500


@review_bp.route('/all-stats', methods=['GET'])
def get_all_stats():
    """Get rating stats for all doctors (public endpoint)"""
    try:
        with SessionLocal() as db:
            stats = ReviewRepository.get_all_doctors_rating_stats(db)
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
        
    except Exception as e:
        print(f"Error fetching all stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch stats'
        }), 500
