"""
Vercel Serverless Function entry point for Campus Voice Flask application.
Discovered and executed automatically by Vercel's Python runtime.
"""
import os
import sys

# Ensure the project root is in the Python search path so 'app' package can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import create_app

# Top-level WSGI application instance required by Vercel
app = create_app()

if __name__ == "__main__":
    app.run()
