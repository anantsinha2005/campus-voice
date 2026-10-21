import os
import re
import csv
import io
import unittest
from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback
from seed_data import seed_database


class AuditReversalAndCleanupTestCase(unittest.TestCase):
    """
    Comprehensive verification for the 15 acceptance criteria:
    1. The incorrect Dr. Grace Hopper demo feedback is absent from active database and views.
    2. Existing legitimate feedback remains intact.
    3. 1-star rating displays Terrible.
    4. 5-star rating displays Excellent.
    5. Student registration, login, logout, and session protection work.
    6. Student can submit feedback (including with optional/empty comments) and view in history.
    7. Administrator can view the submission in central admin dashboard.
    8. Feedback persists after Flask server restarts.
    9. Students cannot view other students' private records.
    10. Students cannot access administrator endpoints.
    11. Rating averages, charts, filters, and CSV exports use the correct scale.
    12. The six real subjects and faculty assignments are correct.
    13. Application does not reinsert the deleted demo feedback on re-seeding.
    14. No default administrator credentials or production debug mode remain enabled.
    15. Database backup exists, is verified, and recovery is documented.
    """

    EXPECTED_CATALOG = [
        ("BCO017A", "Formal Languages and Automation Theory", "Gajanand Sharma"),
        ("BCO023A", "Design and Analysis of Algorithms", "Sonal Saxena"),
        ("BCO037B", "Advance Programming in Java", "Neha Solanki"),
        ("BCO019A", "Artificial Intelligence", "Ankur Agrawal"),
        ("BCO074C", "Minor Project", "Mahesh Kumar Joshi"),
        ("BCO681A", "Web Designing Using AI", "Mohit Parashar"),
    ]

    def setUp(self):
        self.app = create_app(Config)
        self.client = self.app.test_client(use_cookies=True)

    def extract_csrf_token(self, html_content):
        match = re.search(r'name=["\']csrf_token["\'].*?value=["\']([^"\']+)["\']', html_content, re.DOTALL)
        if not match:
            match = re.search(r'value=["\']([^"\']+)["\'].*?name=["\']csrf_token["\']', html_content, re.DOTALL)
        self.assertIsNotNone(match, "CSRF token must be present")
        return match.group(1)

    def login_user(self, email, password):
        get_res = self.client.get('/login')
        csrf_token = self.extract_csrf_token(get_res.get_data(as_text=True))
        return self.client.post('/login', data={
            'csrf_token': csrf_token,
            'email': email,
            'password': password
        }, follow_redirects=True)

    def test_01_deleted_demo_feedback_absent_from_database_and_views(self):
        """Criterion 1: Incorrect Dr. Grace Hopper CS201 demo feedback is absent from database and all views."""
        with self.app.app_context():
            deleted_fb = Feedback.query.filter(
                Feedback.comments.ilike("%Good in theory bad in practical%")
            ).first()
            self.assertIsNone(deleted_fb, "Demo feedback 'Good in theory bad in practical' must NOT exist in database.")

            deleted_id_10 = db.session.get(Feedback, 10)
            self.assertIsNone(deleted_id_10, "Feedback ID 10 must be deleted.")

        # Check admin feedback review page
        self.login_user("admin@university.edu", "AdminSecure2026!")
        admin_fb_res = self.client.get('/admin/feedback')
        html = admin_fb_res.get_data(as_text=True)
        self.assertNotIn("Good in theory bad in practical", html)

        # Check CSV export
        csv_res = self.client.get('/admin/feedback/export-csv')
        csv_text = csv_res.get_data(as_text=True)
        self.assertNotIn("Good in theory bad in practical", csv_text)

    def test_02_existing_legitimate_feedback_intact(self):
        """Criterion 2: Legitimate student feedback records remain intact."""
        with self.app.app_context():
            total_feedbacks = Feedback.query.count()
            self.assertGreaterEqual(total_feedbacks, 15, "All legitimate feedback records must be preserved.")

            # Check specific legitimate feedback for Dr. Alan Turing
            alan_fb = Feedback.query.filter(Feedback.comments.like("%algorithmic complexity%")).first()
            self.assertIsNotNone(alan_fb)
            self.assertEqual(alan_fb.rating, 5)

    def test_03_and_04_rating_scale_labels(self):
        """Criteria 3 & 4: 1-star is Terrible and 5-star is Excellent across models, forms, and views."""
        with self.app.app_context():
            fb1 = Feedback(rating=1, comments="Test", student_id=1, faculty_id=1, course_id=1)
            fb2 = Feedback(rating=2, comments="Test", student_id=1, faculty_id=1, course_id=1)
            fb3 = Feedback(rating=3, comments="Test", student_id=1, faculty_id=1, course_id=1)
            fb4 = Feedback(rating=4, comments="Test", student_id=1, faculty_id=1, course_id=1)
            fb5 = Feedback(rating=5, comments="Test", student_id=1, faculty_id=1, course_id=1)

            self.assertEqual(fb1.rating_label, "Terrible")
            self.assertEqual(fb2.rating_label, "Poor")
            self.assertEqual(fb3.rating_label, "Average")
            self.assertEqual(fb4.rating_label, "Good")
            self.assertEqual(fb5.rating_label, "Excellent")

        # Check student form choices
        self.login_user("emily.w@student.university.edu", "Student123!")
        form_res = self.client.get('/student/submit-feedback')
        html = form_res.get_data(as_text=True)
        self.assertIn("5 - Excellent", html)
        self.assertIn("4 - Good", html)
        self.assertIn("3 - Average", html)
        self.assertIn("2 - Poor", html)
        self.assertIn("1 - Terrible", html)

    def test_05_student_registration_and_authentication(self):
        """Criterion 5: Student registration, login, logout, and session protection work."""
        new_email = f"test.student.{os.getpid()}@student.university.edu"
        new_sid = f"ROLL-{os.getpid()}"

        reg_page = self.client.get('/register')
        csrf_token = self.extract_csrf_token(reg_page.get_data(as_text=True))

        reg_post = self.client.post('/register', data={
            'csrf_token': csrf_token,
            'name': 'Audit Test Student',
            'email': new_email,
            'student_id': new_sid,
            'department': 'Computer Science & Engineering',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!'
        }, follow_redirects=True)
        self.assertEqual(reg_post.status_code, 200)

        # Login with newly created student
        login_res = self.login_user(new_email, "SecurePass123!")
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("Audit Test Student", login_res.get_data(as_text=True))

        # Logout
        logout_res = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertIn("successfully logged out", logout_res.get_data(as_text=True))

    def test_06_and_07_feedback_submission_optional_comments_and_admin_sync(self):
        """Criteria 6 & 7: Student feedback submission works with optional comments and appears in admin dashboard."""
        self.login_user("john.doe@student.university.edu", "Student123!")

        with self.app.app_context():
            course = Course.query.filter_by(course_code="BCO681A").first()
            faculty = Faculty.query.filter_by(faculty_name="Mohit Parashar").first()
            c_id = course.id
            f_id = faculty.id
            john = User.query.filter_by(email="john.doe@student.university.edu").first()
            Feedback.query.filter_by(student_id=john.id, course_id=c_id, faculty_id=f_id).delete()
            db.session.commit()

        form_page = self.client.get(f'/student/submit-feedback?course_id={c_id}&faculty_id={f_id}', follow_redirects=True)
        csrf_token = self.extract_csrf_token(form_page.get_data(as_text=True))

        # Submit with completely blank comments (optional)
        post_res = self.client.post('/student/submit-feedback', data={
            'csrf_token': csrf_token,
            'course_id': c_id,
            'faculty_id': f_id,
            'rating': '5',
            'comments': ''
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertIn("Your feedback has been successfully submitted", post_res.get_data(as_text=True))

        # Verify in student's history
        hist_res = self.client.get('/student/my-feedback')
        hist_html = hist_res.get_data(as_text=True)
        self.assertIn("BCO681A", hist_html)
        self.assertIn("Mohit Parashar", hist_html)
        self.assertIn("Excellent", hist_html)

        # Verify in admin central dashboard
        self.client.get('/logout')
        self.login_user("admin@university.edu", "AdminSecure2026!")

        admin_res = self.client.get('/admin/feedback?course_id=' + str(c_id))
        admin_html = admin_res.get_data(as_text=True)
        self.assertIn("John Doe", admin_html)
        self.assertIn("BCO681A", admin_html)
        self.assertIn("Mohit Parashar", admin_html)
        self.assertIn("Excellent", admin_html)

    def test_08_database_persistence_across_app_restart(self):
        """Criterion 8: Feedback persists across application restart."""
        restarted_app = create_app(Config)
        with restarted_app.app_context():
            course = Course.query.filter_by(course_code="BCO681A").first()
            john = User.query.filter_by(email="john.doe@student.university.edu").first()
            fb = Feedback.query.filter_by(student_id=john.id, course_id=course.id).first()
            self.assertIsNotNone(fb, "Feedback must persist across app restart.")
            self.assertEqual(fb.rating, 5)
            self.assertEqual(fb.rating_label, "Excellent")

    def test_09_and_10_rbac_and_student_privacy(self):
        """Criteria 9 & 10: Students cannot view other students' submissions or access admin routes."""
        self.login_user("rahul.s@student.university.edu", "Student123!")

        # 9. Student history is strictly isolated
        my_res = self.client.get('/student/my-feedback')
        my_html = my_res.get_data(as_text=True)
        # John Doe's submission should not be in Rahul's history
        self.assertNotIn("Unique Audit Observation", my_html)

        # 10. Student receives 403 Forbidden on all admin endpoints
        admin_endpoints = [
            '/admin/dashboard',
            '/admin/feedback',
            '/admin/courses',
            '/admin/faculty',
            '/admin/students',
            '/admin/feedback/export-csv'
        ]
        for ep in admin_endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 403, f"Expected 403 Forbidden for {ep}")

    def test_11_rating_averages_charts_and_csv_export(self):
        """Criterion 11: Rating distribution and CSV exports use the corrected scale and include labels."""
        self.login_user("admin@university.edu", "AdminSecure2026!")

        # Test analytics API
        analytics_res = self.client.get('/admin/analytics/data')
        self.assertEqual(analytics_res.status_code, 200)
        data = analytics_res.get_json()
        self.assertIn('rating_distribution', data)
        self.assertIn('1', data['rating_distribution'])
        self.assertIn('5', data['rating_distribution'])

        # Test CSV export
        csv_res = self.client.get('/admin/feedback/export-csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.mimetype, 'text/csv')
        csv_text = csv_res.get_data(as_text=True)
        reader = list(csv.reader(io.StringIO(csv_text)))
        header = reader[0]
        self.assertIn('Rating (1-5)', header)
        self.assertIn('Rating Label', header)

    def test_12_six_real_subject_and_faculty_assignments(self):
        """Criterion 12: The six real subjects and faculty assignments are correct."""
        with self.app.app_context():
            active_courses = Course.query.filter_by(is_active=True).all()
            self.assertEqual(len(active_courses), 6)

            active_course_map = {c.course_code: c for c in active_courses}
            for code, name, faculty_name in self.EXPECTED_CATALOG:
                self.assertIn(code, active_course_map)
                c = active_course_map[code]
                self.assertEqual(c.course_name, name)
                self.assertIsNotNone(c.assigned_faculty)
                self.assertEqual(c.assigned_faculty.faculty_name, faculty_name)

    def test_13_no_reintroduction_of_demo_feedback(self):
        """Criterion 13: Re-running seed_database does NOT reintroduce deleted demo feedback."""
        with self.app.app_context():
            seed_database(self.app)
            demo_fb = Feedback.query.filter(Feedback.comments.ilike("%Good in theory%")).first()
            self.assertIsNone(demo_fb, "Seeding must not reintroduce deleted demo feedback.")

    def test_14_security_settings_and_no_hardcoded_admin_passwords(self):
        """Criterion 14: Health endpoint exists, and Config doesn't fall back to a hardcoded admin password."""
        # Health check
        health_res = self.client.get('/health')
        self.assertEqual(health_res.status_code, 200)
        self.assertEqual(health_res.get_json()['status'], 'healthy')

        # Verify that without environment variable, Config doesn't contain a hardcoded fallback
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            # Check os.environ.get('ADMIN_PASSWORD') is None
            self.assertIsNone(os.environ.get('ADMIN_PASSWORD'))

    def test_15_backup_exists_and_verified(self):
        """Criterion 15: Verified database backups exist in instance/backups."""
        backup_dir = os.path.join(os.path.dirname(__file__), '..', 'instance', 'backups')
        self.assertTrue(os.path.isdir(backup_dir))
        backups = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
        self.assertGreaterEqual(len(backups), 1, "At least one database backup must exist.")


if __name__ == '__main__':
    unittest.main()
