import logging
import os
import json
from logging.handlers import RotatingFileHandler
from datetime import datetime
from functools import wraps
from flask import request, g
import time

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


class AppLogger:
    _instance = None
    _logger = None
    _file_logging_enabled = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppLogger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self):
        """Initialize the logger with file and console handlers"""
        # Check if file logging is enabled
        self._file_logging_enabled = os.getenv('ENABLE_FILE_LOGGING', 'false').lower() == 'true'
        
        # Create logger
        self._logger = logging.getLogger('medreport_app')
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self._logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Prevent duplicate handlers
        if self._logger.handlers:
            return
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler (always enabled)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(detailed_formatter)
        self._logger.addHandler(console_handler)
        
        # File handler (only if enabled)
        if self._file_logging_enabled:
            log_file_path = os.getenv('LOG_FILE_PATH', 'logs/app.log')
            log_dir = os.path.dirname(log_file_path)
            
            # Create logs directory if it doesn't exist
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Rotating file handler
            max_bytes = int(os.getenv('LOG_MAX_BYTES', 10485760))  # 10MB default
            backup_count = int(os.getenv('LOG_BACKUP_COUNT', 5))
            
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            self._logger.addHandler(file_handler)
            
            self._logger.info(f"File logging enabled: {log_file_path}")
        else:
            self._logger.info("File logging disabled")

    def get_logger(self):
        """Get the logger instance"""
        return self._logger

    def is_file_logging_enabled(self):
        """Check if file logging is enabled"""
        return self._file_logging_enabled


# Global logger instance
app_logger = AppLogger()
logger = app_logger.get_logger()


def log_request(func):
    """Decorator to log API requests and responses"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not app_logger.is_file_logging_enabled():
            return func(*args, **kwargs)
        
        # Start time
        start_time = time.time()
        
        # Log request
        request_data = {
            'method': request.method,
            'path': request.path,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Get user info if available
        if hasattr(g, 'current_user') and g.current_user:
            request_data['user_id'] = g.current_user.get('uid')
            request_data['user_email'] = g.current_user.get('email')
        
        logger.info(f"REQUEST: {json.dumps(request_data)}")
        
        try:
            # Execute the function
            response = func(*args, **kwargs)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            status_code = response[1] if isinstance(response, tuple) else 200
            response_data = {
                'path': request.path,
                'status_code': status_code,
                'duration_ms': round(duration * 1000, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"RESPONSE: {json.dumps(response_data)}")
            
            return response
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            error_data = {
                'path': request.path,
                'error': str(e),
                'error_type': type(e).__name__,
                'duration_ms': round(duration * 1000, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
            logger.error(f"ERROR: {json.dumps(error_data)}", exc_info=True)
            raise
    
    return wrapper


def log_error(error, context=None):
    """Log an error with optional context"""
    error_data = {
        'error': str(error),
        'error_type': type(error).__name__,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if context:
        error_data['context'] = context
    
    logger.error(f"ERROR: {json.dumps(error_data)}", exc_info=True)


def log_info(message, data=None):
    """Log an info message with optional data"""
    log_data = {
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if data:
        log_data['data'] = data
    
    logger.info(f"INFO: {json.dumps(log_data)}")


def log_warning(message, data=None):
    """Log a warning message with optional data"""
    log_data = {
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if data:
        log_data['data'] = data
    
    logger.warning(f"WARNING: {json.dumps(log_data)}")
