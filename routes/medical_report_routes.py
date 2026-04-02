import os
import uuid
import threading
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from utils.auth_utils import get_current_user
from repositories.medical_report_repository import MedicalReportRepository
from repositories.user_repository import UserRepository
from repositories.notification_repository import NotificationRepository

medical_bp = Blueprint('medical_reports', __name__)
report_repo = MedicalReportRepository()
user_repo = UserRepository()
notif_repo = NotificationRepository()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _require_auth():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    return user, None


def _get_file_ext(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def _run_analysis_background(report_id: str, file_path: str, file_type: str,
                              patient_firebase_uid: str):
    """Background thread: analyze report and update DB."""
    from services.medical_ai_service import MedicalAIService
    from services.doctor_matching_service import DoctorMatchingService

    try:
        report_repo.update_report(report_id, {'status': 'ANALYZING'})

        with open(file_path, 'rb') as f:
            file_bytes = f.read()

        ai_service = MedicalAIService()
        ai_analysis, full_text = ai_service.analyze_report(file_bytes, file_type)

        # Doctor matching
        matching_service = DoctorMatchingService()
        specialty = matching_service.detect_medical_specialty(ai_analysis)
        doctors = user_repo.get_all_doctors()
        suggested = matching_service.match_doctors_to_report(ai_analysis, specialty, doctors)

        report_repo.update_ai_analysis(report_id, ai_analysis, full_text)
        report_repo.update_report(report_id, {
            'medical_specialty': specialty,
            'suggested_doctors': suggested,
        })

        ocr_score = ai_analysis.get('extraction_info', {}).get('ocr_quality_score', 1.0)
        if ocr_score < 0.5:
            notif_repo.create_notification(
                user_id=patient_firebase_uid,
                notification_type='SYSTEM_ALERT',
                title='OCR Quality Warning',
                message='Your report was analyzed but the text extraction quality was low. Consider uploading a clearer image.',
                related_id=report_id,
            )
        else:
            notif_repo.create_notification(
                user_id=patient_firebase_uid,
                notification_type='REPORT_ANALYZED',
                title='Report Analyzed',
                message='Your medical report has been successfully analyzed.',
                related_id=report_id,
            )
    except Exception as e:
        logger.error(f"Background analysis failed for report {report_id}: {e}")
        try:
            report_repo.update_report(report_id, {
                'status': 'FAILED',
                'error_message': str(e),
            })
            notif_repo.create_notification(
                user_id=patient_firebase_uid,
                notification_type='SYSTEM_ALERT',
                title='Report Analysis Failed',
                message=f'Analysis of your report failed: {str(e)[:200]}',
                related_id=report_id,
            )
        except Exception as inner:
            logger.error(f"Failed to update report status after error: {inner}")

@medical_bp.route('/my-reports', methods=['GET'])
def my_reports():
    user, err = _require_auth()
    if err:
        return err

    role = user.get('role', 'PATIENT')
    try:
        if role == 'PATIENT':
            reports = report_repo.find_by_patient_id(user['uid'])
            reports.sort(key=lambda r: r.get('uploaded_at') or '', reverse=True)
        elif role == 'DOCTOR':
            assigned = report_repo.find_by_doctor_id(user['uid'])
            assigned_ids = {r['id'] for r in assigned}

            # Unassigned reports matching doctor's specializations or suggested_doctors
            db_doctor = user_repo.find_by_firebase_uid(user['uid'])
            doctor_specs = [s.lower() for s in (db_doctor.get('specializations') or [])]
            doctor_db_id = db_doctor['id'] if db_doctor else None

            unassigned = report_repo.get_unassigned_reports()
            relevant_unassigned = []
            for r in unassigned:
                if r['id'] in assigned_ids:
                    continue
                specialty = (r.get('medical_specialty') or '').lower()
                suggested = r.get('suggested_doctors') or []
                suggested_ids = [s.get('doctor_id') for s in suggested if isinstance(s, dict)]

                spec_match = any(spec in specialty or specialty in spec for spec in doctor_specs)
                suggested_match = doctor_db_id in suggested_ids or user['uid'] in suggested_ids

                if spec_match or suggested_match:
                    relevant_unassigned.append(r)

            all_reports = assigned + relevant_unassigned
            seen = set()
            reports = []
            for r in all_reports:
                if r['id'] not in seen:
                    seen.add(r['id'])
                    reports.append(r)
            reports.sort(key=lambda r: r.get('uploaded_at') or '', reverse=True)
        else:
            # ADMIN
            reports = report_repo.get_all_reports()

        return jsonify({'success': True, 'reports': reports, 'count': len(reports)})
    except Exception as e:
        logger.error(f"my_reports error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@medical_bp.route('/stats', methods=['GET'])
def stats():
    user, err = _require_auth()
    if err:
        return err
    try:
        all_reports = report_repo.get_all_reports()
        total = len(all_reports)
        pending = sum(1 for r in all_reports if r.get('status') in ('PENDING', 'ANALYZING'))
        reviewed = sum(1 for r in all_reports if r.get('status') == 'REVIEWED')
        critical = sum(1 for r in all_reports
                       if r.get('ai_analysis') and
                       r['ai_analysis'].get('severity_level') == 'CRITICAL')
        return jsonify({'success': True, 'stats': {
            'totalReports': total,
            'pendingReports': pending,
            'reviewedReports': reviewed,
            'criticalAlerts': critical,
        }})
    except Exception:
        return jsonify({'success': True, 'stats': {
            'totalReports': 0, 'pendingReports': 0,
            'reviewedReports': 0, 'criticalAlerts': 0,
        }})


@medical_bp.route('/upload', methods=['POST'])
def upload_report():
    user, err = _require_auth()
    if err:
        return err

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    ext = _get_file_ext(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'success': False, 'message': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({'success': False, 'message': 'File too large. Max 10MB'}), 400

    # Resolve firebase_uid to db user id
    db_user = user_repo.find_by_firebase_uid(user['uid'])
    if not db_user:
        return jsonify({'success': False, 'message': 'User not found in database'}), 404

    # Save file
    upload_dir = os.path.join('uploads', user['uid'])
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)
    file.save(file_path)

    # Create report record
    try:
        report = report_repo.create_report(
            patient_id=db_user['id'],
            file_name=file.filename,
            file_path=file_path,
            file_type=ext,
            file_size=str(size),
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

    # Start background analysis thread
    t = threading.Thread(
        target=_run_analysis_background,
        args=(report['id'], file_path, ext, user['uid']),
        daemon=True,
    )
    t.start()

    return jsonify({'success': True, 'message': 'Report uploaded. Analysis started.', 'report': report}), 201


@medical_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id):
    user, err = _require_auth()
    if err:
        return err

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    role = user.get('role', 'PATIENT')
    db_user = user_repo.find_by_firebase_uid(user['uid'])
    db_id = db_user['id'] if db_user else None

    if role == 'PATIENT' and report['patient_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    if role == 'DOCTOR' and report['assigned_doctor_id'] != db_id and report['assigned_doctor_id'] is not None:
        # Allow access to unassigned reports too
        pass

    return jsonify({'success': True, 'report': report})


@medical_bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    user, err = _require_auth()
    if err:
        return err

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    role = user.get('role', 'PATIENT')
    db_user = user_repo.find_by_firebase_uid(user['uid'])
    db_id = db_user['id'] if db_user else None

    if role == 'PATIENT' and report['patient_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    if role == 'DOCTOR':
        return jsonify({'success': False, 'message': 'Doctors cannot delete reports'}), 403

    # Delete file from disk
    try:
        if os.path.exists(report['file_path']):
            os.remove(report['file_path'])
    except Exception:
        pass

    report_repo.delete_report(report_id)
    return jsonify({'success': True, 'message': 'Report deleted'})


@medical_bp.route('/<report_id>/analyze', methods=['POST'])
def analyze_report(report_id):
    user, err = _require_auth()
    if err:
        return err

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    role = user.get('role', 'PATIENT')
    db_user = user_repo.find_by_firebase_uid(user['uid'])
    db_id = db_user['id'] if db_user else None

    if role == 'PATIENT' and report['patient_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    if role == 'DOCTOR' and report['assigned_doctor_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    if not os.path.exists(report['file_path']):
        return jsonify({'success': False, 'message': 'Report file not found on disk'}), 404

    try:
        from services.medical_ai_service import MedicalAIService
        from services.doctor_matching_service import DoctorMatchingService

        report_repo.update_report(report_id, {'status': 'ANALYZING'})

        with open(report['file_path'], 'rb') as f:
            file_bytes = f.read()

        ai_service = MedicalAIService()
        ai_analysis, full_text = ai_service.analyze_report(file_bytes, report['file_type'])

        matching_service = DoctorMatchingService()
        specialty = matching_service.detect_medical_specialty(ai_analysis)
        doctors = user_repo.get_all_doctors()
        suggested = matching_service.match_doctors_to_report(ai_analysis, specialty, doctors)

        report_repo.update_ai_analysis(report_id, ai_analysis, full_text)
        updated = report_repo.update_report(report_id, {
            'medical_specialty': specialty,
            'suggested_doctors': suggested,
        })
        return jsonify({'success': True, 'message': 'Analysis complete', 'report': updated})
    except Exception as e:
        logger.error(f"analyze_report error: {e}")
        try:
            report_repo.update_report(report_id, {'status': 'FAILED', 'error_message': str(e)[:500]})
        except Exception:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500


@medical_bp.route('/<report_id>/assign-doctor', methods=['POST'])
def assign_doctor(report_id):
    user, err = _require_auth()
    if err:
        return err

    role = user.get('role', 'PATIENT')
    if role not in ('DOCTOR', 'ADMIN'):
        return jsonify({'success': False, 'message': 'Only doctors or admins can assign'}), 403

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    data = request.get_json() or {}
    doctor_firebase_uid = data.get('doctor_id') or user['uid']

    try:
        updated = report_repo.assign_doctor(report_id, doctor_firebase_uid)

        # Create chat if not exists
        from repositories.chat_repository import ChatRepository
        chat_repo = ChatRepository()
        existing_chat = chat_repo.find_by_report_id(report_id)
        if not existing_chat:
            doctor_db = user_repo.find_by_firebase_uid(doctor_firebase_uid)
            if doctor_db:
                try:
                    chat_repo.create_chat(
                        report_id=report_id,
                        patient_id=updated['patient_id'],
                        doctor_id=doctor_db['id'],
                    )
                except Exception:
                    pass  # Duplicate key — already exists

        # Notify patient
        notif_repo.create_notification(
            user_id=updated['patient_id'],
            notification_type='DOCTOR_ACCEPTED',
            title='Doctor Assigned',
            message='A doctor has been assigned to your report.',
            related_id=report_id,
        )
        return jsonify({'success': True, 'message': 'Doctor assigned', 'report': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@medical_bp.route('/<report_id>/review', methods=['POST'])
def review_report(report_id):
    user, err = _require_auth()
    if err:
        return err

    if user.get('role') != 'DOCTOR':
        return jsonify({'success': False, 'message': 'Only doctors can review reports'}), 403

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    db_user = user_repo.find_by_firebase_uid(user['uid'])
    if not db_user or report['assigned_doctor_id'] != db_user['id']:
        return jsonify({'success': False, 'message': 'You are not the assigned doctor'}), 403

    data = request.get_json() or {}
    notes = data.get('notes', '')

    try:
        updated = report_repo.update_report(report_id, {
            'doctor_notes': notes,
            'status': 'REVIEWED',
            'reviewed_at': datetime.utcnow(),
        })
        return jsonify({'success': True, 'message': 'Report reviewed', 'report': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@medical_bp.route('/<report_id>/archive', methods=['PUT'])
def archive_report(report_id):
    user, err = _require_auth()
    if err:
        return err

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    db_user = user_repo.find_by_firebase_uid(user['uid'])
    db_id = db_user['id'] if db_user else None
    role = user.get('role', 'PATIENT')

    if role == 'PATIENT' and report['patient_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    if role == 'DOCTOR' and report['assigned_doctor_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    data = request.get_json() or {}
    is_archived = bool(data.get('is_archived', False))

    try:
        updated = report_repo.archive_report(report_id, is_archived)
        return jsonify({'success': True, 'message': 'Archive status updated', 'report': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@medical_bp.route('/<report_id>/doctor-edit-permission', methods=['PUT'])
def set_doctor_edit_permission(report_id):
    user, err = _require_auth()
    if err:
        return err

    if user.get('role') != 'PATIENT':
        return jsonify({'success': False, 'message': 'Only patients can grant/revoke doctor edit permission'}), 403

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    db_user = user_repo.find_by_firebase_uid(user['uid'])
    if not db_user or report['patient_id'] != db_user['id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    data = request.get_json() or {}
    allow = bool(data.get('allow', False))

    try:
        updated = report_repo.update_report(report_id, {'doctor_edit_permission': allow})
        return jsonify({'success': True, 'message': 'Permission updated', 'report': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@medical_bp.route('/<report_id>/ai-analysis', methods=['PUT'])
def update_ai_analysis(report_id):
    user, err = _require_auth()
    if err:
        return err

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    db_user = user_repo.find_by_firebase_uid(user['uid'])
    db_id = db_user['id'] if db_user else None
    role = user.get('role', 'PATIENT')

    if role == 'PATIENT' and report['patient_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    if role == 'DOCTOR' and report['assigned_doctor_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    if role == 'DOCTOR' and not report.get('doctor_edit_permission', False):
        return jsonify({'success': False, 'message': 'Patient has not granted edit permission'}), 403

    data = request.get_json() or {}
    ai_analysis = data.get('ai_analysis')
    if ai_analysis is None:
        return jsonify({'success': False, 'message': 'ai_analysis is required'}), 400

    try:
        updated = report_repo.update_report(report_id, {'ai_analysis': ai_analysis})
        return jsonify({'success': True, 'message': 'AI analysis updated', 'report': updated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@medical_bp.route('/<report_id>/ai-chat', methods=['GET'])
def get_ai_chat_history(report_id):
    user, err = _require_auth()
    if err: return err

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    # Authorization Check
    db_user = user_repo.find_by_firebase_uid(user['uid'])
    db_id = db_user['id'] if db_user else None
    if user.get('role') == 'PATIENT' and report['patient_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    history = report_repo.get_ai_chat_history(report_id)
    return jsonify({'success': True, 'history': history})


@medical_bp.route('/<report_id>/ask', methods=['POST'])
def ask_ai_question(report_id):
    user, err = _require_auth()
    if err: return err

    data = request.get_json() or {}
    question = data.get('question')
    if not question:
        return jsonify({'success': False, 'message': 'Question is required'}), 400

    report = report_repo.find_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': 'Report not found'}), 404

    # Authorization Check
    db_user = user_repo.find_by_firebase_uid(user['uid'])
    db_id = db_user['id'] if db_user else None
    if user.get('role') == 'PATIENT' and report['patient_id'] != db_id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    try:
        from services.medical_ai_service import MedicalAIService
        ai_service = MedicalAIService()

        # Get context
        context = report.get('extracted_text') or ""
        if not context and report.get('ai_analysis'):
             # Fallback to summary if full text not available
             context = report['ai_analysis'].get('summary', "")

        # Get history
        history = report_repo.get_ai_chat_history(report_id)

        # Save user message
        user_msg = report_repo.create_ai_chat_message(report_id, 'user', question)

        # Get AI answer
        answer = ai_service.ask_question_about_report(context, history, question)

        # Save AI message
        ai_msg = report_repo.create_ai_chat_message(report_id, 'assistant', answer)

        return jsonify({
            'success': True,
            'question': user_msg,
            'answer': ai_msg
        })
    except Exception as e:
        logger.error(f"ask_ai_question error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
