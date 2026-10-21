import os
import re
import csv
import io
import sqlite3
import unittest
from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback
from seed_data import seed_database


class CampusVoiceAuditTestCase(unittest.TestCase):
    """
    Verification of the 10 acceptance criteria for Campus Voice audit and data cleanup:
    1. All confirmed dummy records have been removed.
    2. Genuine accounts and feedback remain intact.
    3. The six real subject-faculty assignments remain correct.
    4. Dashboard totals and averages reflect the cleaned database.
    5. Deleted dummy records do not return after restarting the application or re-seeding.
    6. Student registration, login, and feedback submission still work.
    7. Administrators can view genuine feedback and export reports.
    8. The 1-to-5 rating scale remains correct.
    9. All visible branding uses 'Campus Voice'.
    10. No unintended database changes or broken pages remain.
    """

    EXPECTED_CATALOG = [
        ("BCO017A", "Formal Languages and Automation Theory", "Gajanand Sharma"),
        ("BCO023A", "Design and Analysis of Algorithms", "Sonal Saxena"),
        ("BCO037B", "Advance Programming in Java", "Neha Solanki"),
        ("BCO019A", "Artificial Intelligence", "Ankur Agrawal"),
        ("BCO074C", "Minor Project", "Mahesh Kumar Joshi"),
        ("BCO681A", "Web Designing Using AI", "Mohit Parashar"),
    ]

    DUMMY_STUDENT_EMAILS = [
        "john.doe@student.university.edu",
        "emily.w@student.university.edu",
        "rahul.s@student.university.edu",
        "sophia.m@student.university.edu",
        "test.verifier@student.university.edu",
    ]

    DUMMY_FACULTY_NAMES = [
        "Dr. Grace Hopper",
        "Dr. Alan Turing",
        "Dr. Claude Shannon",
        "Dr. Nikola Tesla",
        "Dr. Peter Drucker",
        "Prof. Ada Lovelace",
        "Prof. Katherine Johnson",
        "Prof. Linus Torvalds",
    ]

    DUMMY_COURSE_CODES = [
        "CS101", "CS201", "CS301", "CS401", "IT202", "IT305", "EC105", "ME204", "BA102", "MA101"
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

    def test_01_all_dummy_records_removed(self):
        """Criterion 1: Confirmed dummy students, faculty, sample courses, and dummy feedback are absent."""
        with self.app.app_context():
            # Check dummy students
            for email in self.DUMMY_STUDENT_EMAILS:
                user = User.query.filter_by(email=email).first()
                self.assertIsNone(user, f"Dummy student '{email}' must be removed from the database.")

            # Check test student patterns
            test_students = User.query.filter(User.email.like("%test.student.%")).all()
            self.assertEqual(len(test_students), 0, "No audit test students should remain in the database.")

            # Check dummy faculty
            for fac_name in self.DUMMY_FACULTY_NAMES:
                fac = Faculty.query.filter_by(faculty_name=fac_name).first()
                self.assertIsNone(fac, f"Dummy faculty '{fac_name}' must be removed from the database.")

            # Check dummy courses
            for code in self.DUMMY_COURSE_CODES:
                course = Course.query.filter_by(course_code=code).first()
                self.assertIsNone(course, f"Sample course '{code}' must be removed from the database.")

            # Check generated review comments
            generated_fbs = Feedback.query.filter(Feedback.comments.like("Comprehensive review%")).all()
            self.assertEqual(len(generated_fbs), 0, "Generated dummy feedback reviews must be removed.")

            deleted_grace_fb = Feedback.query.filter(Feedback.comments.ilike("%Good in theory bad in practical%")).first()
            self.assertIsNone(deleted_grace_fb, "Grace Hopper CS201 demo review must not exist.")

    def test_02_genuine_accounts_and_feedback_intact(self):
        """Criterion 2: Legitimate account Anant Sinha, admin, and genuine feedback remain intact."""
        with self.app.app_context():
            # Check Anant Sinha
            anant = User.query.filter_by(email="anant@jecrc.edu.in").first()
            self.assertIsNotNone(anant, "Legitimate student account 'anant@jecrc.edu.in' must be preserved.")
            self.assertEqual(anant.name, "Anant Sinha")
            self.assertEqual(anant.student_id, "23BCON1670")
            self.assertEqual(anant.department, "Computer Science & Engineering")
            self.assertTrue(anant.is_active)

            # Check Administrator
            admin = User.query.filter_by(email="admin@university.edu").first()
            self.assertIsNotNone(admin, "Administrator account must be preserved.")
            self.assertEqual(admin.role, "admin")

            # Check genuine feedback #92
            genuine_fb = Feedback.query.filter_by(student_id=anant.id).first()
            self.assertIsNotNone(genuine_fb, "Anant Sinha's genuine feedback must be preserved.")
            self.assertEqual(genuine_fb.course.course_code, "BCO037B")
            self.assertEqual(genuine_fb.faculty.faculty_name, "Neha Solanki")
            self.assertEqual(genuine_fb.rating, 5)
            self.assertEqual(genuine_fb.comments, "Good")

    def test_03_six_real_subject_faculty_assignments(self):
        """Criterion 3: The 6 real subject and faculty assignments remain active and correctly mapped."""
        with self.app.app_context():
            active_courses = Course.query.filter_by(is_active=True).all()
            self.assertEqual(len(active_courses), 6, "Exactly 6 active courses must exist.")

            active_faculties = Faculty.query.filter_by(is_active=True).all()
            self.assertEqual(len(active_faculties), 6, "Exactly 6 active faculty members must exist.")

            for code, name, faculty_name in self.EXPECTED_CATALOG:
                course = Course.query.filter_by(course_code=code).first()
                self.assertIsNotNone(course, f"Course {code} must exist.")
                self.assertEqual(course.course_name, name)
                self.assertTrue(course.is_active)
                self.assertIsNotNone(course.assigned_faculty, f"Course {code} must have assigned faculty.")
                self.assertEqual(course.assigned_faculty.faculty_name, faculty_name)
                self.assertTrue(course.assigned_faculty.is_active)

    def test_04_dashboard_totals_and_averages(self):
        """Criterion 4: Dashboard totals and averages reflect the cleaned database."""
        with self.app.app_context():
            total_students = User.query.filter_by(role='student').count()
            total_courses = Course.query.filter_by(is_active=True).count()
            total_faculty = Faculty.query.filter_by(is_active=True).count()
            total_feedback = Feedback.query.count()

            self.assertEqual(total_students, 1)
            self.assertEqual(total_courses, 6)
            self.assertEqual(total_faculty, 6)
            self.assertEqual(total_feedback, 1)

        # Check admin dashboard response
        self.login_user("admin@university.edu", "AdminSecure2026!")
        dash_res = self.client.get('/admin/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        html = dash_res.get_data(as_text=True)
        self.assertIn("Total Active Courses", html)
        self.assertIn("Overall Average Rating", html)
        self.assertIn("5.0", html)

    def test_05_dummy_records_do_not_return_on_reseeding(self):
        """Criterion 5: Reseeding does NOT recreate dummy students or fake feedback."""
        with self.app.app_context():
            seed_database(self.app)
            for email in self.DUMMY_STUDENT_EMAILS:
                self.assertIsNone(User.query.filter_by(email=email).first())
            for fac in self.DUMMY_FACULTY_NAMES:
                self.assertIsNone(Faculty.query.filter_by(faculty_name=fac).first())
            self.assertEqual(Feedback.query.count(), 1)

    def test_06_student_registration_login_and_feedback(self):
        """Criterion 6: Student registration, login, and feedback submission work smoothly."""
        temp_email = "test.live.verify@student.university.edu"
        temp_sid = "LIVE-VERIFY-01"

        try:
            # Register
            reg_page = self.client.get('/register')
            csrf = self.extract_csrf_token(reg_page.get_data(as_text=True))
            reg_res = self.client.post('/register', data={
                'csrf_token': csrf,
                'name': 'Live Verify Student',
                'email': temp_email,
                'student_id': temp_sid,
                'department': 'Computer Science & Engineering',
                'password': 'Password123!',
                'confirm_password': 'Password123!'
            }, follow_redirects=True)
            self.assertEqual(reg_res.status_code, 200)

            # Login
            login_res = self.login_user(temp_email, "Password123!")
            self.assertEqual(login_res.status_code, 200)
            self.assertIn("Live Verify Student", login_res.get_data(as_text=True))

            # Submit feedback for BCO017A
            with self.app.app_context():
                c = Course.query.filter_by(course_code="BCO017A").first()
                f = Faculty.query.filter_by(faculty_name="Gajanand Sharma").first()
                c_id, f_id = c.id, f.id

            fb_page = self.client.get(f'/student/submit-feedback?course_id={c_id}&faculty_id={f_id}')
            fb_csrf = self.extract_csrf_token(fb_page.get_data(as_text=True))
            post_fb = self.client.post('/student/submit-feedback', data={
                'csrf_token': fb_csrf,
                'course_id': c_id,
                'faculty_id': f_id,
                'rating': '5',
                'comments': 'Live verification test feedback'
            }, follow_redirects=True)
            self.assertEqual(post_fb.status_code, 200)
            self.assertIn("Your feedback has been successfully submitted", post_fb.get_data(as_text=True))

            # View in history
            hist = self.client.get('/student/my-feedback')
            self.assertIn("BCO017A", hist.get_data(as_text=True))
            self.assertIn("Gajanand Sharma", hist.get_data(as_text=True))
        finally:
            # Clean up test user & its submitted feedback
            with self.app.app_context():
                u = User.query.filter_by(email=temp_email).first()
                if u:
                    Feedback.query.filter_by(student_id=u.id).delete()
                    db.session.delete(u)
                    db.session.commit()

    def test_07_admin_views_genuine_feedback_and_export_csv(self):
        """Criterion 7: Administrators can view genuine feedback and export CSV report."""
        self.login_user("admin@university.edu", "AdminSecure2026!")

        # 1. Feedback Review Page
        fb_res = self.client.get('/admin/feedback')
        self.assertEqual(fb_res.status_code, 200)
        html = fb_res.get_data(as_text=True)
        self.assertIn("Anant Sinha", html)
        self.assertIn("23BCON1670", html)
        self.assertIn("BCO037B", html)
        self.assertIn("Neha Solanki", html)
        self.assertIn("Good", html)

        # 2. CSV Export
        csv_res = self.client.get('/admin/feedback/export-csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.mimetype, 'text/csv')
        csv_text = csv_res.get_data(as_text=True)
        self.assertIn("Feedback ID,Submission Date,Student Name", csv_text)
        self.assertIn("Anant Sinha", csv_text)
        self.assertIn("23BCON1670", csv_text)
        self.assertIn("BCO037B", csv_text)
        self.assertIn("Neha Solanki", csv_text)
        self.assertIn("Excellent", csv_text)

    def test_08_rating_scale_remains_correct(self):
        """Criterion 8: 1=Terrible, 2=Poor, 3=Average, 4=Good, 5=Excellent throughout."""
        self.assertEqual(Feedback.RATING_SCALE[1], "Terrible")
        self.assertEqual(Feedback.RATING_SCALE[2], "Poor")
        self.assertEqual(Feedback.RATING_SCALE[3], "Average")
        self.assertEqual(Feedback.RATING_SCALE[4], "Good")
        self.assertEqual(Feedback.RATING_SCALE[5], "Excellent")

        with self.app.app_context():
            fb = Feedback.query.filter_by(id=92).first()
            if fb:
                self.assertEqual(fb.rating_label, "Excellent")

    def test_09_all_visible_branding_uses_campus_voice(self):
        """Criterion 9: All visible branding uses 'Campus Voice' and EduFeedback is absent."""
        # Check /health endpoint
        health_res = self.client.get('/health')
        self.assertEqual(health_res.status_code, 200)
        health_json = health_res.get_json()
        self.assertEqual(health_json['service'], "Campus Voice")
        self.assertEqual(health_json['status'], "healthy")

        # Check Login Page
        login_res = self.client.get('/login')
        login_html = login_res.get_data(as_text=True)
        self.assertIn("Campus Voice", login_html)
        self.assertNotIn("EduFeedback", login_html)

        # Check Register Page
        reg_res = self.client.get('/register')
        reg_html = reg_res.get_data(as_text=True)
        self.assertIn("Campus Voice", reg_html)
        self.assertNotIn("EduFeedback", reg_html)

        # Check Admin Dashboard
        self.login_user("admin@university.edu", "AdminSecure2026!")
        admin_res = self.client.get('/admin/dashboard')
        admin_html = admin_res.get_data(as_text=True)
        self.assertIn("Campus Voice", admin_html)
        self.assertNotIn("EduFeedback", admin_html)

    def test_10_database_integrity_and_routes(self):
        """Criterion 10: Database integrity is verified and core routes return HTTP 200."""
        # SQLite integrity check
        con = sqlite3.connect('instance/feedback.db')
        integrity = con.execute('PRAGMA integrity_check;').fetchone()[0]
        con.close()
        self.assertEqual(integrity, 'ok', "Database integrity must be 'ok'.")

        # Check admin routes
        self.login_user("admin@university.edu", "AdminSecure2026!")
        for route in ['/admin/dashboard', '/admin/faculty', '/admin/courses', '/admin/feedback', '/admin/students']:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} must return 200 OK")


if __name__ == '__main__':
    unittest.main()
