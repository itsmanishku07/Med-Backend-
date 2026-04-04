import os
import sys

# Ensure current directory is in sys.path
sys.path.append(os.path.dirname(__file__))

from app import create_app

# Vercel's Python runtime searches for a top-level variable named 'app' or 'application'.
# If 'create_app()' fails during build, it may report 'top-level app not found'.
try:
    _app, _socketio = create_app()
    app = _app
    application = _app
except Exception as e:
    # This will help capture errors in the Vercel Build logs
    print(f"FAILED TO INITIALIZE APP: {e}")
    # Still define a dummy app to prevent the build error if possible
    from flask import Flask
    app = Flask(__name__)
    application = app
