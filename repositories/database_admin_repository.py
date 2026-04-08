from typing import List, Dict, Any, Optional
from sqlalchemy import inspect, text, MetaData, Table
from sqlalchemy.orm import Session
from config.database import SessionLocal, engine
from models.db_models import MedicalReport
import os

class DatabaseAdminRepository:
    
    def get_all_tables(self) -> List[Dict[str, Any]]:
        """Get list of all tables with row counts"""
        with SessionLocal() as session:
            inspector = inspect(engine)
            tables = []
            
            for table_name in inspector.get_table_names():
                # Skip internal tables
                if table_name.startswith('_'):
                    continue
                
                # Get row count
                try:
                    result = session.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                    count = result.scalar()
                except:
                    count = 0
                
                tables.append({
                    'name': table_name,
                    'row_count': count
                })
            
            return sorted(tables, key=lambda x: x['name'])
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema information for a table"""
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        
        schema = []
        for col in columns:
            schema.append({
                'name': col['name'],
                'type': str(col['type']),
                'nullable': col['nullable'],
                'default': str(col['default']) if col['default'] else None,
                'primary_key': col.get('primary_key', False)
            })
        
        return schema
    
    def get_table_data(self, table_name: str, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """Get paginated data from a table"""
        with SessionLocal() as session:
            # Get total count
            count_result = session.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            total = count_result.scalar()
            
            # Get paginated data
            offset = (page - 1) * per_page
            query = text(f'SELECT * FROM "{table_name}" LIMIT :limit OFFSET :offset')
            result = session.execute(query, {'limit': per_page, 'offset': offset})
            
            # Convert to list of dicts
            columns = result.keys()
            rows = []
            for row in result:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # Convert non-serializable types
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    elif isinstance(value, bytes):
                        value = f"<binary data: {len(value)} bytes>"
                    elif value is None:
                        value = None
                    else:
                        value = str(value)
                    row_dict[col] = value
                rows.append(row_dict)
            
            return {
                'table_name': table_name,
                'columns': list(columns),
                'rows': rows,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
    
    def delete_record(self, table_name: str, record_id: str) -> bool:
        """Delete a specific record from a table"""
        with SessionLocal() as session:
            try:
                # Get primary key column name
                inspector = inspect(engine)
                pk_columns = inspector.get_pk_constraint(table_name)['constrained_columns']
                
                if not pk_columns:
                    raise ValueError(f"Table {table_name} has no primary key")
                
                pk_column = pk_columns[0]
                
                # Delete the record
                query = text(f'DELETE FROM "{table_name}" WHERE "{pk_column}" = :id')
                result = session.execute(query, {'id': record_id})
                session.commit()
                
                return result.rowcount > 0
            except Exception as e:
                session.rollback()
                raise e
    
    def clear_table(self, table_name: str) -> int:
        """Clear all records from a table"""
        with SessionLocal() as session:
            try:
                # Get count before deletion
                count_result = session.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                count = count_result.scalar()
                
                # Delete all records
                session.execute(text(f'DELETE FROM "{table_name}"'))
                session.commit()
                
                return count
            except Exception as e:
                session.rollback()
                raise e
    
    def delete_report_with_file(self, report_id: str) -> bool:
        """Delete a medical report and its associated file"""
        with SessionLocal() as session:
            try:
                # Get the report
                report = session.query(MedicalReport).filter(MedicalReport.id == report_id).first()
                
                if not report:
                    return False
                
                # Delete the file if it exists
                if report.file_path and os.path.exists(report.file_path):
                    try:
                        os.remove(report.file_path)
                        print(f"Deleted file: {report.file_path}")
                    except Exception as e:
                        print(f"Failed to delete file: {e}")
                
                # Delete the database record
                session.delete(report)
                session.commit()
                
                return True
            except Exception as e:
                session.rollback()
                raise e
    
    def delete_user_completely(self, user_id: str) -> Dict[str, Any]:
        """Delete a user from both database and Firebase"""
        from models.db_models import User
        from firebase_admin import auth as firebase_auth
        
        with SessionLocal() as session:
            try:
                # Get the user
                user = session.query(User).filter(User.id == user_id).first()
                
                if not user:
                    return {
                        'success': False,
                        'message': 'User not found in database'
                    }
                
                firebase_uid = user.firebase_uid
                user_email = user.email
                
                # Delete from Firebase first
                firebase_deleted = False
                firebase_error = None
                try:
                    firebase_auth.delete_user(firebase_uid)
                    firebase_deleted = True
                    print(f"Deleted user from Firebase: {firebase_uid}")
                except Exception as e:
                    firebase_error = str(e)
                    print(f"Failed to delete from Firebase: {e}")
                
                # Delete from database
                session.delete(user)
                session.commit()
                
                message = f"User {user_email} deleted from database"
                if firebase_deleted:
                    message += " and Firebase"
                elif firebase_error:
                    message += f" (Firebase deletion failed: {firebase_error})"
                
                return {
                    'success': True,
                    'message': message,
                    'deleted_from_db': True,
                    'deleted_from_firebase': firebase_deleted,
                    'firebase_error': firebase_error
                }
            except Exception as e:
                session.rollback()
                return {
                    'success': False,
                    'message': f'Failed to delete user: {str(e)}'
                }
