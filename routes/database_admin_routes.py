from flask import Blueprint, request, jsonify
from utils.auth_utils import get_current_user
from repositories.database_admin_repository import DatabaseAdminRepository

database_admin_bp = Blueprint('database_admin', __name__)
db_admin_repo = DatabaseAdminRepository()

def _require_admin():
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    if user.get('role') != 'ADMIN':
        return None, (jsonify({'success': False, 'message': 'Admin access required'}), 403)
    return user, None

@database_admin_bp.route('/tables', methods=['GET'])
def get_all_tables():
    """Get list of all database tables with row counts"""
    user, err = _require_admin()
    if err: return err
    
    try:
        tables = db_admin_repo.get_all_tables()
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@database_admin_bp.route('/tables/<table_name>', methods=['GET'])
def get_table_data(table_name):
    """Get data from a specific table with pagination"""
    user, err = _require_admin()
    if err: return err
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    try:
        data = db_admin_repo.get_table_data(table_name, page, per_page)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@database_admin_bp.route('/tables/<table_name>/record/<record_id>', methods=['DELETE'])
def delete_record(table_name, record_id):
    """Delete a specific record from a table"""
    user, err = _require_admin()
    if err: return err
    
    try:
        result = db_admin_repo.delete_record(table_name, record_id)
        if result:
            return jsonify({'success': True, 'message': f'Record deleted from {table_name}'})
        else:
            return jsonify({'success': False, 'message': 'Record not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@database_admin_bp.route('/tables/<table_name>/clear', methods=['DELETE'])
def clear_table(table_name):
    """Clear all records from a table"""
    user, err = _require_admin()
    if err: return err
    
    # Require confirmation
    confirm = request.args.get('confirm', '').lower()
    if confirm != 'yes':
        return jsonify({
            'success': False, 
            'message': 'Confirmation required. Add ?confirm=yes to the request'
        }), 400
    
    try:
        count = db_admin_repo.clear_table(table_name)
        return jsonify({
            'success': True, 
            'message': f'Cleared {count} records from {table_name}',
            'deleted_count': count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@database_admin_bp.route('/reports/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    """Delete a medical report and its file"""
    user, err = _require_admin()
    if err: return err
    
    try:
        result = db_admin_repo.delete_report_with_file(report_id)
        if result:
            return jsonify({'success': True, 'message': 'Report deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Report not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@database_admin_bp.route('/tables/<table_name>/schema', methods=['GET'])
def get_table_schema(table_name):
    """Get schema information for a table"""
    user, err = _require_admin()
    if err: return err
    
    try:
        schema = db_admin_repo.get_table_schema(table_name)
        return jsonify({'success': True, 'schema': schema})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@database_admin_bp.route('/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user from both database and Firebase"""
    user, err = _require_admin()
    if err: return err
    
    try:
        result = db_admin_repo.delete_user_completely(user_id)
        if result['success']:
            return jsonify({
                'success': True, 
                'message': result['message'],
                'deleted_from_db': result['deleted_from_db'],
                'deleted_from_firebase': result['deleted_from_firebase']
            })
        else:
            return jsonify({'success': False, 'message': result['message']}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
