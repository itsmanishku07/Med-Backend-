import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def create_app():
    app = Flask(__name__)
    app.url_map.strict_slashes = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit for profile pictures and reports

    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')

    CORS(
        app,
        resources={r"/api/*": {"origins": cors_origins}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["2000 per day", "500 per hour"],
        storage_uri="memory://",
    )

    socketio = SocketIO(
        app,
        cors_allowed_origins=cors_origins,
        async_mode='threading',
        logger=False,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25,
        manage_session=False,   # we use Firebase tokens, not Flask sessions
    )

    # Initialize Firebase Admin SDK
    from config.firebase_config import init_firebase
    init_firebase()

    # Initialize PostgreSQL tables
    from config.database import init_db
    init_db()

    # Start medicine reminder push scheduler
    from services.reminder_scheduler import start_scheduler
    start_scheduler()

    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.medical_report_routes import medical_bp
    from routes.notification_routes import notification_bp
    from routes.chat_routes import chat_bp
    from routes.admin_routes import admin_bp
    from routes.medicine_reminder_routes import reminder_bp
    from routes.push_routes import push_bp
    from routes.appointment_routes import appointment_bp
    from routes.availability_routes import availability_bp
    from routes.review_routes import review_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(medical_bp, url_prefix='/api/medical-reports')
    app.register_blueprint(notification_bp, url_prefix='/api/notifications')
    app.register_blueprint(chat_bp, url_prefix='/api/chats')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(reminder_bp, url_prefix='/api/medicine-reminders')
    app.register_blueprint(push_bp, url_prefix='/api/push')
    app.register_blueprint(appointment_bp, url_prefix='/api/appointments')
    app.register_blueprint(availability_bp, url_prefix='/api/availability')
    app.register_blueprint(review_bp, url_prefix='/api/reviews')

    # Register SocketIO events
    from routes.chat_socket import register_socket_events
    register_socket_events(socketio)

    # Error handlers (all in app.py only)
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'success': False, 'message': str(e.description)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'success': False, 'message': 'Access forbidden'}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'success': False, 'message': 'Resource not found'}), 404

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({'success': False, 'message': f'Rate limit exceeded: {e.description}'}), 429

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({'success': False, 'message': 'File is too large. Please select an image under 16MB.'}), 413

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

    return app, socketio


if __name__ == '__main__':
    app, socketio = create_app()
    port = int(os.getenv('PORT', 8081))
    # use_reloader=False is critical — the reloader forks a second process
    # that breaks WebSocket handling in threading mode
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
