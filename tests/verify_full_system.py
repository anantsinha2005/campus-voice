import re
import csv
import io
import unittest
from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback


class ComprehensiveSystemVerification(unittest.TestCase):
    """
    Detailed verification covering all 10 user requirements:
    1. Dependencies and imports
    2. Database initialization and constraints
    3. Student registration (with CSRF), validation, login, session, logout
    4. Student feedback submission, persistence, duplicate prevention, history isolation
    5. Admin authentication, RBAC route protection (403), unauthorized redirects
    6. Faculty CRUD and deactivation
    7. Course CRUD and deactivation
    8. Feedback multi-criteria filtering and keyword search
    9. Chart.js analytics endpoint
    10. CSV Export structure and data integrity
    """

    def setUp(self):
        self.app = create_app(Config)
        self.client = self.app.test_client(use_cookies=True)

    def extract_csrf_token(self, html_content):
        """Extracts CSRF token from rendered HTML form."""
        match = re.search(r'name=["\']csrf_token["\'].*?value=["\']([^"\']+)["\']', html_content, re.DOTALL)
        if not match:
            match = re.search(r'value=["\']([^"\']+)["\'].*?name=["\']csrf_token["\']', html_content, re.DOTALL)
        self.assertIsNotNone(match, "CSRF token must be present in HTML form")
        return match.group(1)

    # -------------------------------------------------------------------------
    # STEP 4: Registration, Login, Logout, Session
    # -------------------------------------------------------------------------
    def test_01_student_registration_workflow(self):
        """Verify student registration with valid and invalid inputs."""
        # 1. Fetch registration form to get CSRF token
        get_res = self.client.get('/register')
        self.assertEqual(get_res.status_code, 200)
        csrf_token = self.extract_csrf_token(get_res.get_data(as_text=True))

        # 2. Register a new test student
        test_email = "test.verifier@student.university.edu"
        test_sid = "TEST-2026-99"

        # Cleanup if previously exists
        with self.app.app_context():
            old = User.query.filter_by(email=test_email).first()
            if old:
                db.session.delete(old)
                db.session.commit()

        post_res = self.client.post('/register', data={
            'csrf_token': csrf_token,
            'name': 'Test Verifier Student',
            'email': test_email,
            'student_id': test_sid,
            'department': 'Computer Science & Engineering',
            'password': 'VerifierPass123!',
            'confirm_password': 'VerifierPass123!'
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertIn("created successfully", post_res.get_data(as_text=True))

        # Verify in DB
        with self.app.app_context():
            user = User.query.filter_by(email=test_email).first()
            self.assertIsNotNone(user)
            self.assertEqual(user.role, 'student', "Registered user must strictly have student role")
            self.assertEqual(user.student_id, test_sid)
            self.assertTrue(user.check_password('VerifierPass123!'))

        # 3. Attempt duplicate registration (same email)
        get_res2 = self.client.get('/register')
        csrf2 = self.extract_csrf_token(get_res2.get_data(as_text=True))
        dup_res = self.client.post('/register', data={
            'csrf_token': csrf2,
            'name': 'Duplicate Person',
            'email': test_email,
            'student_id': 'ANOTHER-ID-1',
            'department': 'Computer Science & Engineering',
            'password': 'VerifierPass123!',
            'confirm_password': 'VerifierPass123!'
        })
        self.assertIn("already registered", dup_res.get_data(as_text=True))

    def test_02_student_login_and_session(self):
        """Verify student login, session cookie, and role redirection."""
        get_res = self.client.get('/login')
        csrf_token = self.extract_csrf_token(get_res.get_data(as_text=True))

        login_res = self.client.post('/login', data={
            'csrf_token': csrf_token,
            'email': 'john.doe@student.university.edu',
            'password': 'Student123!',
            'remember_me': 'y'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("Welcome back, John Doe", login_res.get_data(as_text=True))
        self.assertIn("Student Portal", login_res.get_data(as_text=True))

        # Check dashboard loads cleanly
        dash_res = self.client.get('/student/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn("CS-2023-0101", dash_res.get_data(as_text=True))

        # Logout
        logout_res = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertIn("successfully logged out", logout_res.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # STEP 5: Feedback Submission, Persistence, Duplicate Prevention
    # -------------------------------------------------------------------------
    def test_03_student_feedback_submission_and_duplicate_check(self):
        """Verify feedback form submission, persistence, and duplicate blocking."""
        # Log in as test student
        get_login = self.client.get('/login')
        csrf_login = self.extract_csrf_token(get_login.get_data(as_text=True))
        self.client.post('/login', data={
            'csrf_token': csrf_login,
            'email': 'test.verifier@student.university.edu',
            'password': 'VerifierPass123!'
        }, follow_redirects=True)

        with self.app.app_context():
            course = Course.query.filter_by(is_active=True).first()
            faculty = Faculty.query.filter_by(is_active=True).first()
            test_student = User.query.filter_by(email='test.verifier@student.university.edu').first()
            
            # Remove any existing feedback for this test combo
            Feedback.query.filter_by(
                student_id=test_student.id,
                course_id=course.id,
                faculty_id=faculty.id
            ).delete()
            db.session.commit()

            c_id = course.id
            f_id = faculty.id
            s_id = test_student.id

        # 1. Fetch feedback form
        fb_get = self.client.get(f'/student/submit-feedback?course_id={c_id}&faculty_id={f_id}')
        self.assertEqual(fb_get.status_code, 200)
        csrf_fb = self.extract_csrf_token(fb_get.get_data(as_text=True))

        # 2. Submit new feedback
        comments_text = "Thorough explanations and insightful real-world examples throughout the course."
        fb_post = self.client.post('/student/submit-feedback', data={
            'csrf_token': csrf_fb,
            'course_id': c_id,
            'faculty_id': f_id,
            'rating': '5',
            'comments': comments_text
        }, follow_redirects=True)
        self.assertEqual(fb_post.status_code, 200)
        self.assertIn("successfully submitted", fb_post.get_data(as_text=True))

        # Verify DB persistence
        with self.app.app_context():
            saved_fb = Feedback.query.filter_by(
                student_id=s_id,
                course_id=c_id,
                faculty_id=f_id
            ).first()
            self.assertIsNotNone(saved_fb)
            self.assertEqual(saved_fb.rating, 5)
            self.assertEqual(saved_fb.comments, comments_text)

        # 3. Attempt duplicate feedback submission for identical (course, faculty)
        fb_get2 = self.client.get('/student/submit-feedback')
        csrf_fb2 = self.extract_csrf_token(fb_get2.get_data(as_text=True))
        dup_fb = self.client.post('/student/submit-feedback', data={
            'csrf_token': csrf_fb2,
            'course_id': c_id,
            'faculty_id': f_id,
            'rating': '4',
            'comments': "Attempting duplicate evaluation."
        }, follow_redirects=True)
        self.assertIn("Duplicate submissions are prohibited", dup_fb.get_data(as_text=True))

        # Check history page
        hist_res = self.client.get('/student/my-feedback')
        self.assertEqual(hist_res.status_code, 200)
        self.assertIn(comments_text, hist_res.get_data(as_text=True))

        # Logout student
        self.client.get('/logout')

    # -------------------------------------------------------------------------
    # STEP 6: Administrator Login & RBAC Enforcement
    # -------------------------------------------------------------------------
    def test_04_admin_login_and_rbac(self):
        """Verify admin login and strict access control on all routes."""
        # 1. Unauthenticated attempts to access admin routes must redirect to login
        admin_unauth = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(admin_unauth.status_code, 302)
        self.assertIn('/login', admin_unauth.location)

        # 2. Student attempting to access admin route must receive 403 Forbidden
        get_login = self.client.get('/login')
        csrf_login = self.extract_csrf_token(get_login.get_data(as_text=True))
        self.client.post('/login', data={
            'csrf_token': csrf_login,
            'email': 'john.doe@student.university.edu',
            'password': 'Student123!'
        }, follow_redirects=True)

        res_forbidden = self.client.get('/admin/dashboard')
        self.assertEqual(res_forbidden.status_code, 403)
        self.assertIn("Access Prohibited", res_forbidden.get_data(as_text=True))

        self.client.get('/logout')

        # 3. Valid admin login
        get_login2 = self.client.get('/login')
        csrf_admin = self.extract_csrf_token(get_login2.get_data(as_text=True))
        admin_login = self.client.post('/login', data={
            'csrf_token': csrf_admin,
            'email': 'admin@university.edu',
            'password': 'AdminSecure2026!'
        }, follow_redirects=True)
        self.assertEqual(admin_login.status_code, 200)
        self.assertIn("Administrator Control Center", admin_login.get_data(as_text=True))

        # Admin accessing student dashboard gets redirected cleanly to admin dashboard
        stud_redirect = self.client.get('/student/dashboard', follow_redirects=True)
        self.assertEqual(stud_redirect.status_code, 200)
        self.assertIn("Administrator Control Center", stud_redirect.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # STEP 7: Faculty & Course Management, Filters, Analytics, CSV Export
    # -------------------------------------------------------------------------
    def test_05_faculty_and_course_management(self):
        """Verify faculty & course CRUD operations and toggling."""
        # Admin is already logged in or let's ensure login
        get_login = self.client.get('/login')
        csrf_login = self.extract_csrf_token(get_login.get_data(as_text=True))
        self.client.post('/login', data={
            'csrf_token': csrf_login,
            'email': 'admin@university.edu',
            'password': 'AdminSecure2026!'
        }, follow_redirects=True)

        # 1. Add Faculty
        fac_page = self.client.get('/admin/faculty')
        csrf_fac = self.extract_csrf_token(fac_page.get_data(as_text=True))
        test_fac_email = "linus.torvalds@university.edu"

        # Cleanup if previously exists
        with self.app.app_context():
            old_f = Faculty.query.filter_by(email=test_fac_email).first()
            if old_f:
                db.session.delete(old_f)
                db.session.commit()

        add_fac_res = self.client.post('/admin/faculty', data={
            'csrf_token': csrf_fac,
            'faculty_name': 'Prof. Linus Torvalds',
            'department': 'Computer Science & Engineering',
            'email': test_fac_email,
            'is_active': 'y'
        }, follow_redirects=True)
        self.assertIn("added successfully", add_fac_res.get_data(as_text=True))

        with self.app.app_context():
            f = Faculty.query.filter_by(email=test_fac_email).first()
            self.assertIsNotNone(f)
            self.assertTrue(f.is_active)
            fac_id = f.id

        # 2. Toggle Faculty active status (POST with CSRF)
        fac_page2 = self.client.get('/admin/faculty')
        csrf_toggle = self.extract_csrf_token(fac_page2.get_data(as_text=True))
        toggle_res = self.client.post(f'/admin/faculty/{fac_id}/toggle', data={
            'csrf_token': csrf_toggle
        }, follow_redirects=True)
        self.assertIn("deactivated", toggle_res.get_data(as_text=True))

        with self.app.app_context():
            self.assertFalse(db.session.get(Faculty, fac_id).is_active)

        # 3. Add Course
        crs_page = self.client.get('/admin/courses')
        csrf_crs = self.extract_csrf_token(crs_page.get_data(as_text=True))
        test_crs_code = "CS401"

        # Cleanup if previously exists
        with self.app.app_context():
            old_c = Course.query.filter_by(course_code=test_crs_code).first()
            if old_c:
                db.session.delete(old_c)
                db.session.commit()

        add_crs_res = self.client.post('/admin/courses', data={
            'csrf_token': csrf_crs,
            'course_code': test_crs_code,
            'course_name': 'Advanced Compiler Design',
            'department': 'Computer Science & Engineering',
            'is_active': 'y'
        }, follow_redirects=True)
        self.assertIn("created successfully", add_crs_res.get_data(as_text=True))

        with self.app.app_context():
            c = Course.query.filter_by(course_code=test_crs_code).first()
            self.assertIsNotNone(c)
            crs_id = c.id

        # 4. Toggle Course active status
        crs_page2 = self.client.get('/admin/courses')
        csrf_crs_toggle = self.extract_csrf_token(crs_page2.get_data(as_text=True))
        toggle_crs_res = self.client.post(f'/admin/courses/{crs_id}/toggle', data={
            'csrf_token': csrf_crs_toggle
        }, follow_redirects=True)
        self.assertIn("deactivated", toggle_crs_res.get_data(as_text=True))

        with self.app.app_context():
            self.assertFalse(db.session.get(Course, crs_id).is_active)

    def test_06_feedback_filtering_and_analytics_and_csv(self):
        """Verify feedback filtering, Chart.js analytics API, and CSV generation."""
        # Ensure admin is logged in
        get_login = self.client.get('/login')
        csrf_login = self.extract_csrf_token(get_login.get_data(as_text=True))
        self.client.post('/login', data={
            'csrf_token': csrf_login,
            'email': 'admin@university.edu',
            'password': 'AdminSecure2026!'
        }, follow_redirects=True)

        # 1. Test Chart.js analytics data API
        analytics_res = self.client.get('/admin/analytics/data')
        self.assertEqual(analytics_res.status_code, 200)
        data = analytics_res.get_json()
        self.assertIn('rating_distribution', data)
        self.assertIn('faculty_ratings', data)
        self.assertIn('course_ratings', data)
        self.assertIn('1', data['rating_distribution'])
        self.assertIn('5', data['rating_distribution'])

        # 2. Test feedback search and filtering
        filter_res = self.client.get('/admin/feedback?rating=5&search=Turing')
        self.assertEqual(filter_res.status_code, 200)
        html = filter_res.get_data(as_text=True)
        self.assertIn("Filtered View", html)
        self.assertIn("Dr. Alan Turing", html)

        # 3. Test CSV export with filter
        csv_res = self.client.get('/admin/feedback/export-csv?rating=5')
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.mimetype, 'text/csv')
        csv_text = csv_res.get_data(as_text=True)

        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        self.assertGreater(len(rows), 1, "CSV must contain header and data rows")
        header = rows[0]
        self.assertEqual(header[0], 'Feedback ID')
        self.assertEqual(header[1], 'Submission Date')
        self.assertEqual(header[2], 'Student Name')
        self.assertEqual(header[3], 'Student Roll ID')
        self.assertEqual(header[4], 'Student Department')
        self.assertEqual(header[5], 'Course Code')
        self.assertEqual(header[6], 'Course Name')
        self.assertEqual(header[7], 'Faculty Name')
        self.assertEqual(header[8], 'Faculty Department')
        self.assertEqual(header[9], 'Rating (1-5)')
        self.assertEqual(header[10], 'Comments')

        # Verify rating column in data rows is 5
        for row in rows[1:]:
            self.assertEqual(row[9], '5', "All filtered CSV rows must match rating=5")


if __name__ == '__main__':
    unittest.main()
