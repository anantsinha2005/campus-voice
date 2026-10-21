import re
import unittest
from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback


class CatalogAssignmentsTestCase(unittest.TestCase):
    """
    Verification tests for Section G: Real Subject & Faculty assignments.
    """

    EXPECTED_CATALOG = [
        ("BCO017A", "Formal Languages and Automation Theory", "Gajanand Sharma"),
        ("BCO023A", "Design and Analysis of Algorithms", "Sonal Saxena"),
        ("BCO037B", "Advance Programming in Java", "Neha Solanki"),
        ("BCO019A", "Artificial Intelligence", "Ankur Agrawal"),
        ("BCO074C", "Minor Project", "Mahesh Kumar Joshi"),
        ("BCO681A", "Web Designing Using AI", "Mohit Parashar"),
    ]

    TEST_STUDENT_EMAIL = "catalog.tester@student.test.edu"

    def setUp(self):
        self.app = create_app(Config)
        self.client = self.app.test_client(use_cookies=True)

        with self.app.app_context():
            u = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            if not u:
                u = User(
                    name="Catalog Tester",
                    email=self.TEST_STUDENT_EMAIL,
                    student_id="CATALOG-TESTER-01",
                    department="Computer Science & Engineering",
                    role="student",
                    is_active=True
                )
                u.set_password("Student123!")
                db.session.add(u)
                db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            u = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            if u:
                Feedback.query.filter_by(student_id=u.id).delete()
                db.session.delete(u)
                db.session.commit()

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

    def test_01_active_catalog_exact_match(self):
        """Verify that exactly the 6 specified courses and 6 faculty members exist and are active."""
        with self.app.app_context():
            active_courses = Course.query.filter_by(is_active=True).all()
            self.assertEqual(len(active_courses), 6, "Exactly 6 active courses must exist.")

            active_faculty = Faculty.query.filter_by(is_active=True).all()
            self.assertEqual(len(active_faculty), 6, "Exactly 6 active faculty members must exist.")

            active_course_map = {c.course_code: c for c in active_courses}
            active_faculty_names = {f.faculty_name for f in active_faculty}

            for code, name, faculty_name in self.EXPECTED_CATALOG:
                self.assertIn(code, active_course_map, f"Course code {code} must be active.")
                c = active_course_map[code]
                self.assertEqual(c.course_name, name, f"Course name for {code} must match.")
                self.assertIsNotNone(c.assigned_faculty, f"Course {code} must have assigned faculty.")
                self.assertEqual(c.assigned_faculty.faculty_name, faculty_name)
                self.assertIn(faculty_name, active_faculty_names)

    def test_02_subject_display_name_format(self):
        """Verify subject display format: <Subject Name> (<Subject Code>)."""
        with self.app.app_context():
            for code, name, _ in self.EXPECTED_CATALOG:
                course = Course.query.filter_by(course_code=code).first()
                expected_format = f"{name} ({code})"
                self.assertEqual(course.display_name(), expected_format)

    def test_03_student_feedback_form_rendering(self):
        """Verify student feedback form renders display format and JavaScript mapping."""
        self.login_user(self.TEST_STUDENT_EMAIL, "Student123!")
        res = self.client.get('/student/submit-feedback')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        for code, name, faculty_name in self.EXPECTED_CATALOG:
            self.assertIn(f"{name} ({code})", html)
            self.assertIn(faculty_name, html)

        self.assertIn("COURSE_FACULTY_MAP", html)

    def test_04_mismatched_subject_faculty_submission_rejected(self):
        """Verify server prevents mismatched subject-to-faculty submissions."""
        self.login_user(self.TEST_STUDENT_EMAIL, "Student123!")

        with self.app.app_context():
            course_bco017a = Course.query.filter_by(course_code="BCO017A").first()
            faculty_sonal = Faculty.query.filter_by(faculty_name="Sonal Saxena").first()
            c_id = course_bco017a.id
            f_id = faculty_sonal.id

        form_res = self.client.get('/student/submit-feedback')
        csrf_token = self.extract_csrf_token(form_res.get_data(as_text=True))

        post_res = self.client.post('/student/submit-feedback', data={
            'csrf_token': csrf_token,
            'course_id': c_id,
            'faculty_id': f_id,
            'rating': '4',
            'comments': 'Deliberate mismatch test comment for verification.'
        }, follow_redirects=True)

        html = post_res.get_data(as_text=True)
        self.assertIn("Invalid assignment", html)

        with self.app.app_context():
            mismatched_db = Feedback.query.filter(
                Feedback.comments.like("%Deliberate mismatch test%")
            ).first()
            self.assertIsNone(mismatched_db, "Mismatched feedback submission must NOT be saved.")

    def test_05_submissions_work_for_all_subjects_and_clean_up(self):
        """Verify that valid student feedback submissions work for all catalog subjects."""
        login_res = self.login_user(self.TEST_STUDENT_EMAIL, "Student123!")
        self.assertEqual(login_res.status_code, 200)

        with self.app.app_context():
            student = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            for code, _, _ in self.EXPECTED_CATALOG:
                c = Course.query.filter_by(course_code=code).first()
                Feedback.query.filter_by(student_id=student.id, course_id=c.id).delete()
            db.session.commit()

        try:
            for idx, (code, _, faculty_name) in enumerate(self.EXPECTED_CATALOG, start=1):
                with self.app.app_context():
                    c = Course.query.filter_by(course_code=code).first()
                    f = Faculty.query.filter_by(faculty_name=faculty_name).first()
                    c_id = c.id
                    f_id = f.id

                form_res = self.client.get(f'/student/submit-feedback?course_id={c_id}&faculty_id={f_id}', follow_redirects=True)
                csrf_token = self.extract_csrf_token(form_res.get_data(as_text=True))

                comment = f"Test catalog verification remark {idx}."
                post_res = self.client.post('/student/submit-feedback', data={
                    'csrf_token': csrf_token,
                    'course_id': c_id,
                    'faculty_id': f_id,
                    'rating': str((idx % 5) + 1),
                    'comments': comment
                }, follow_redirects=True)

                self.assertEqual(post_res.status_code, 200)
                self.assertIn("Your feedback has been successfully submitted", post_res.get_data(as_text=True))
        finally:
            with self.app.app_context():
                student = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
                if student:
                    Feedback.query.filter_by(student_id=student.id).delete()
                    db.session.commit()

    def test_06_duplicate_feedback_prevention(self):
        """Verify that duplicate feedback for the same subject and faculty is rejected."""
        login_res = self.login_user(self.TEST_STUDENT_EMAIL, "Student123!")
        self.assertEqual(login_res.status_code, 200)

        with self.app.app_context():
            student = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            c = Course.query.filter_by(course_code="BCO017A").first()
            f = Faculty.query.filter_by(faculty_name="Gajanand Sharma").first()
            c_id = c.id
            f_id = f.id

            # Insert initial feedback
            fb = Feedback(
                student_id=student.id,
                course_id=c_id,
                faculty_id=f_id,
                rating=5,
                comments="Initial review before duplicate test."
            )
            db.session.add(fb)
            db.session.commit()

        form_res = self.client.get(f'/student/submit-feedback?course_id={c_id}&faculty_id={f_id}', follow_redirects=True)
        csrf_token = self.extract_csrf_token(form_res.get_data(as_text=True))

        dup_res = self.client.post('/student/submit-feedback', data={
            'csrf_token': csrf_token,
            'course_id': c_id,
            'faculty_id': f_id,
            'rating': '5',
            'comments': 'Second duplicate submission attempt should fail gracefully.'
        }, follow_redirects=True)

        html = dup_res.get_data(as_text=True)
        self.assertIn("already submitted feedback", html)

    def test_07_genuine_records_intact(self):
        """Verify that legitimate records (Anant Sinha) remain intact."""
        with self.app.app_context():
            anant = User.query.filter_by(email="anant@jecrc.edu.in").first()
            self.assertIsNotNone(anant, "Legitimate student account Anant Sinha must be preserved.")
            anant_fb = Feedback.query.filter_by(student_id=anant.id).first()
            self.assertIsNotNone(anant_fb, "Anant Sinha's genuine feedback must be preserved.")
            self.assertEqual(anant_fb.course.course_code, "BCO037B")
            self.assertEqual(anant_fb.faculty.faculty_name, "Neha Solanki")

    def test_08_admin_views_reflect_real_catalog(self):
        """Verify that admin courses and faculty views reflect the real catalog and assignments."""
        self.login_user("admin@university.edu", "AdminSecure2026!")

        courses_res = self.client.get('/admin/courses')
        self.assertEqual(courses_res.status_code, 200)
        c_html = courses_res.get_data(as_text=True)

        faculty_res = self.client.get('/admin/faculty')
        self.assertEqual(faculty_res.status_code, 200)
        f_html = faculty_res.get_data(as_text=True)

        for code, name, faculty_name in self.EXPECTED_CATALOG:
            self.assertIn(code, c_html)
            self.assertIn(faculty_name, c_html)
            self.assertIn(faculty_name, f_html)

    def test_09_bco681a_specific_workflow(self):
        """Dedicated test for BCO681A - Web Designing Using AI - Mohit Parashar."""
        with self.app.app_context():
            course = Course.query.filter_by(course_code="BCO681A").first()
            self.assertIsNotNone(course)
            self.assertEqual(course.course_name, "Web Designing Using AI")
            self.assertEqual(course.display_name(), "Web Designing Using AI (BCO681A)")
            self.assertIsNotNone(course.assigned_faculty)
            self.assertEqual(course.assigned_faculty.faculty_name, "Mohit Parashar")
            c_id = course.id
            f_id = course.assigned_faculty.id

        # Student submission flow
        self.login_user(self.TEST_STUDENT_EMAIL, "Student123!")

        form_res = self.client.get(f'/student/submit-feedback?course_id={c_id}&faculty_id={f_id}', follow_redirects=True)
        html = form_res.get_data(as_text=True)
        self.assertIn("Web Designing Using AI (BCO681A)", html)
        self.assertIn("Mohit Parashar", html)

        csrf_token = self.extract_csrf_token(html)
        comment_text = "BCO681A AI-driven web design test remark."

        post_res = self.client.post('/student/submit-feedback', data={
            'csrf_token': csrf_token,
            'course_id': c_id,
            'faculty_id': f_id,
            'rating': '5',
            'comments': comment_text
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertIn("Your feedback has been successfully submitted", post_res.get_data(as_text=True))

        # Admin verification
        self.client.get('/logout')
        self.login_user("admin@university.edu", "AdminSecure2026!")

        fb_html = self.client.get('/admin/feedback').get_data(as_text=True)
        self.assertIn("BCO681A", fb_html)
        self.assertIn("Mohit Parashar", fb_html)


if __name__ == '__main__':
    unittest.main()
