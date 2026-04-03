import uuid
from datetime import datetime
from sqlalchemy import or_, and_
from config.database import SessionLocal
from models.db_models import MedicalReport, ReportStatus, User


class MedicalReportRepository:

    def _to_dict(self, report: MedicalReport) -> dict:
        return {
            'id': report.id,
            'patient_id': report.patient_id,
            'assigned_doctor_id': report.assigned_doctor_id,
            'file_name': report.file_name,
            'file_path': report.file_path,
            'file_type': report.file_type,
            'file_size': report.file_size,
            'status': report.status.value if report.status else 'PENDING',
            'medical_specialty': report.medical_specialty,
            'suggested_doctors': report.suggested_doctors or [],
            'ai_analysis': report.ai_analysis,
            'doctor_notes': report.doctor_notes,
            'error_message': report.error_message,
            'uploaded_at': report.uploaded_at.isoformat() + 'Z' if report.uploaded_at else None,
            'analyzed_at': report.analyzed_at.isoformat() + 'Z' if report.analyzed_at else None,
            'assigned_at': report.assigned_at.isoformat() + 'Z' if report.assigned_at else None,
            'reviewed_at': report.reviewed_at.isoformat() + 'Z' if report.reviewed_at else None,
            'is_archived': report.is_archived,
            'doctor_edit_permission': report.doctor_edit_permission or False,
            'extracted_text': report.extracted_text,
        }

    def create_report(self, patient_id: str, file_name: str, file_path: str,
                      file_type: str, file_size: str, file_content: bytes = None) -> dict:
        with SessionLocal() as session:
            report = MedicalReport(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                file_name=file_name,
                file_path=file_path,
                file_type=file_type,
                file_size=file_size,
                file_content=file_content,
                status=ReportStatus.PENDING,
                uploaded_at=datetime.utcnow(),
            )
            session.add(report)
            session.commit()
            session.refresh(report)
            return self._to_dict(report)

    def find_by_id(self, report_id: str) -> dict | None:
        with SessionLocal() as session:
            report = session.query(MedicalReport).filter_by(id=report_id).first()
            return self._to_dict(report) if report else None

    def find_by_patient_id(self, firebase_uid: str) -> list[dict]:
        from repositories.user_repository import UserRepository
        user = UserRepository().find_by_firebase_uid(firebase_uid)
        if not user:
            return []
        with SessionLocal() as session:
            reports = (session.query(MedicalReport)
                       .filter_by(patient_id=user['id'])
                       .order_by(MedicalReport.uploaded_at.desc())
                       .all())
            return [self._to_dict(r) for r in reports]

    def find_by_doctor_id(self, firebase_uid: str) -> list[dict]:
        from repositories.user_repository import UserRepository
        user = UserRepository().find_by_firebase_uid(firebase_uid)
        if not user:
            return []
        with SessionLocal() as session:
            reports = (session.query(MedicalReport)
                       .filter_by(assigned_doctor_id=user['id'])
                       .order_by(MedicalReport.uploaded_at.desc())
                       .all())
            return [self._to_dict(r) for r in reports]

    def get_all_reports(self) -> list[dict]:
        with SessionLocal() as session:
            reports = session.query(MedicalReport).order_by(MedicalReport.uploaded_at.desc()).all()
            return [self._to_dict(r) for r in reports]

    def get_unassigned_reports(self) -> list[dict]:
        with SessionLocal() as session:
            reports = (session.query(MedicalReport)
                       .filter(
                           MedicalReport.assigned_doctor_id.is_(None),
                           MedicalReport.status.notin_([ReportStatus.FAILED])
                       )
                       .order_by(MedicalReport.uploaded_at.desc())
                       .all())
            return [self._to_dict(r) for r in reports]

    def update_report(self, report_id: str, updates: dict) -> dict:
        with SessionLocal() as session:
            report = session.query(MedicalReport).filter_by(id=report_id).first()
            if not report:
                raise ValueError(f"Report {report_id} not found")
            for key, value in updates.items():
                if key == 'status':
                    if isinstance(value, str):
                        value = ReportStatus[value.upper()]
                    setattr(report, key, value)
                elif hasattr(report, key):
                    setattr(report, key, value)
            session.commit()
            session.refresh(report)
            return self._to_dict(report)

    def update_ai_analysis(self, report_id: str, ai_analysis: dict, extracted_text: str = None) -> dict:
        with SessionLocal() as session:
            report = session.query(MedicalReport).filter_by(id=report_id).first()
            if not report:
                raise ValueError(f"Report {report_id} not found")
            report.ai_analysis = ai_analysis
            if extracted_text:
                report.extracted_text = extracted_text
            report.status = ReportStatus.ANALYZED
            report.analyzed_at = datetime.utcnow()
            session.commit()
            session.refresh(report)
            return self._to_dict(report)

    def assign_doctor(self, report_id: str, doctor_firebase_uid: str) -> dict:
        from repositories.user_repository import UserRepository
        doctor = UserRepository().find_by_firebase_uid(doctor_firebase_uid)
        if not doctor:
            raise ValueError(f"Doctor with firebase_uid {doctor_firebase_uid} not found")
        with SessionLocal() as session:
            report = session.query(MedicalReport).filter_by(id=report_id).first()
            if not report:
                raise ValueError(f"Report {report_id} not found")
            report.assigned_doctor_id = doctor['id']
            report.assigned_at = datetime.utcnow()
            session.commit()
            session.refresh(report)
            return self._to_dict(report)

    def archive_report(self, report_id: str, is_archived: bool) -> dict:
        return self.update_report(report_id, {'is_archived': is_archived})

    def delete_report(self, report_id: str) -> bool:
        with SessionLocal() as session:
            report = session.query(MedicalReport).filter_by(id=report_id).first()
            if not report:
                return False
            session.delete(report)
            session.commit()
            return True

    def get_file_content(self, report_id: str) -> bytes | None:
        with SessionLocal() as session:
            report = session.query(MedicalReport).filter_by(id=report_id).first()
            return report.file_content if report else None

    # ── AI Chat methods ──────────────────────────────────────────────────
    def create_ai_chat_message(self, report_id: str, role: str, content: str) -> dict:
        from models.db_models import MedicalReportAIChat
        with SessionLocal() as session:
            msg = MedicalReportAIChat(
                id=str(uuid.uuid4()),
                report_id=report_id,
                role=role,
                content=content,
                timestamp=datetime.utcnow()
            )
            session.add(msg)
            session.commit()
            session.refresh(msg)
            return {
                'id': msg.id,
                'report_id': msg.report_id,
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat() + 'Z'
            }

    def get_ai_chat_history(self, report_id: str) -> list[dict]:
        from models.db_models import MedicalReportAIChat
        with SessionLocal() as session:
            messages = (session.query(MedicalReportAIChat)
                        .filter_by(report_id=report_id)
                        .order_by(MedicalReportAIChat.timestamp.asc())
                        .all())
            return [{
                'id': m.id,
                'report_id': m.report_id,
                'role': m.role,
                'content': m.content,
                'timestamp': m.timestamp.isoformat() + 'Z'
            } for m in messages]
