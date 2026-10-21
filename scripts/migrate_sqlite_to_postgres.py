"""
Campus Voice - SQLite to PostgreSQL Data Migration Tool
Transfers all users, faculties, courses, and feedback records from local SQLite 
into a persistent PostgreSQL database without modifying the SQLite source.
"""
import os
import sys
import sqlite3
import argparse
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.models import db, User, Course, Faculty, Feedback
from app import create_app


def migrate(sqlite_path: str, postgres_url: str):
    """Safely migrates data from SQLite to PostgreSQL."""
    if not os.path.exists(sqlite_path):
        print(f"[ERROR] Source SQLite database not found at: {sqlite_path}", file=sys.stderr)
        return False

    # Normalize postgres:// to postgresql://
    if postgres_url.startswith("postgres://"):
        postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)

    print("=" * 70)
    print(" Campus Voice - SQLite -> PostgreSQL Migration")
    print(f" Source SQLite:     {sqlite_path}")
    print(f" Target PostgreSQL: {postgres_url.split('@')[-1] if '@' in postgres_url else 'configured'}")
    print("=" * 70)

    # 1. Read records from SQLite in Read-Only mode
    sqlite_uri = f"file:{Path(sqlite_path).as_posix()}?mode=ro"
    src_conn = sqlite3.connect(sqlite_uri, uri=True)
    src_conn.row_factory = sqlite3.Row

    src_faculties = src_conn.execute("SELECT * FROM faculties ORDER BY id;").fetchall()
    src_courses = src_conn.execute("SELECT * FROM courses ORDER BY id;").fetchall()
    src_users = src_conn.execute("SELECT * FROM users ORDER BY id;").fetchall()
    src_feedbacks = src_conn.execute("SELECT * FROM feedbacks ORDER BY id;").fetchall()
    src_conn.close()

    print(f"[*] Read from SQLite:")
    print(f"    - Faculties: {len(src_faculties)}")
    print(f"    - Courses:   {len(src_courses)}")
    print(f"    - Users:     {len(src_users)}")
    print(f"    - Feedbacks: {len(src_feedbacks)}")

    # 2. Connect to PostgreSQL
    pg_engine = create_engine(postgres_url, pool_pre_ping=True)
    Session = sessionmaker(bind=pg_engine)
    session = Session()

    # 3. Create tables in PostgreSQL if not already present
    app = create_app()
    with app.app_context():
        # Set engine dynamically
        db.metadata.create_all(bind=pg_engine)
        print("[*] Verified PostgreSQL table schema.")

    # 4. Migrate Faculties
    for row in src_faculties:
        existing = session.query(Faculty).filter_by(id=row['id']).first()
        if not existing:
            fac = Faculty(
                id=row['id'],
                faculty_name=row['faculty_name'],
                department=row['department'],
                email=row['email'],
                is_active=bool(row['is_active'])
            )
            session.add(fac)
    session.flush()

    # 5. Migrate Courses
    for row in src_courses:
        existing = session.query(Course).filter_by(id=row['id']).first()
        if not existing:
            crs = Course(
                id=row['id'],
                course_name=row['course_name'],
                course_code=row['course_code'],
                department=row['department'],
                faculty_id=row['faculty_id'],
                is_active=bool(row['is_active'])
            )
            session.add(crs)
    session.flush()

    # 6. Migrate Users
    for row in src_users:
        existing = session.query(User).filter_by(id=row['id']).first()
        if not existing:
            usr = User(
                id=row['id'],
                name=row['name'],
                email=row['email'],
                student_id=row['student_id'],
                department=row['department'],
                password_hash=row['password_hash'],
                role=row['role'],
                is_active=bool(row['is_active'])
            )
            session.add(usr)
    session.flush()

    # 7. Migrate Feedbacks
    for row in src_feedbacks:
        existing = session.query(Feedback).filter_by(id=row['id']).first()
        if not existing:
            fb = Feedback(
                id=row['id'],
                student_id=row['student_id'],
                faculty_id=row['faculty_id'],
                course_id=row['course_id'],
                rating=row['rating'],
                comments=row['comments']
            )
            session.add(fb)
    session.commit()

    # 8. Reset PostgreSQL sequences so auto-increment works for new records
    tables = ['users', 'faculties', 'courses', 'feedbacks']
    for tbl in tables:
        try:
            session.execute(text(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), coalesce(max(id), 1)) FROM {tbl};"))
            session.commit()
        except Exception as e:
            session.rollback()
            # Non-fatal if sequence does not match default naming

    # 9. Verify target counts
    pg_faculties = session.query(Faculty).count()
    pg_courses = session.query(Course).count()
    pg_users = session.query(User).count()
    pg_feedbacks = session.query(Feedback).count()
    session.close()

    print("\n" + "=" * 70)
    print(" [SUCCESS] PostgreSQL Migration Completed Successfully!")
    print(f" Target PostgreSQL State:")
    print(f"    - Faculties: {pg_faculties}")
    print(f"    - Courses:   {pg_courses}")
    print(f"    - Users:     {pg_users}")
    print(f"    - Feedbacks: {pg_feedbacks}")
    print("=" * 70)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Migrate Campus Voice SQLite database to PostgreSQL.")
    parser.add_argument("--sqlite-path", default=str(project_root / 'instance' / 'feedback.db'),
                        help="Path to source SQLite database (default: instance/feedback.db)")
    parser.add_argument("--postgres-url", default=os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL'),
                        help="Target PostgreSQL connection URL (e.g. postgresql://user:pass@host/db)")

    args = parser.parse_args()

    if not args.postgres_url:
        print("[ERROR] Please provide --postgres-url or set DATABASE_URL environment variable.", file=sys.stderr)
        sys.exit(1)

    success = migrate(args.sqlite_path, args.postgres_url)
    sys.exit(0 if success else 1)
