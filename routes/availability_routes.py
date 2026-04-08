from flask import Blueprint, request, jsonify
from functools import wraps
from datetime import datetime
from config.database import SessionLocal
from repositories.availability_repository import AvailabilityRepository
from utils.auth_utils import get_current_user

availability_bp = Blueprint('availability', __name__)


def _require_auth():
    """Helper to check authentication and return user or error response"""
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None


def _require_doctor():
    """Helper to check authentication and doctor role"""
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    
    if user.get('role') not in ['DOCTOR', 'ADMIN']:
        return None, (jsonify({'success': False, 'message': 'Doctor access required'}), 403)
    
    return user, None


@availability_bp.route('/slots', methods=['GET'])
def get_availability_slots():
    """Get doctor's availability slots"""
    user, err = _require_doctor()
    if err: return err
    
    try:
        with SessionLocal() as db:
            slots = AvailabilityRepository.get_doctor_slots(db, user['id'])
            
            slots_data = [{
                'id': slot.id,
                'day_of_week': slot.day_of_week,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'max_appointments': int(slot.max_appointments) if slot.max_appointments else 10,
                'created_at': slot.created_at.isoformat() if slot.created_at else None
            } for slot in slots]
        
        return jsonify({
            'success': True,
            'slots': slots_data
        }), 200
        
    except Exception as e:
        print(f"Error fetching slots: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch availability slots'
        }), 500


@availability_bp.route('/slots', methods=['POST'])
def create_availability_slot():
    """Create a new availability slot"""
    user, err = _require_doctor()
    if err: return err
    
    try:
        data = request.get_json()
        
        required_fields = ['day_of_week', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if data['day_of_week'] not in valid_days:
            return jsonify({
                'success': False,
                'message': 'Invalid day of week'
            }), 400
        
        try:
            datetime.strptime(data['start_time'], '%H:%M')
            datetime.strptime(data['end_time'], '%H:%M')
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid time format. Use HH:MM'
            }), 400
        
        if data['start_time'] >= data['end_time']:
            return jsonify({
                'success': False,
                'message': 'Start time must be before end time'
            }), 400
        
        max_appointments = data.get('max_appointments', 10)
        
        with SessionLocal() as db:
            slot = AvailabilityRepository.create_slot(
                db, user['id'], data['day_of_week'],
                data['start_time'], data['end_time'], max_appointments
            )
            
            slot_data = {
                'id': slot.id,
                'day_of_week': slot.day_of_week,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'max_appointments': int(slot.max_appointments) if slot.max_appointments else 10
            }
        
        return jsonify({
            'success': True,
            'message': 'Availability slot created successfully',
            'slot': slot_data
        }), 201
        
    except Exception as e:
        print(f"Error creating slot: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to create availability slot'
        }), 500


@availability_bp.route('/slots/<slot_id>', methods=['DELETE'])
def delete_availability_slot(slot_id):
    """Delete an availability slot"""
    user, err = _require_doctor()
    if err: return err
    
    try:
        with SessionLocal() as db:
            success = AvailabilityRepository.delete_slot(db, slot_id, user['id'])
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Availability slot deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Slot not found or unauthorized'
            }), 404
            
    except Exception as e:
        print(f"Error deleting slot: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete availability slot'
        }), 500


@availability_bp.route('/blocked-dates', methods=['GET'])
def get_blocked_dates():
    """Get doctor's blocked dates"""
    user, err = _require_doctor()
    if err: return err
    
    try:
        with SessionLocal() as db:
            blocked_dates = AvailabilityRepository.get_blocked_dates(db, user['id'])
            
            dates_data = [{
                'id': blocked.id,
                'date': blocked.date.isoformat() if blocked.date else None,
                'reason': blocked.reason,
                'created_at': blocked.created_at.isoformat() if blocked.created_at else None
            } for blocked in blocked_dates]
        
        return jsonify({
            'success': True,
            'blocked_dates': dates_data
        }), 200
        
    except Exception as e:
        print(f"Error fetching blocked dates: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch blocked dates'
        }), 500


@availability_bp.route('/block-date', methods=['POST'])
def block_date():
    """Block a specific date"""
    user, err = _require_doctor()
    if err: return err
    
    try:
        data = request.get_json()
        
        if 'date' not in data:
            return jsonify({
                'success': False,
                'message': 'Missing required field: date'
            }), 400
        
        try:
            date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date format. Use ISO format (YYYY-MM-DD)'
            }), 400
        
        if date.date() < datetime.utcnow().date():
            return jsonify({
                'success': False,
                'message': 'Cannot block dates in the past'
            }), 400
        
        reason = data.get('reason', '')
        
        with SessionLocal() as db:
            blocked = AvailabilityRepository.block_date(db, user['id'], date, reason)
            
            blocked_data = {
                'id': blocked.id,
                'date': blocked.date.isoformat() if blocked.date else None,
                'reason': blocked.reason
            }
        
        return jsonify({
            'success': True,
            'message': 'Date blocked successfully',
            'blocked_date': blocked_data
        }), 201
        
    except Exception as e:
        print(f"Error blocking date: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to block date'
        }), 500


@availability_bp.route('/blocked-dates/<blocked_id>', methods=['DELETE'])
def unblock_date(blocked_id):
    """Unblock a date"""
    user, err = _require_doctor()
    if err: return err
    
    try:
        with SessionLocal() as db:
            success = AvailabilityRepository.unblock_date(db, blocked_id, user['id'])
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Date unblocked successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Blocked date not found or unauthorized'
            }), 404
            
    except Exception as e:
        print(f"Error unblocking date: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to unblock date'
        }), 500


