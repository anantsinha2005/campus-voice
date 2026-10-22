import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
basedir = Path(__file__).resolve().parent.parent
load_dotenv(basedir / '.env')


class Config:
    """Base application configuration for Campus Voice using MongoDB."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-secret-key-change-in-production')

    # MongoDB Configuration
    # Uses MONGODB_URI environment variable (e.g. MongoDB Atlas connection string)
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/campus_voice')
    MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'campus_voice')

    # Security and Session Cookie Settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1')
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1')
    WTF_CSRF_ENABLED = True

    # Administrator Configuration via Environment
    ADMIN_NAME = os.environ.get('ADMIN_NAME', 'System Administrator')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@university.edu')
    # No hardcoded password fallback: must be configured securely
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', None)
    ADMIN_DEPARTMENT = os.environ.get('ADMIN_DEPARTMENT', 'Administration')


class TestingConfig(Config):
    """Testing configuration using mongomock in-memory database."""
    TESTING = True
    MONGODB_URI = 'mongomock://localhost/campus_voice_test'
    MONGODB_DB_NAME = 'campus_voice_test'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'
