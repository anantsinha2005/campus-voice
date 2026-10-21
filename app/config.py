import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
basedir = Path(__file__).resolve().parent.parent
load_dotenv(basedir / '.env')


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-secret-key-change-in-production')
    
    # Database Configuration (Ensures consistent absolute path across all working directories)
    INSTANCE_DIR = basedir / 'instance'
    INSTANCE_DIR.mkdir(exist_ok=True)
    
    default_db_path = f"sqlite:///{ (INSTANCE_DIR / 'feedback.db').as_posix() }"
    env_db = os.environ.get('DATABASE_URL')
    if env_db and not env_db.endswith('feedback.db'):
        SQLALCHEMY_DATABASE_URI = env_db
    else:
        SQLALCHEMY_DATABASE_URI = default_db_path
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
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
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', None)
    ADMIN_DEPARTMENT = os.environ.get('ADMIN_DEPARTMENT', 'Administration')


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'
