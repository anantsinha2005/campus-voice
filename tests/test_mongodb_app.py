"""
Automated test suite for Campus Voice MongoDB Atlas implementation.
Tests MongoDB connectivity, authentication, session persistence,
faculty/course CRUD, feedback submission, duplicate prevention,
admin analytics, CSV export, and security requirements without touching production data.
"""
import os
import unittest
from bson import ObjectId
from app import create_app
from app.config import TestingConfig
from app.db import get_mongo_client, get_db, init_indexes, close_db_client
from app.models import User, Faculty, Course, Feedback
from seed_data import seed_database


class MongoDBAppTestCase(unittest.TestCase):
    """Full application test suite using mongomock in-memory database."""

    @classmethod
    def setUpClass(cls):
        # Configure test environment
        os.environ['MONGODB_URI'] = 'mongomock://localhost/campus_voice_test'
        os.environ['MONGODB_DB_NAME'] = 'campus_voice_test'
        os.environ['WTF_CSRF_ENABLED'] = 'false'
        os.environ['SECRET_KEY'] = 'test-secret-key'

    def setUp(self):
        close_db_client()
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

        self.db = get_db()
        # Clean test collections
        self.db.users.delete_many({})
        self.db.faculties.delete_many({})
        self.db.courses.delete_many({})
        self.db.feedbacks.delete_many({})
        init_indexes(self.db)

    def tearDown(self):
        self.db.users.delete_many({})
        self.db.faculties.delete_many({})
        self.db.courses.delete_many({})
        self.db.feedbacks.delete_many({})
        self.app_context.pop()
        close_db_client()

    def test_01_mongodb_connectivity_and_indexes(self):
        """Test MongoDB client connection and index creation."""
        self.assertIsNotNone(self.db)
        init_indexes(self.db)
        # Verify collection access
        self.assertEqual(self.db.users.count_documents({}), 0)

    def test_02_user_model_and_password_hashing(self):
        """Test password hashing, verification, and role methods."""
        user = User(
            name="Test Student",
            email="student@univ.edu",
            student_id="STU1001",
            department="Computer Science & Engineering",
            role="student"
        )
        user.set_password("StudentPass123!")
        user.save()

        # Retrieve user from MongoDB
        fetched = User.find_by_email("student@univ.edu")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Test Student")
        self.assertEqual(fetched.student_id, "STU1001")
        self.assertTrue(fetched.is_student())
        self.assertFalse(fetched.is_admin())
        self.assertTrue(fetched.check_password("StudentPass123!"))
        self.assertFalse(fetched.check_password("WrongPassword"))

    def test_03_login_consistency_and_bad_credentials(self):
        """Test authentication flow, bad credentials rejection, and session user loader."""
        user = User(
            name="Valid Student",
            email="valid@univ.edu",
            student_id="STU2001",
            department="Computer Science & Engineering",
            role="student"
        )
        user.set_password("CorrectPassword123!")
        user.save()

        # 1. Correct credentials login
        res = self.client.post('/login', data={
            'email': 'valid@univ.edu',
            'password': 'CorrectPassword123!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome back, Valid Student!", res.data)

        # 2. Bad password rejected
        self.client.get('/logout', follow_redirects=True)
        bad_pw_res = self.client.post('/login', data={
            'email': 'valid@univ.edu',
            'password': 'BadPassword!'
        }, follow_redirects=True)
        self.assertIn(b"Invalid email address or password", bad_pw_res.data)

        # 3. Non-existent email rejected
        unknown_res = self.client.post('/login', data={
            'email': 'unknown@univ.edu',
            'password': 'SomePassword123!'
        }, follow_redirects=True)
        self.assertIn(b"Invalid email address or password", unknown_res.data)

        # 4. Deactivated user rejected
        user.is_active = False
        user.save()
        deact_res = self.client.post('/login', data={
            'email': 'valid@univ.edu',
            'password': 'CorrectPassword123!'
        }, follow_redirects=True)
        self.assertIn(b"Your account has been deactivated", deact_res.data)

    def test_04_student_registration(self):
        """Test student self-registration."""
        res = self.client.post('/register', data={
            'name': 'New Student',
            'email': 'newstudent@univ.edu',
            'student_id': 'STU3001',
            'department': 'Information Technology',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Your student account has been created successfully", res.data)

        user = User.find_by_email('newstudent@univ.edu')
        self.assertIsNotNone(user)
        self.assertEqual(user.role, 'student')
        self.assertEqual(user.student_id, 'STU3001')

    def test_05_faculty_and_course_crud(self):
        """Test admin faculty and course creation, editing, and status toggling."""
        # Create Admin
        admin = User(
            name="System Admin",
            email="admin@univ.edu",
            department="Administration",
            role="admin"
        )
        admin.set_password("AdminSecret123!")
        admin.save()

        # Login as Admin
        self.client.post('/login', data={'email': 'admin@univ.edu', 'password': 'AdminSecret123!'}, follow_redirects=True)

        # 1. Add Faculty
        fac_res = self.client.post('/admin/faculty', data={
            'faculty_name': 'Dr. Alan Turing',
            'department': 'Computer Science & Engineering',
            'email': 'turing@univ.edu',
            'is_active': 'y'
        }, follow_redirects=True)
        self.assertIn(b"Dr. Alan Turing", fac_res.data)
        faculty = Faculty.find_by_name('Dr. Alan Turing')
        self.assertIsNotNone(faculty)

        # 2. Edit Faculty
        edit_fac_res = self.client.post(f'/admin/faculty/{faculty.id}/edit', data={
            'faculty_name': 'Prof. Alan M. Turing',
            'department': 'Computer Science & Engineering',
            'email': 'turing@univ.edu',
            'is_active': 'y'
        }, follow_redirects=True)
        self.assertIn(b"updated successfully", edit_fac_res.data)
        updated_fac = Faculty.get_by_id(faculty.id)
        self.assertEqual(updated_fac.faculty_name, 'Prof. Alan M. Turing')

        # 3. Toggle Faculty Status
        self.client.post(f'/admin/faculty/{faculty.id}/toggle', follow_redirects=True)
        toggled_fac = Faculty.get_by_id(faculty.id)
        self.assertFalse(toggled_fac.is_active)
        self.client.post(f'/admin/faculty/{faculty.id}/toggle', follow_redirects=True)
        self.assertTrue(Faculty.get_by_id(faculty.id).is_active)

        # 4. Add Course
        crs_res = self.client.post('/admin/courses', data={
            'course_name': 'Theory of Computation',
            'course_code': 'CS301',
            'department': 'Computer Science & Engineering',
            'faculty_id': faculty.id,
            'is_active': 'y'
        }, follow_redirects=True)
        self.assertIn(b"CS301", crs_res.data)
        course = Course.find_by_code('CS301')
        self.assertIsNotNone(course)
        self.assertEqual(course.faculty_id, faculty.id)
        self.assertEqual(course.assigned_faculty.faculty_name, 'Prof. Alan M. Turing')

        # 5. Edit Course
        self.client.post(f'/admin/courses/{course.id}/edit', data={
            'course_name': 'Advanced Theory of Computation',
            'course_code': 'CS301',
            'department': 'Computer Science & Engineering',
            'faculty_id': faculty.id,
            'is_active': 'y'
        }, follow_redirects=True)
        self.assertEqual(Course.get_by_id(course.id).course_name, 'Advanced Theory of Computation')

    def test_06_student_feedback_submission_and_duplicate_prevention(self):
        """Test feedback submission and duplicate prevention."""
        # Create Student
        student = User(
            name="Feedback Submitter",
            email="submitter@univ.edu",
            student_id="STU5001",
            department="Computer Science & Engineering",
            role="student"
        )
        student.set_password("Password123!")
        student.save()

        # Create Faculty & Course
        fac = Faculty(faculty_name="Dr. Ada Lovelace", department="Computer Science & Engineering")
        fac.save()
        crs = Course(course_name="Programming Paradigms", course_code="CS101", department="Computer Science & Engineering", faculty_id=fac.id)
        crs.save()

        # Login as student
        self.client.post('/login', data={'email': 'submitter@univ.edu', 'password': 'Password123!'}, follow_redirects=True)

        # 1. Submit feedback
        fb_res = self.client.post('/student/submit-feedback', data={
            'course_id': crs.id,
            'faculty_id': fac.id,
            'rating': '5',
            'comments': 'Exceptional teaching!'
        }, follow_redirects=True)
        self.assertIn(b"Your feedback has been successfully submitted", fb_res.data)

        # Verify feedback in MongoDB
        fb = Feedback.find_one({'student_id': student.id, 'course_id': crs.id, 'faculty_id': fac.id})
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.comments, 'Exceptional teaching!')
        self.assertEqual(fb.rating_label, 'Excellent')

        # 2. Duplicate submission prevention
        dup_res = self.client.post('/student/submit-feedback', data={
            'course_id': crs.id,
            'faculty_id': fac.id,
            'rating': '4',
            'comments': 'Second review should fail.'
        }, follow_redirects=True)
        self.assertIn(b"already submitted feedback", dup_res.data)

        # Total feedback count must remain exactly 1
        self.assertEqual(Feedback.count(), 1)

    def test_07_admin_analytics_and_csv_export(self):
        """Test admin analytics dashboard, Chart.js data endpoint, and CSV export."""
        # Create Admin
        admin = User(name="Analyst Admin", email="analyst@univ.edu", department="Admin", role="admin")
        admin.set_password("AdminPass123!")
        admin.save()

        # Create student, faculty, course, feedback
        stu = User(name="Student A", email="stua@univ.edu", student_id="STUA", department="CSE", role="student")
        stu.save()
        fac = Faculty(faculty_name="Prof. Shannon", department="CSE")
        fac.save()
        crs = Course(course_name="Information Theory", course_code="CS401", department="CSE", faculty_id=fac.id)
        crs.save()
        fb = Feedback(student_id=stu.id, faculty_id=fac.id, course_id=crs.id, rating=5, comments="Superb course.")
        fb.save()

        # Login as Admin
        self.client.post('/login', data={'email': 'analyst@univ.edu', 'password': 'AdminPass123!'}, follow_redirects=True)

        # 1. Dashboard
        dash_res = self.client.get('/admin/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b"Information Theory", dash_res.data)

        # 2. Analytics JSON endpoint
        analytics_res = self.client.get('/admin/analytics/data')
        self.assertEqual(analytics_res.status_code, 200)
        data = analytics_res.get_json()
        self.assertIn('rating_distribution', data)
        self.assertEqual(data['rating_distribution']['5'], 1)

        # 3. Filtered Feedback List
        list_res = self.client.get(f'/admin/feedback?course_id={crs.id}')
        self.assertEqual(list_res.status_code, 200)
        self.assertIn(b"Superb course", list_res.data)

        # 4. CSV Export
        csv_res = self.client.get(f'/admin/feedback/export-csv?course_id={crs.id}')
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.mimetype, 'text/csv')
        self.assertIn(b"Superb course", csv_res.data)
        self.assertIn(b"Prof. Shannon", csv_res.data)

    def test_08_admin_password_security_no_fallback(self):
        """Test that seed_database strictly requires ADMIN_PASSWORD environment variable."""
        # Ensure ADMIN_PASSWORD is unset
        if 'ADMIN_PASSWORD' in os.environ:
            del os.environ['ADMIN_PASSWORD']
        self.app.config['ADMIN_PASSWORD'] = None

        # Attempting to seed without ADMIN_PASSWORD must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            seed_database(self.app)
        self.assertIn("ADMIN_PASSWORD environment variable must be set", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
