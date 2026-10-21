import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
basedir = Path(__file__).resolve().parent.parent
load_dotenv(basedir / '.env')


def is_writable_dir(directory: Path) -> bool:
    """Checks if a directory exists and is writable."""
    try:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
        test_file = directory / '.write_probe'
        test_file.touch(exist_ok=True)
        test_file.unlink(missing_ok=True)
        return True
    except OSError:
        return False


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-secret-key-change-in-production')
    
    # Instance Directory Handling
    # Detects serverless / read-only filesystem (e.g. AWS Lambda / Vercel)
    local_instance_dir = basedir / 'instance'
    is_serverless = (
        os.environ.get('VERCEL') in ('1', 'true', 'True')
        or os.environ.get('VERCEL_ENV') is not None
        or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
        or not is_writable_dir(local_instance_dir)
    )

    if is_serverless:
        INSTANCE_DIR = Path('/tmp') / 'instance'
        try:
            INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    else:
        INSTANCE_DIR = local_instance_dir
    
    # Database Configuration
    # Supports DATABASE_URL or POSTGRES_URL (e.g. Vercel Postgres, Supabase, Neon)
    env_db = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    if env_db and (env_db.startswith('postgresql://') or env_db.startswith('postgres://')):
        # SQLAlchemy 1.4+ / 2.0+ requires 'postgresql://' instead of legacy 'postgres://'
        if env_db.startswith('postgres://'):
            env_db = env_db.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = env_db
    elif env_db and not env_db.endswith('feedback.db') and not env_db.startswith('sqlite:///'):
        SQLALCHEMY_DATABASE_URI = env_db
    else:
        # Default SQLite path: in serverless environments, store in writable /tmp
        if is_serverless:
            tmp_db = Path('/tmp') / 'feedback.db'
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_db.as_posix()}"
        else:
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{ (INSTANCE_DIR / 'feedback.db').as_posix() }"
            
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
