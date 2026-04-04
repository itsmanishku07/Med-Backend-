from app import create_app

# Create the app instance for Vercel's Python runtime
# Vercel looks for 'app' or 'application' in the entry point file
app, socketio = create_app()

# Note: In Vercel serverless functions, the app instance 'app' is used by the runtime.
# socketio.run() is not needed and will not work here.
