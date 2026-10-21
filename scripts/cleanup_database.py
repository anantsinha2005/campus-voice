import sqlite3
import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import db, User, Course, Faculty, Feedback

REAL_COURSES = {
    "BCO017A": "Formal Languages and Automation Theory",
    "BCO023A": "Design and Analysis of Algorithms",
    "BCO037B": "Advance Programming in Java",
    "BCO019A": "Artificial Intelligence",
    "BCO074C": "Minor Project",
    "BCO681A": "Web Designing Using AI",
}

REAL_FACULTY = [
    "Gajanand Sharma",
    "Sonal Saxena",
    "Neha Solanki",
    "Ankur Agrawal",
    "Mahesh Kumar Joshi",
    "Mohit Parashar",
]

LEGITIMATE_STUDENTS = [
    "anant@jecrc.edu.in",
]


def clean_database():
    app = create_app()
    with app.app_context():
        print("=== STARTING DATABASE CLEANUP ===")

        # 1. Verify legitimate account exists
        anant = User.query.filter_by(email="anant@jecrc.edu.in").first()
        if not anant:
            raise RuntimeError("CRITICAL: Legitimate account anant@jecrc.edu.in not found!")
        print(f"[VERIFIED] Legitimate account found: {anant.name} ({anant.email}, Roll: {anant.student_id})")

        admin = User.query.filter_by(role="admin").first()
        if not admin:
            raise RuntimeError("CRITICAL: Administrator account not found!")
        print(f"[VERIFIED] Administrator found: {admin.name} ({admin.email})")

        # 2. Verify Anant's genuine feedback exists
        anant_fbs = Feedback.query.filter_by(student_id=anant.id).all()
        print(f"[VERIFIED] Legitimate feedback count for Anant Sinha: {len(anant_fbs)}")
        for fb in anant_fbs:
            crs = Course.query.get(fb.course_id)
            fac = Faculty.query.get(fb.faculty_id)
            print(f"  -> Feedback #{fb.id}: Course: {crs.course_code if crs else fb.course_id}, Faculty: {fac.faculty_name if fac else fb.faculty_id}, Rating: {fb.rating}, Comments: '{fb.comments}'")

        # 3. Identify and delete dummy feedbacks
        dummy_fbs = Feedback.query.filter(Feedback.student_id != anant.id).all()
        print(f"\n[ACTION] Deleting {len(dummy_fbs)} dummy/test feedback submissions...")
        for fb in dummy_fbs:
            db.session.delete(fb)

        # 4. Identify and delete dummy students
        dummy_students = User.query.filter(
            User.role == 'student',
            ~User.email.in_(LEGITIMATE_STUDENTS)
        ).all()
        print(f"[ACTION] Deleting {len(dummy_students)} dummy/test student accounts...")
        for stu in dummy_students:
            print(f"  - Deleting user: {stu.name} ({stu.email})")
            db.session.delete(stu)

        # 5. Identify and delete dummy courses
        real_codes = list(REAL_COURSES.keys())
        dummy_courses = Course.query.filter(~Course.course_code.in_(real_codes)).all()
        print(f"[ACTION] Deleting {len(dummy_courses)} unrelated sample courses...")
        for crs in dummy_courses:
            print(f"  - Deleting course: {crs.course_code} - {crs.course_name}")
            db.session.delete(crs)

        # 6. Identify and delete dummy faculty
        dummy_faculty = Faculty.query.filter(~Faculty.faculty_name.in_(REAL_FACULTY)).all()
        print(f"[ACTION] Deleting {len(dummy_faculty)} fictional demo faculty...")
        for fac in dummy_faculty:
            print(f"  - Deleting faculty: {fac.faculty_name}")
            db.session.delete(fac)

        # 7. Ensure real courses and faculty are active and properly linked
        print("\n[ACTION] Verifying the 6 real subjects and assigned faculty...")
        for code, faculty_name in [
            ("BCO017A", "Gajanand Sharma"),
            ("BCO023A", "Sonal Saxena"),
            ("BCO037B", "Neha Solanki"),
            ("BCO019A", "Ankur Agrawal"),
            ("BCO074C", "Mahesh Kumar Joshi"),
            ("BCO681A", "Mohit Parashar"),
        ]:
            fac = Faculty.query.filter_by(faculty_name=faculty_name).first()
            crs = Course.query.filter_by(course_code=code).first()
            if not fac or not crs:
                raise RuntimeError(f"Missing real catalog entry: {code} / {faculty_name}")
            fac.is_active = True
            crs.is_active = True
            crs.faculty_id = fac.id

        # Commit all changes in transaction
        db.session.commit()
        print("\n[SUCCESS] Database transaction committed successfully!")

        # 8. Post-cleanup verification
        users_count = User.query.count()
        students_count = User.query.filter_by(role='student').count()
        courses_count = Course.query.count()
        faculty_count = Faculty.query.count()
        feedback_count = Feedback.query.count()

        print("\n=== POST-CLEANUP SUMMARY ===")
        print(f"Total Users: {users_count} (Students: {students_count}, Admins: {users_count - students_count})")
        print(f"Total Courses: {courses_count} (All Real)")
        print(f"Total Faculty: {faculty_count} (All Real)")
        print(f"Total Feedback: {feedback_count} (All Genuine)")

        # Verify integrity
        con = sqlite3.connect('instance/feedback.db')
        integrity = con.execute('PRAGMA integrity_check;').fetchone()[0]
        con.close()
        print(f"SQLite PRAGMA integrity_check: {integrity}")


if __name__ == '__main__':
    clean_database()
