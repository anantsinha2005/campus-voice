"""
Vercel Serverless Function Entry Point for Campus Voice.
Discovered automatically by Vercel's Python runtime.
"""
import os
import sys

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Expose the Flask WSGI app instance
from index import app
