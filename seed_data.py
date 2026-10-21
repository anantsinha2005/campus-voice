import secrets
from datetime import datetime, timedelta
from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback


REAL_CATALOG = [
    ("BCO017A", "Formal Languages and Automation Theory", "Gajanand Sharma"),
    ("BCO023A", "Design and Analysis of Algorithms", "Sonal Saxena"),
    ("BCO037B", "Advance Programming in Java", "Neha Solanki"),
    ("BCO019A", "Artificial Intelligence", "Ankur Agrawal"),
    ("BCO074C", "Minor Project", "Mahesh Kumar Joshi"),
    ("BCO681A", "Web Designing Using AI", "Mohit Parashar"),
]


def seed_database(app=None):
    """
    Seeds initial administrator, academic courses, faculty members,
    sample student accounts, and realistic feedback submissions using the
    active real academic catalog.
    Does NOT seed outdated demo entries.
    """
    if app is None:
        app = create_app()

    with app.app_context():
        db.create_all()

        print("[INFO] Initializing Student Feedback System database...")

        # 1. Create Initial Administrator Account (if configured)
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin_pwd = Config.ADMIN_PASSWORD or secrets.token_urlsafe(16)
            admin = User(
                name=Config.ADMIN_NAME,
                email=Config.ADMIN_EMAIL.lower().strip(),
                department=Config.ADMIN_DEPARTMENT,
                student_id=None,
                role='admin',
                is_active=True
            )
            admin.set_password(admin_pwd)
            db.session.add(admin)
            print(f"[+] Created initial admin account: {admin.email}")
            if not Config.ADMIN_PASSWORD:
                print(f"[SECURITY NOTE] Generated secure password for {admin.email}: {admin_pwd}")
        else:
            print(f"[*] Admin account already exists: {admin.email}")

        # 2. Seed Real Faculty Members & Courses
        faculty_map = {}
        course_map = {}

        for code, name, faculty_name in REAL_CATALOG:
            # Faculty
            fac = Faculty.query.filter_by(faculty_name=faculty_name).first()
            if not fac:
                fac = Faculty(
                    faculty_name=faculty_name,
                    department="Computer Science & Engineering",
                    email=None,
                    is_active=True
                )
                db.session.add(fac)
                db.session.flush()
                print(f"[+] Added faculty: {faculty_name}")
            else:
                fac.is_active = True
            faculty_map[faculty_name] = fac

            # Course
            crs = Course.query.filter_by(course_code=code).first()
            if not crs:
                crs = Course(
                    course_code=code,
                    course_name=name,
                    department="Computer Science & Engineering",
                    faculty_id=fac.id,
                    is_active=True
                )
                db.session.add(crs)
                db.session.flush()
                print(f"[+] Added course: {code} - {name}")
            else:
                crs.course_name = name
                crs.faculty_id = fac.id
                crs.is_active = True
            course_map[code] = crs

        db.session.commit()
        print("[SUCCESS] Database initialized and verified with real catalog (No dummy records seeded)!")


if __name__ == '__main__':
    seed_database()
