"""
Seed script for Campus Voice - Student Feedback & Academic Quality System.
Populates academic faculty, courses, and the initial administrator account in MongoDB.
Strictly requires ADMIN_PASSWORD to be provided via environment variables.
Does NOT create dummy reviews or dummy students.
"""
import os
import sys
from app import create_app
from app.config import Config
from app.models import User, Course, Faculty
from app.db import get_db, init_indexes

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
    and the real academic catalog if not present in MongoDB.
    Strictly requires ADMIN_PASSWORD environment variable for administrator provisioning.
    """
    if app is None:
        app = create_app()

    with app.app_context():
        db = get_db()
        init_indexes(db)

        print("[INFO] Initializing Campus Voice MongoDB database...")

        # 1. Create Initial Administrator Account (strictly requires ADMIN_PASSWORD)
        admin = User.all(filter_dict={'role': 'admin'})
        if not admin:
            admin_pwd = (app.config.get('ADMIN_PASSWORD') if app else None) or os.environ.get('ADMIN_PASSWORD')
            if not admin_pwd or not str(admin_pwd).strip():
                raise ValueError(
                    "ADMIN_PASSWORD environment variable must be set to provision the initial administrator. "
                    "Refusing to create administrator with fallback or default password."
                )

            admin_user = User(
                name=app.config.get('ADMIN_NAME', Config.ADMIN_NAME),
                email=app.config.get('ADMIN_EMAIL', Config.ADMIN_EMAIL).lower().strip(),
                department=app.config.get('ADMIN_DEPARTMENT', Config.ADMIN_DEPARTMENT),
                student_id=None,
                role='admin',
                is_active=True
            )
            admin_user.set_password(str(admin_pwd).strip())
            admin_user.save()
            print(f"[+] Created initial admin account: {admin_user.email}")
        else:
            print(f"[*] Admin account already exists: {admin[0].email}")

        # 2. Seed Real Faculty Members & Courses
        faculty_map = {}
        for code, name, faculty_name in REAL_CATALOG:
            # Faculty
            fac = Faculty.find_by_name(faculty_name)
            if not fac:
                fac = Faculty(
                    faculty_name=faculty_name,
                    department="Computer Science & Engineering",
                    email=None,
                    is_active=True
                )
                fac.save()
                print(f"[+] Added faculty: {faculty_name}")
            else:
                fac.is_active = True
                fac.save()
            faculty_map[faculty_name] = fac

            # Course
            crs = Course.find_by_code(code)
            if not crs:
                crs = Course(
                    course_code=code,
                    course_name=name,
                    department="Computer Science & Engineering",
                    faculty_id=fac.id,
                    is_active=True
                )
                crs.save()
                print(f"[+] Added course: {code} - {name}")
            else:
                crs.course_name = name
                crs.faculty_id = fac.id
                crs.is_active = True
                crs.save()

        print("[SUCCESS] MongoDB initialized and verified with real catalog (No dummy records seeded)!")


if __name__ == '__main__':
    seed_database()
