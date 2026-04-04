import os
import sys

# Ensure current directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import create_app

# Vercel's Python runtime searches for a top-level variable named 'app' or 'application'.
# We avoid try-except blocks during the initial app assignment to satisfy static-analysis checks.
app, _socketio = create_app()

# For maximum WSGI compatibility
application = app
