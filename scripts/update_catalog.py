import os
import sys
import sqlite3
from pathlib import Path

# Add project root to sys.path
basedir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(basedir))

from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback
from scripts.backup_database import backup_db

# Exact 6 required assignments
TARGET_ASSIGNMENTS = [
    ("BCO017A", "Formal Languages and Automation Theory", "Gajanand Sharma"),
    ("BCO023A", "Design and Analysis of Algorithms", "Sonal Saxena"),
    ("BCO037B", "Advance Programming in Java", "Neha Solanki"),
    ("BCO019A", "Artificial Intelligence", "Ankur Agrawal"),
    ("BCO074C", "Minor Project", "Mahesh Kumar Joshi"),
    ("BCO681A", "Web Designing Using AI", "Mohit Parashar")
]


def run_catalog_update():
    """
    Safely and idempotently migrates the database schema and updates
    course and faculty assignments while strictly preserving all historical
    feedback records, student accounts, and data integrity.
    """
    print("\n" + "=" * 70)
    print("STEP 1: CREATING VERIFIED PRE-MIGRATION DATABASE BACKUP")
    print("=" * 70)
    backup_path = backup_db()

    db_file = basedir / 'instance' / 'feedback.db'

    print("\n" + "=" * 70)
    print("STEP 2: RUNNING MINIMAL SCHEMA MIGRATIONS (IF NEEDED)")
    print("=" * 70)
    
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    # 1. Ensure courses table has faculty_id column
    cur.execute("PRAGMA table_info(courses);")
    course_cols = [c[1] for c in cur.fetchall()]
    if 'faculty_id' not in course_cols:
        print("[MIGRATE] Adding 'faculty_id' column to 'courses' table...")
        cur.execute("ALTER TABLE courses ADD COLUMN faculty_id INTEGER REFERENCES faculties(id);")
        print("[OK] Column 'faculty_id' added to courses.")
    else:
        print("[OK] Column 'faculty_id' already present in courses.")

    # 2. Ensure faculties table allows NULL email
    cur.execute("PRAGMA table_info(faculties);")
    fac_cols = cur.fetchall()
    # (cid, name, type, notnull, dflt_value, pk)
    email_col = next((c for c in fac_cols if c[1] == 'email'), None)
    if email_col and email_col[3] == 1:  # notnull is 1
        print("[MIGRATE] Migrating faculties table to allow NULL email addresses...")
        cur.execute("PRAGMA foreign_keys = OFF;")
        cur.execute("""
            CREATE TABLE faculties_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                faculty_name VARCHAR(150) NOT NULL,
                department VARCHAR(100) NOT NULL,
                email VARCHAR(120),
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_faculties_email UNIQUE (email)
            );
        """)
        cur.execute("""
            INSERT INTO faculties_new (id, faculty_name, department, email, is_active, created_at)
            SELECT id, faculty_name, department, email, is_active, created_at FROM faculties;
        """)
        cur.execute("DROP TABLE faculties;")
        cur.execute("ALTER TABLE faculties_new RENAME TO faculties;")
        cur.execute("PRAGMA foreign_keys = ON;")
        print("[OK] Faculties table migrated to allow NULL email.")
    else:
        print("[OK] Faculties table already supports NULL email.")

    # Verify foreign keys in SQLite
    cur.execute("PRAGMA foreign_key_check;")
    fk_errors = cur.fetchall()
    if fk_errors:
        conn.close()
        raise RuntimeError(f"Foreign key integrity check failed: {fk_errors}")
    print("[OK] Foreign key integrity verified. 0 errors.")

    conn.commit()
    conn.close()

    print("\n" + "=" * 70)
    print("STEP 3: UPDATING COURSE AND FACULTY CATALOG RECORDS")
    print("=" * 70)

    app = create_app(Config)
    with app.app_context():
        # Record initial metrics
        initial_feedback_count = Feedback.query.count()
        initial_user_count = User.query.count()

        target_codes = [a[0] for a in TARGET_ASSIGNMENTS]
        target_faculty_names = [a[2] for a in TARGET_ASSIGNMENTS]

        # 1. Archive/deactivate old sample courses to preserve historical feedback
        old_courses = Course.query.filter(~Course.course_code.in_(target_codes)).all()
        for c in old_courses:
            if c.is_active:
                c.is_active = False
                print(f"[ARCHIVE] Deactivated historical course: {c.course_code} - {c.course_name} (Preserving {c.feedbacks.count()} feedback records)")

        # 2. Archive/deactivate old sample faculty to preserve historical feedback
        old_faculty = Faculty.query.filter(~Faculty.faculty_name.in_(target_faculty_names)).all()
        for f in old_faculty:
            if f.is_active:
                f.is_active = False
                print(f"[ARCHIVE] Deactivated historical faculty: {f.faculty_name} (Preserving {f.feedbacks.count()} feedback records)")

        # 3. Create or update the 5 real assignments
        active_assignments_summary = []
        for code, subject_name, faculty_name in TARGET_ASSIGNMENTS:
            # Match or create faculty
            faculty = Faculty.query.filter_by(faculty_name=faculty_name).first()
            if not faculty:
                faculty = Faculty(
                    faculty_name=faculty_name,
                    department="Computer Science & Engineering",
                    email=None,
                    is_active=True
                )
                db.session.add(faculty)
                db.session.flush()
                print(f"[+] Created real faculty member: {faculty.faculty_name}")
            else:
                faculty.is_active = True
                faculty.department = "Computer Science & Engineering"
                print(f"[*] Reusing / updating faculty: {faculty.faculty_name}")

            # Match or create course
            course = Course.query.filter_by(course_code=code).first()
            if not course:
                course = Course(
                    course_code=code,
                    course_name=subject_name,
                    department="Computer Science & Engineering",
                    faculty_id=faculty.id,
                    is_active=True
                )
                db.session.add(course)
                db.session.flush()
                print(f"[+] Created real course: {course.course_code} - {course.course_name}")
            else:
                course.course_name = subject_name
                course.department = "Computer Science & Engineering"
                course.faculty_id = faculty.id
                course.is_active = True
                print(f"[*] Reusing / updating course: {course.course_code} - {course.course_name}")

            active_assignments_summary.append({
                "code": course.course_code,
                "subject": course.course_name,
                "faculty": faculty.faculty_name,
                "course_id": course.id,
                "faculty_id": faculty.id
            })

        db.session.commit()

        # Step 4: Verification of Data Integrity
        final_feedback_count = Feedback.query.count()
        final_user_count = User.query.count()
        active_courses_count = Course.query.filter_by(is_active=True).count()
        active_faculty_count = Faculty.query.filter_by(is_active=True).count()

        assert final_feedback_count == initial_feedback_count, f"Feedback count changed! Before: {initial_feedback_count}, After: {final_feedback_count}"
        assert final_user_count == initial_user_count, f"User count changed! Before: {initial_user_count}, After: {final_user_count}"
        assert active_courses_count == 6, f"Expected 6 active courses, got {active_courses_count}"
        assert active_faculty_count == 6, f"Expected 6 active faculty, got {active_faculty_count}"

        # Verify all foreign keys on existing feedbacks still resolve
        for fb in Feedback.query.all():
            assert fb.course is not None, f"Feedback #{fb.id} has broken course_id!"
            assert fb.faculty is not None, f"Feedback #{fb.id} has broken faculty_id!"
            assert fb.student is not None, f"Feedback #{fb.id} has broken student_id!"

        print("\n" + "=" * 70)
        print("MIGRATION COMPLETE & INTEGRITY VERIFIED")
        print("=" * 70)
        print(f"  Backup Created At: {backup_path}")
        print(f"  Total Courses: {Course.query.count()} ({active_courses_count} Active, {len(old_courses)} Archived Historical)")
        print(f"  Total Faculty: {Faculty.query.count()} ({active_faculty_count} Active, {len(old_faculty)} Archived Historical)")
        print(f"  Total Student Accounts: {final_user_count} (100% Intact)")
        print(f"  Total Feedback Records: {final_feedback_count} (100% Intact)")
        print("\nACTIVE ACADEMIC ASSIGNMENTS:")
        for idx, item in enumerate(active_assignments_summary, 1):
            print(f"  {idx}. {item['subject']} ({item['code']}) -> {item['faculty']}")
        print("=" * 70 + "\n")


if __name__ == '__main__':
    run_catalog_update()
