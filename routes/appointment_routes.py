from flask import Blueprint, request, jsonify
from datetime import datetime
from utils.auth_utils import get_current_user
from repositories.appointment_repository import AppointmentRepository
from repositories.user_repository import UserRepository
from repositories.notification_repository import NotificationRepository

appointment_bp = Blueprint('appointments', __name__)
appointment_repo = AppointmentRepository()
user_repo = UserRepository()
notif_repo = NotificationRepository()

def _require_auth():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None

@appointment_bp.route('/request', methods=['POST'])
def request_appointment():
    user, err = _require_auth()
    if err: return err

    data = request.get_json() or {}
    doctor_id = data.get('doctor_id')
    notes = data.get('notes', '')
    preferred_time_str = data.get('preferred_time')

    if not doctor_id:
        return jsonify({'success': False, 'message': 'Doctor ID is required'}), 400

    preferred_time = None
    if preferred_time_str:
        try:
            # Handle possible 'Z' offset or simple ISO
            clean_date = preferred_time_str.replace('Z', '+00:00')
            preferred_time = datetime.fromisoformat(clean_date)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid preferred time format'}), 400

    # Resolve IDs
    db_patient = user_repo.find_by_firebase_uid(user['uid'])
    db_doctor = user_repo.find_by_id(doctor_id)

    if not db_patient or not db_doctor:
        return jsonify({'success': False, 'message': 'Patient or Doctor not found'}), 404

    try:
        appointment = appointment_repo.create_appointment(
            patient_id=db_patient['id'],
            doctor_id=db_doctor['id'],
            notes=notes,
            preferred_time=preferred_time
        )

        # Notify Doctor
        notif_msg = f"Patient {db_patient['name']} has requested an appointment."
        if preferred_time:
            time_str = preferred_time.strftime('%B %d, %Y at %I:%M %p')
            notif_msg += f" Suggested time: {time_str}"
            
        notif_repo.create_notification(
            user_id=db_doctor['id'],
            notification_type='APPOINTMENT_REQUESTED',
            title='New Appointment Request',
            message=notif_msg,
            related_id=appointment['id']
        )

        return jsonify({'success': True, 'appointment': appointment}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@appointment_bp.route('/patient', methods=['GET'])
def get_patient_appointments():
    user, err = _require_auth()
    if err: return err

    db_user = user_repo.find_by_firebase_uid(user['uid'])
    if not db_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    appointments = appointment_repo.get_patient_appointments(db_user['id'])
    return jsonify({'success': True, 'appointments': appointments})

@appointment_bp.route('/doctor', methods=['GET'])
def get_doctor_appointments():
    user, err = _require_auth()
    if err: return err

    if user.get('role') != 'DOCTOR':
        return jsonify({'success': False, 'message': 'Doctor access required'}), 403

    db_user = user_repo.find_by_firebase_uid(user['uid'])
    if not db_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    appointments = appointment_repo.get_doctor_appointments(db_user['id'])
    return jsonify({'success': True, 'appointments': appointments})

@appointment_bp.route('/<appointment_id>/status', methods=['PUT'])
def update_appointment_status(appointment_id):
    user, err = _require_auth()
    if err: return err

    data = request.get_json() or {}
    status = data.get('status') # ACCEPTED, REJECTED, etc.
    scheduled_at_str = data.get('scheduled_at') # ISO string
    doctor_notes = data.get('doctor_notes', '')

    db_user = user_repo.find_by_firebase_uid(user['uid'])
    appointment = appointment_repo.get_by_id(appointment_id)

    if not appointment:
        return jsonify({'success': False, 'message': 'Appointment not found'}), 404

    # Authorization Check (Only assigned doctor can update)
    if user.get('role') != 'DOCTOR' or appointment['doctor_id'] != db_user['id']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    updates = {'status': status, 'doctor_notes': doctor_notes}
    if scheduled_at_str:
        try:
            # Handle possible 'Z' offset or simple ISO
            clean_date = scheduled_at_str.replace('Z', '+00:00')
            updates['scheduled_at'] = datetime.fromisoformat(clean_date)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    try:
        updated = appointment_repo.update_appointment(appointment_id, updates)

        # Notify Patient
        notif_msg = f"Your appointment has been {status.lower()}."
        if updated['scheduled_at']:
            # Format time for message (simple approach)
            time_str = datetime.fromisoformat(updated['scheduled_at']).strftime('%B %d, %Y at %I:%M %p')
            notif_msg += f" Scheduled for: {time_str}"

        notif_repo.create_notification(
            user_id=updated['patient_id'],
            notification_type='APPOINTMENT_ACCEPTED' if status == 'ACCEPTED' else 'SYSTEM_ALERT',
            title=f"Appointment {status.title()}",
            message=notif_msg,
            related_id=appointment_id
        )

        return jsonify({'success': True, 'appointment': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
