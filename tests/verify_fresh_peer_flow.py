"""
Verification test confirming that the MongoDB-backed Campus Voice application
supports fresh user registration, login, and feedback submission starting from an
empty database, without requiring any historical SQLite data.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.config import TestingConfig
from app.db import get_db, close_db_client
from seed_data import seed_database
from app.models import Course, Faculty, Feedback

def test_fresh_peer_workflow():
    os.environ['MONGODB_URI'] = 'mongomock://localhost/empty_db_test'
    os.environ['ADMIN_PASSWORD'] = 'SecureAdminSecret2026!'
    os.environ['WTF_CSRF_ENABLED'] = 'false'

    close_db_client()
    app = create_app(TestingConfig)
    app.config['ADMIN_PASSWORD'] = 'SecureAdminSecret2026!'

    with app.app_context():
        db = get_db()
        # 1. Start with completely empty database
        db.users.delete_many({})
        db.courses.delete_many({})
        db.faculties.delete_many({})
        db.feedbacks.delete_many({})
        print(f"1. Initial DB state: Users={db.users.count_documents({})}, Courses={db.courses.count_documents({})}, Feedbacks={db.feedbacks.count_documents({})}")

        # 2. Seed academic catalog & admin only (zero student data)
        seed_database(app)
        print(f"2. Seeded state: Courses={db.courses.count_documents({})}, Faculties={db.faculties.count_documents({})}, Users={db.users.count_documents({})}, Feedbacks={db.feedbacks.count_documents({})}")

        # 3. Simulate peer student registration via HTTP
        client = app.test_client()
        reg_res = client.post('/register', data={
            'name': 'Peer Reviewer',
            'email': 'peer@university.edu',
            'student_id': '2026-PEER-01',
            'department': 'Computer Science & Engineering',
            'password': 'PeerPassword123!',
            'confirm_password': 'PeerPassword123!'
        }, follow_redirects=True)
        print(f"3. Peer Registration HTTP Status: {reg_res.status_code}")
        assert reg_res.status_code == 200
        assert b"created successfully" in reg_res.data

        # 4. Peer login
        login_res = client.post('/login', data={
            'email': 'peer@university.edu',
            'password': 'PeerPassword123!'
        }, follow_redirects=True)
        print(f"4. Peer Login HTTP Status: {login_res.status_code}")
        assert login_res.status_code == 200
        assert b"Welcome back, Peer Reviewer!" in login_res.data

        # 5. Peer submits feedback for course BCO017A
        course = Course.find_by_code('BCO017A')
        faculty = Faculty.find_by_name('Gajanand Sharma')
        fb_res = client.post('/student/submit-feedback', data={
            'course_id': course.id,
            'faculty_id': faculty.id,
            'rating': '5',
            'comments': 'Peer testing review: excellent practical delivery!'
        }, follow_redirects=True)
        print(f"5. Peer Feedback Submission HTTP Status: {fb_res.status_code}")
        assert fb_res.status_code == 200
        assert b"successfully submitted" in fb_res.data

        # 6. Verify feedback recorded in MongoDB
        total_fb = db.feedbacks.count_documents({})
        print(f"6. Feedbacks in MongoDB: Total={total_fb}")
        assert total_fb == 1
        fb = Feedback.find()[0]
        print(f"   Feedback recorded: Course={course.course_code}, Faculty={faculty.faculty_name}, Rating={fb.rating} stars")

    print("\nRESULT: Fresh user registration & feedback submission verified on empty database!")
    close_db_client()

if __name__ == '__main__':
    test_fresh_peer_workflow()
