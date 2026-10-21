import unittest
from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback


import re

class EndToEndSystemVerification(unittest.TestCase):
    """
    End-to-end integration and smoke verification against the configured instance database.
    Verifies that seed data, models, relations, authentication, and reporting work seamlessly.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(Config)
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client(use_cookies=True)

    def test_01_verify_seed_counts(self):
        """Verifies initial seeded academic entities are present."""
        with self.app.app_context():
            admin = User.query.filter_by(role='admin').first()
            self.assertIsNotNone(admin, "Initial administrator must exist.")
            self.assertEqual(admin.email, "admin@university.edu")

            courses_count = Course.query.count()
            self.assertEqual(courses_count, 6, "Exactly 6 real catalog courses should exist.")

            faculty_count = Faculty.query.count()
            self.assertEqual(faculty_count, 6, "Exactly 6 real faculty members should exist.")

            feedback_count = Feedback.query.count()
            self.assertGreaterEqual(feedback_count, 1, "Legitimate feedback should be present.")

    def test_02_student_flow(self):
        """Test full student flow: register/login -> view dashboard -> view courses -> view history."""
        test_email = "temp.e2e.student@university.edu"
        with self.app.app_context():
            existing = User.query.filter_by(email=test_email).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()
            temp_student = User(
                name="E2E Student",
                email=test_email,
                student_id="E2E-9999",
                department="Computer Science & Engineering",
                role="student",
                is_active=True
            )
            temp_student.set_password("Student123!")
            db.session.add(temp_student)
            db.session.commit()

        try:
            # 1. Login with test student
            res_login = self.client.post('/login', data={
                'email': test_email,
                'password': 'Student123!'
            }, follow_redirects=True)
            self.assertEqual(res_login.status_code, 200)
            self.assertIn(b"E2E Student", res_login.data)

            # 2. View dashboard
            res_dash = self.client.get('/student/dashboard')
            self.assertEqual(res_dash.status_code, 200)
            self.assertIn(b"Available Academic Courses", res_dash.data)

            # 3. View submission history
            res_hist = self.client.get('/student/my-feedback')
            self.assertEqual(res_hist.status_code, 200)
            self.assertIn(b"My Evaluation History", res_hist.data)

            # 4. Logout
            res_logout = self.client.get('/logout', follow_redirects=True)
            self.assertEqual(res_logout.status_code, 200)
        finally:
            with self.app.app_context():
                User.query.filter_by(email=test_email).delete()
                db.session.commit()

    def test_03_admin_flow(self):
        """Test full admin flow: login -> dashboard -> faculty list -> course list -> feedback list -> CSV export."""
        # 1. Login with admin credentials
        res_login = self.client.post('/login', data={
            'email': 'admin@university.edu',
            'password': 'AdminSecure2026!'
        }, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"Administrator Control Center", res_login.data)

        # 2. View Dashboard
        res_dash = self.client.get('/admin/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Rating Breakdown", res_dash.data)

        # 3. View Faculty Catalog
        res_fac = self.client.get('/admin/faculty')
        self.assertEqual(res_fac.status_code, 200)
        self.assertIn(b"Faculty Directory", res_fac.data)

        # 4. View Course Catalog
        res_courses = self.client.get('/admin/courses')
        self.assertEqual(res_courses.status_code, 200)
        self.assertIn(b"Course Curriculum Catalog", res_courses.data)

        # 5. View Feedback list with filter
        res_fb = self.client.get('/admin/feedback?rating=5')
        self.assertEqual(res_fb.status_code, 200)
        self.assertIn(b"Feedback Submissions Review", res_fb.data)

        # 6. Export CSV
        res_csv = self.client.get('/admin/feedback/export-csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, 'text/csv')
        self.assertIn(b"Feedback ID,Submission Date", res_csv.data)

        # 7. Logout
        self.client.get('/logout', follow_redirects=True)


if __name__ == '__main__':
    unittest.main()
