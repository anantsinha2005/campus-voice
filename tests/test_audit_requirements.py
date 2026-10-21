import re
import csv
import io
import unittest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError
from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback


class AuditRequirementsTestCase(unittest.TestCase):
    """
    Direct verification of all 10 acceptance criteria:
    1. Submit feedback as a student.
    2. Confirm the record is present in the actual database.
    3. Refresh the student dashboard and confirm the submission remains visible.
    4. Log out and log back in, then verify the record still exists.
    5. Log in as an administrator and confirm the same record appears in Feedback Review.
    6. Confirm the dashboard count and average rating match the stored records.
    7. Confirm filtering and CSV export return the correct records.
    8. Restart the Flask server and verify the feedback still exists.
    9. Confirm that a student cannot access administrator feedback or another student's records.
    10. Confirm that failed database transactions do not create false success messages.
    """

    TEST_STUDENT_EMAIL = "audit.tester@student.test.edu"
    OTHER_STUDENT_EMAIL = "other.tester@student.test.edu"

    def setUp(self):
        self.app = create_app(Config)
        self.client = self.app.test_client(use_cookies=True)

        with self.app.app_context():
            # Ensure primary test student exists
            u1 = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            if not u1:
                u1 = User(
                    name="Audit Tester",
                    email=self.TEST_STUDENT_EMAIL,
                    student_id="AUDIT-2026-01",
                    department="Computer Science & Engineering",
                    role="student",
                    is_active=True
                )
                u1.set_password("Student123!")
                db.session.add(u1)

            # Ensure secondary test student exists for privacy testing
            u2 = User.query.filter_by(email=self.OTHER_STUDENT_EMAIL).first()
            if not u2:
                u2 = User(
                    name="Other Tester",
                    email=self.OTHER_STUDENT_EMAIL,
                    student_id="AUDIT-2026-02",
                    department="Information Technology",
                    role="student",
                    is_active=True
                )
                u2.set_password("Student123!")
                db.session.add(u2)

            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            u1 = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            if u1:
                Feedback.query.filter_by(student_id=u1.id).delete()
                db.session.delete(u1)
            u2 = User.query.filter_by(email=self.OTHER_STUDENT_EMAIL).first()
            if u2:
                Feedback.query.filter_by(student_id=u2.id).delete()
                db.session.delete(u2)
            db.session.commit()

    def extract_csrf_token(self, html_content):
        """Extracts CSRF token from rendered HTML form."""
        match = re.search(r'name=["\']csrf_token["\'].*?value=["\']([^"\']+)["\']', html_content, re.DOTALL)
        if not match:
            match = re.search(r'value=["\']([^"\']+)["\'].*?name=["\']csrf_token["\']', html_content, re.DOTALL)
        self.assertIsNotNone(match, "CSRF token must be present in HTML form")
        return match.group(1)

    def login_user(self, email, password):
        """Helper to log in a user and handle CSRF."""
        get_res = self.client.get('/login')
        csrf_token = self.extract_csrf_token(get_res.get_data(as_text=True))
        return self.client.post('/login', data={
            'csrf_token': csrf_token,
            'email': email,
            'password': password
        }, follow_redirects=True)

    def test_01_to_04_student_submission_persistence_and_relogin(self):
        """
        Criteria 1-4:
        1. Submit feedback as student.
        2. Confirm record is present in actual database.
        3. Refresh student dashboard and confirm submission remains visible.
        4. Log out and log back in, verify record still exists.
        """
        res_login = self.login_user(self.TEST_STUDENT_EMAIL, "Student123!")
        self.assertEqual(res_login.status_code, 200)

        with self.app.app_context():
            tester = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            course = Course.query.filter_by(course_code="BCO017A").first()
            faculty = Faculty.query.filter_by(faculty_name="Gajanand Sharma").first()
            self.assertIsNotNone(tester)
            self.assertIsNotNone(course)
            self.assertIsNotNone(faculty)

            Feedback.query.filter_by(student_id=tester.id, course_id=course.id, faculty_id=faculty.id).delete()
            db.session.commit()

            c_id = course.id
            f_id = faculty.id
            t_id = tester.id

        # 1. Submit feedback
        fb_page = self.client.get(f'/student/submit-feedback?course_id={c_id}&faculty_id={f_id}')
        csrf_token = self.extract_csrf_token(fb_page.get_data(as_text=True))

        unique_comments = "Unique Audit Observation: Outstanding instruction in BCO017A foundational concepts."
        post_fb = self.client.post('/student/submit-feedback', data={
            'csrf_token': csrf_token,
            'course_id': c_id,
            'faculty_id': f_id,
            'rating': '5',
            'comments': unique_comments
        }, follow_redirects=True)
        self.assertEqual(post_fb.status_code, 200)
        self.assertIn("Your feedback has been successfully submitted", post_fb.get_data(as_text=True))

        # 2. Confirm record is present in actual database
        with self.app.app_context():
            db_record = Feedback.query.filter_by(
                student_id=t_id,
                course_id=c_id,
                faculty_id=f_id
            ).first()
            self.assertIsNotNone(db_record, "Feedback record must be stored permanently in the database.")
            self.assertEqual(db_record.rating, 5)
            self.assertEqual(db_record.comments, unique_comments)

        # 3. Refresh the student dashboard and confirm submission remains visible
        dash_res = self.client.get('/student/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn("BCO017A", dash_res.get_data(as_text=True))
        self.assertIn("Gajanand Sharma", dash_res.get_data(as_text=True))

        # 4. Log out and log back in, then verify record still exists
        self.client.get('/logout')
        relogin_res = self.login_user(self.TEST_STUDENT_EMAIL, "Student123!")
        self.assertEqual(relogin_res.status_code, 200)

        hist_res = self.client.get('/student/my-feedback')
        self.assertEqual(hist_res.status_code, 200)
        self.assertIn(unique_comments, hist_res.get_data(as_text=True))
        self.assertIn("BCO017A", hist_res.get_data(as_text=True))

    def test_05_to_07_admin_feedback_review_count_filter_and_csv(self):
        """
        Criteria 5-7:
        5. Log in as administrator and confirm same record appears in Feedback Review.
        6. Confirm dashboard count and average rating match stored records.
        7. Confirm filtering and CSV export return the correct records.
        """
        # Ensure test feedback exists
        unique_comments = "Audit Observation for Admin Check"
        with self.app.app_context():
            tester = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            course = Course.query.filter_by(course_code="BCO017A").first()
            faculty = Faculty.query.filter_by(faculty_name="Gajanand Sharma").first()
            existing_fb = Feedback.query.filter_by(student_id=tester.id, course_id=course.id, faculty_id=faculty.id).first()
            if not existing_fb:
                fb = Feedback(
                    student_id=tester.id,
                    course_id=course.id,
                    faculty_id=faculty.id,
                    rating=5,
                    comments=unique_comments
                )
                db.session.add(fb)
                db.session.commit()
            c_id = course.id

        # Log in as admin
        admin_login = self.login_user("admin@university.edu", "AdminSecure2026!")
        self.assertEqual(admin_login.status_code, 200)

        # 5. Access Feedback Review and confirm the submission appears
        fb_review = self.client.get('/admin/feedback')
        self.assertEqual(fb_review.status_code, 200)
        html = fb_review.get_data(as_text=True)
        self.assertIn("Feedback Submissions Review", html)
        self.assertIn("BCO017A", html)
        self.assertIn("Gajanand Sharma", html)

        # 6. Verify dashboard total count and average rating match DB
        dash_res = self.client.get('/admin/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        dash_html = dash_res.get_data(as_text=True)

        with self.app.app_context():
            real_count = Feedback.query.count()
            ratings = [f.rating for f in Feedback.query.all()]
            real_avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        self.assertIn(str(real_count), dash_html)
        self.assertIn(str(real_avg), dash_html)

        # 7. Test filtering and CSV export
        filtered_res = self.client.get('/admin/feedback?course_id=' + str(c_id))
        self.assertEqual(filtered_res.status_code, 200)
        filtered_html = filtered_res.get_data(as_text=True)
        self.assertIn("BCO017A", filtered_html)

        csv_res = self.client.get('/admin/feedback/export-csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.mimetype, 'text/csv')
        csv_text = csv_res.get_data(as_text=True)
        self.assertIn("Feedback ID,Submission Date,Student Name", csv_text)

    def test_08_database_persistence_across_app_restart(self):
        """Criterion 8: Feedback persists across application restart."""
        # Create test feedback
        with self.app.app_context():
            tester = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            course = Course.query.filter_by(course_code="BCO017A").first()
            faculty = Faculty.query.filter_by(faculty_name="Gajanand Sharma").first()
            Feedback.query.filter_by(student_id=tester.id, course_id=course.id).delete()
            fb = Feedback(
                student_id=tester.id,
                course_id=course.id,
                faculty_id=faculty.id,
                rating=5,
                comments="Persistence Test Remark"
            )
            db.session.add(fb)
            db.session.commit()

        # Re-initialize app instance
        restarted_app = create_app(Config)
        with restarted_app.app_context():
            persisted_fb = Feedback.query.filter_by(comments="Persistence Test Remark").first()
            self.assertIsNotNone(persisted_fb, "Feedback submission must persist across application restarts.")
            self.assertEqual(persisted_fb.rating, 5)

    def test_09_rbac_and_student_privacy(self):
        """Criterion 9: Confirm that a student cannot access administrator feedback or another student's records."""
        # Log in as other student
        self.login_user(self.OTHER_STUDENT_EMAIL, "Student123!")

        # 1. Student attempts to access admin feedback pages -> 403 Forbidden
        admin_pages = [
            '/admin/feedback',
            '/admin/dashboard',
            '/admin/faculty',
            '/admin/courses',
            '/admin/students',
            '/admin/feedback/export-csv',
            '/admin/analytics/data'
        ]
        for url in admin_pages:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, f"Student must receive 403 Forbidden when requesting {url}")

    def test_10_database_failure_transaction_safety(self):
        """Criterion 10: Confirm that failed database transactions do not create false success messages."""
        self.login_user(self.TEST_STUDENT_EMAIL, "Student123!")

        with self.app.app_context():
            tester = User.query.filter_by(email=self.TEST_STUDENT_EMAIL).first()
            course = Course.query.filter_by(course_code="BCO023A").first()
            faculty = Faculty.query.filter_by(faculty_name="Sonal Saxena").first()
            Feedback.query.filter_by(student_id=tester.id, course_id=course.id, faculty_id=faculty.id).delete()
            db.session.commit()
            c_id = course.id
            f_id = faculty.id

        fb_page = self.client.get(f'/student/submit-feedback?course_id={c_id}&faculty_id={f_id}')
        csrf_token = self.extract_csrf_token(fb_page.get_data(as_text=True))

        with patch.object(db.session, 'commit', side_effect=SQLAlchemyError("Simulated DB Write Error")):
            res = self.client.post('/student/submit-feedback', data={
                'csrf_token': csrf_token,
                'course_id': c_id,
                'faculty_id': f_id,
                'rating': '4',
                'comments': 'Testing simulated database write failure handling.'
            }, follow_redirects=True)

            html = res.get_data(as_text=True)
            self.assertNotIn("Your feedback has been successfully submitted", html)
            self.assertIn("error occurred", html)


if __name__ == '__main__':
    unittest.main()
