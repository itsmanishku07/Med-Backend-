from flask import Blueprint, request, jsonify
from utils.auth_utils import get_current_user
from repositories.user_repository import UserRepository
from services.log_analyzer import LogAnalyzer
import os

logs_bp = Blueprint('logs', __name__)
user_repo = UserRepository()


def _require_admin():
    """Require admin authentication"""
    user = get_current_user()
    if not user:
        return None, (jsonify({'success': False, 'message': 'Authentication required'}), 401)
    
    db_user = user_repo.find_by_firebase_uid(user['uid'])
    if not db_user or db_user['role'] != 'ADMIN':
        return None, (jsonify({'success': False, 'message': 'Admin access required'}), 403)
    
    return user, None


# Add CORS preflight handler for all routes
@logs_bp.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@logs_bp.route('/statistics', methods=['GET'])
def get_log_statistics():
    """Get log statistics for admin dashboard"""
    user, err = _require_admin()
    if err:
        return err
    
    hours = int(request.args.get('hours', 24))
    
    analyzer = LogAnalyzer()
    stats = analyzer.get_statistics(hours=hours)
    
    # Return stats even if logging is disabled (to show historical data)
    return jsonify({
        'success': True,
        'statistics': stats,
        'hours': hours,
        'logging_enabled': os.getenv('ENABLE_FILE_LOGGING', 'false').lower() == 'true'
    })


@logs_bp.route('/list', methods=['GET'])
def get_logs():
    """Get paginated logs with filtering"""
    user, err = _require_admin()
    if err:
        return err
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 100))
    level = request.args.get('level')
    search = request.args.get('search')
    hours = int(request.args.get('hours', 24))
    
    analyzer = LogAnalyzer()
    result = analyzer.get_logs_paginated(
        page=page,
        per_page=per_page,
        level=level,
        search=search,
        hours=hours
    )
    
    # Format logs for frontend
    formatted_logs = []
    for log in result['logs']:
        formatted_logs.append({
            'timestamp': log['timestamp'].isoformat(),
            'level': log['level'],
            'type': log['type'],
            'message': log['raw'],
            'data': log['data']
        })
    
    return jsonify({
        'success': True,
        'logs': formatted_logs,
        'pagination': {
            'total': result['total'],
            'page': result['page'],
            'per_page': result['per_page'],
            'total_pages': result['total_pages']
        },
        'logging_enabled': os.getenv('ENABLE_FILE_LOGGING', 'false').lower() == 'true'
    })


@logs_bp.route('/download', methods=['GET'])
def download_logs():
    """Download log file"""
    user, err = _require_admin()
    if err:
        return err
    
    log_file_path = os.getenv('LOG_FILE_PATH', 'logs/app.log')
    
    if not os.path.exists(log_file_path):
        return jsonify({
            'success': False,
            'message': 'Log file not found'
        }), 404
    
    from flask import send_file
    return send_file(log_file_path, as_attachment=True, download_name='app.log')


@logs_bp.route('/clear', methods=['DELETE', 'OPTIONS'])
def clear_logs():
    """Clear/delete log file"""
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    user, err = _require_admin()
    if err:
        return err
    
    log_file_path = os.getenv('LOG_FILE_PATH', 'logs/app.log')
    
    try:
        # Clear the log file by opening it in write mode and truncating
        if os.path.exists(log_file_path):
            with open(log_file_path, 'w') as f:
                f.write('')
            
            # Log the action only if logging is enabled
            if os.getenv('ENABLE_FILE_LOGGING', 'false').lower() == 'true':
                from utils.logger import log_info
                log_info('Log file cleared by admin', {
                    'admin_email': user.get('email'),
                    'admin_uid': user.get('uid')
                })
            
            return jsonify({
                'success': True,
                'message': 'Log file cleared successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Log file not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to clear log file: {str(e)}'
        }), 500


@logs_bp.route('/settings', methods=['GET', 'OPTIONS'])
def get_log_settings():
    """Get current log settings"""
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    user, err = _require_admin()
    if err:
        return err
    
    enabled = os.getenv('ENABLE_FILE_LOGGING', 'false').lower() == 'true'
    
    return jsonify({
        'success': True,
        'settings': {
            'enabled': enabled,
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'log_file_path': os.getenv('LOG_FILE_PATH', 'logs/app.log')
        }
    })


@logs_bp.route('/settings', methods=['PUT', 'OPTIONS'])
def update_log_settings():
    """Update log settings in .env file"""
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    user, err = _require_admin()
    if err:
        return err
    
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    try:
        from dotenv import set_key
        
        env_file_path = '.env'
        
        # Update the setting using dotenv's set_key function
        set_key(env_file_path, 'ENABLE_FILE_LOGGING', 'true' if enabled else 'false')
        
        # Update the environment variable for current process
        os.environ['ENABLE_FILE_LOGGING'] = 'true' if enabled else 'false'
        
        # Reload dotenv to ensure all changes are picked up
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        # Log the action
        from utils.logger import log_info
        log_info(f'Log settings updated by admin: enabled={enabled}', {
            'admin_email': user.get('email'),
            'admin_uid': user.get('uid'),
            'enabled': enabled
        })
        
        return jsonify({
            'success': True,
            'message': f'Logging {"enabled" if enabled else "disabled"} successfully. Changes will take effect immediately.',
            'settings': {
                'enabled': enabled,
                'log_level': os.getenv('LOG_LEVEL', 'INFO'),
                'log_file_path': os.getenv('LOG_FILE_PATH', 'logs/app.log')
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to update settings: {str(e)}'
        }), 500
