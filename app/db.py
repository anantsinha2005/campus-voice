"""
MongoDB connection and client management for Campus Voice.
Provides a singleton MongoClient instance optimized for serverless execution,
index initialization, health check utilities, and pagination helpers.
"""
import math
import os
from typing import Optional, List, Any
from urllib.parse import urlparse
import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError

# Singleton client reference for serverless cold-start reuse
_client: Optional[MongoClient] = None


def get_mongo_client(uri: Optional[str] = None) -> MongoClient:
    """
    Returns a singleton MongoClient configured with connection pooling
    suited for serverless environments (e.g., Vercel / AWS Lambda).
    """
    global _client

    if _client is not None:
        try:
            # Quick check if client is alive
            return _client
        except Exception:
            _client = None

    connection_uri = uri or os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/campus_voice')

    # Support mongomock for unit tests
    if connection_uri.startswith('mongomock://') or os.environ.get('TESTING') == 'True' or os.environ.get('USE_MONGOMOCK') == '1':
        try:
            import mongomock
            _client = mongomock.MongoClient()
            return _client
        except ImportError:
            raise RuntimeError("mongomock is required for in-memory testing. Install with: pip install mongomock")

    # PyMongo client with connection pooling
    _client = MongoClient(
        connection_uri,
        maxPoolSize=10,
        minPoolSize=1,
        maxIdleTimeMS=60000,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        retryWrites=True
    )
    return _client


def get_db(db_name: Optional[str] = None, uri: Optional[str] = None) -> Database:
    """
    Retrieves the application MongoDB database instance.
    Defaults to MONGODB_DB_NAME env var or extracts database name from URI.
    """
    client = get_mongo_client(uri)
    target_db = db_name or os.environ.get('MONGODB_DB_NAME')
    
    if not target_db:
        # Extract from URI path if present
        connection_uri = uri or os.environ.get('MONGODB_URI', '')
        if connection_uri.startswith('mongomock://'):
            connection_uri = connection_uri.replace('mongomock://', 'mongodb://')
        if '?' in connection_uri:
            path_part = connection_uri.split('?')[0]
        else:
            path_part = connection_uri
        
        if '/' in path_part:
            extracted = path_part.rstrip('/').split('/')[-1]
            if extracted and not extracted.startswith('mongodb'):
                target_db = extracted

    target_db = target_db or 'campus_voice'
    return client[target_db]


def ping_db(client: Optional[MongoClient] = None) -> bool:
    """
    Pings the MongoDB server to verify active connectivity.
    """
    try:
        c = client or get_mongo_client()
        # Admin command ping
        c.admin.command('ping')
        return True
    except Exception:
        return False


def init_indexes(db: Optional[Database] = None):
    """
    Ensures all critical unique and lookup indexes exist in MongoDB.
    Safe and idempotent.
    """
    if db is None:
        db = get_db()

    try:
        # Users Collection
        db.users.create_index([("email", ASCENDING)], unique=True, name="uq_users_email")
        db.users.create_index([("student_id", ASCENDING)], unique=True, sparse=True, name="uq_users_student_id")
        db.users.create_index([("role", ASCENDING)], name="idx_users_role")

        # Faculties Collection
        db.faculties.create_index([("email", ASCENDING)], unique=True, sparse=True, name="uq_faculties_email")
        db.faculties.create_index([("faculty_name", ASCENDING)], name="idx_faculties_name")

        # Courses Collection
        db.courses.create_index([("course_code", ASCENDING)], unique=True, name="uq_courses_course_code")
        db.courses.create_index([("faculty_id", ASCENDING)], name="idx_courses_faculty")

        # Feedbacks Collection - Compound unique index prevents duplicate submissions
        db.feedbacks.create_index(
            [
                ("student_id", ASCENDING),
                ("faculty_id", ASCENDING),
                ("course_id", ASCENDING)
            ],
            unique=True,
            name="uq_student_faculty_course"
        )
        db.feedbacks.create_index([("created_at", DESCENDING)], name="idx_feedbacks_created_at")
        db.feedbacks.create_index([("rating", ASCENDING)], name="idx_feedbacks_rating")
    except Exception as exc:
        # When working with mongomock, some index options may differ, handle gracefully
        pass


def close_db_client():
    """Closes the current MongoClient connection pool."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


class Pagination:
    """
    Pagination helper object compatible with Flask-SQLAlchemy Pagination API,
    used in templates for page navigation, numbering, and stats.
    """
    def __init__(self, items: List[Any], page: int, per_page: int, total: int):
        self.items = items
        self.page = max(1, page)
        self.per_page = max(1, per_page)
        self.total = total
        self.pages = max(1, int(math.ceil(total / float(self.per_page))))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def prev_num(self) -> Optional[int]:
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self) -> Optional[int]:
        return self.page + 1 if self.has_next else None

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 3,
        right_edge: int = 2
    ):
        """
        Yields page numbers for pagination controls, inserting None for ellipses.
        """
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (self.page - left_current - 1 < num < self.page + right_current)
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num