@availability_bp.route('/doctor/<doctor_id>/slots', methods=['GET'])
def get_doctor_public_slots(doctor_id):
    """Get a doctor's availability slots (for patients booking appointments)"""
    user, err = _require_auth()
    if err: return err
    
    try:
        with SessionLocal() as db:
            slots = AvailabilityRepository.get_doctor_slots(db, doctor_id)
            
            slots_data = [{
                'day_of_week': slot.day_of_week,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'max_appointments': int(slot.max_appointments) if slot.max_appointments else 10
            } for slot in slots]
        
        return jsonify({
            'success': True,
            'slots': slots_data
        }), 200
        
    except Exception as e:
        print(f"Error fetching doctor slots: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch doctor availability'
        }), 500


@availability_bp.route('/doctor/<doctor_id>/is-available', methods=['POST'])
def check_doctor_availability(doctor_id):
    """Check if doctor is available on a specific date/time"""
    user, err = _require_auth()
    if err: return err
    
    try:
        data = request.get_json()
        
        if 'date' not in data:
            return jsonify({
                'success': False,
                'message': 'Missing required field: date'
            }), 400
        
        try:
            date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date format'
            }), 400
        
        with SessionLocal() as db:
            is_blocked = AvailabilityRepository.is_date_blocked(db, doctor_id, date)
            
            if is_blocked:
                return jsonify({
                    'success': True,
                    'available': False,
                    'reason': 'Doctor is not available on this date'
                }), 200
            
            day_name = date.strftime('%A')
            
            slots = AvailabilityRepository.get_doctor_availability_for_day(db, doctor_id, day_name)
            
            if not slots:
                return jsonify({
                    'success': True,
                    'available': False,
                    'reason': 'Doctor does not work on this day'
                }), 200
            
            slots_data = [{
                'start_time': slot.start_time,
                'end_time': slot.end_time
            } for slot in slots]
        
        return jsonify({
            'success': True,
            'available': True,
            'slots': slots_data
        }), 200
        
    except Exception as e:
        print(f"Error checking availability: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to check availability'
        }), 500


@availability_bp.route('/calendar-slots', methods=['GET'])
def get_calendar_slots():
    """Get availability slots for calendar view with date range"""
    user, err = _require_doctor()
    if err: return err
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    try:
        with SessionLocal() as db:
            # Get date-specific slots
            date_slots = []
            if start_date and end_date:
                date_slots = AvailabilityRepository.get_calendar_slots(db, user['id'], start_date, end_date)
            
            # Get weekly template
            weekly_template = AvailabilityRepository.get_doctor_slots(db, user['id'])
            
            # Get blocked dates
            blocked_dates = AvailabilityRepository.get_blocked_dates(db, user['id'])
            
            date_slots_data = [{
                'id': slot.id,
                'date': slot.date.isoformat() if slot.date else None,
                'day_of_week': slot.day_of_week,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'max_appointments': int(slot.max_appointments) if slot.max_appointments else 10
            } for slot in date_slots]
            
            template_data = [{
                'id': slot.id,
                'day_of_week': slot.day_of_week,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'max_appointments': int(slot.max_appointments) if slot.max_appointments else 10
            } for slot in weekly_template]
            
            blocked_data = [{
                'date': blocked.date.isoformat() if blocked.date else None,
                'reason': blocked.reason
            } for blocked in blocked_dates]
        
        return jsonify({
            'success': True,
            'slots': date_slots_data,
            'weekly_template': template_data,
            'blocked_dates': blocked_data
        })
    except Exception as e:
        print(f"Error fetching calendar slots: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@availability_bp.route('/calendar-slots', methods=['POST'])
def create_calendar_slot():
    """Create availability slot for a specific date"""
    user, err = _require_doctor()
    if err: return err
    
    data = request.get_json() or {}
    date = data.get('date')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    max_appointments = data.get('max_appointments', 10)
    
    if not all([date, start_time, end_time]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    try:
        with SessionLocal() as db:
            slot = AvailabilityRepository.create_calendar_slot(
                db, user['id'], date, start_time, end_time, max_appointments
            )
            
            slot_data = {
                'id': slot.id,
                'date': slot.date.isoformat() if slot.date else None,
                'day_of_week': slot.day_of_week,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'max_appointments': int(slot.max_appointments) if slot.max_appointments else 10
            }
        
        return jsonify({'success': True, 'slot': slot_data}), 201
    except Exception as e:
        print(f"Error creating calendar slot: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@availability_bp.route('/calendar-slots/<slot_id>', methods=['DELETE'])
def delete_calendar_slot(slot_id):
    """Delete a calendar availability slot"""
    user, err = _require_doctor()
    if err: return err
    
    try:
        with SessionLocal() as db:
            result = AvailabilityRepository.delete_calendar_slot(db, slot_id, user['id'])
        
        if result:
            return jsonify({'success': True, 'message': 'Slot deleted'})
        else:
            return jsonify({'success': False, 'message': 'Slot not found or unauthorized'}), 404
    except Exception as e:
        print(f"Error deleting calendar slot: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@availability_bp.route('/apply-template', methods=['POST'])
def apply_weekly_template():
    """Apply weekly template to multiple weeks"""
    user, err = _require_doctor()
    if err: return err
    
    data = request.get_json() or {}
    start_date = data.get('start_date')
    weeks = data.get('weeks', 1)
    
    if not start_date:
        return jsonify({'success': False, 'message': 'Start date required'}), 400
    
    try:
        with SessionLocal() as db:
            count = AvailabilityRepository.apply_weekly_template(db, user['id'], start_date, weeks)
        
        return jsonify({
            'success': True,
            'message': f'Template applied to {weeks} week(s)',
            'slots_created': count
        })
    except Exception as e:
        print(f"Error applying template: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
