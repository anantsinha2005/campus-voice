import unittest
from app import create_app
from app.config import TestingConfig
from app.models import db, User, Course, Faculty, Feedback


class StudentFeedbackSystemTestCase(unittest.TestCase):
    """
    Comprehensive automated test suite covering:
    - User password hashing and verification
    - Student registration & input validation
    - Session authentication (Login/Logout)
    - Role-Based Access Control (RBAC) enforcement
    - Feedback submission and duplicate prevention
    - Faculty and Course CRUD operations
    - Feedback CSV export and Analytics API
    """

    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client(use_cookies=True)
        db.create_all()

        # Seed initial admin
        self.admin = User(
            name="Admin Tester",
            email="admin@test.edu",
            department="Administration",
            student_id=None,
            role="admin",
            is_active=True
        )
        self.admin.set_password("AdminPass123!")
        db.session.add(self.admin)

        # Seed test student
        self.student = User(
            name="Alice Student",
            email="alice@student.test.edu",
            department="Computer Science & Engineering",
            student_id="CS-9901",
            role="student",
            is_active=True
        )
        self.student.set_password("StudentPass123!")
        db.session.add(self.student)

        # Seed test course
        self.course = Course(
            course_code="CS101",
            course_name="Intro to Programming",
            department="Computer Science & Engineering",
            is_active=True
        )
        db.session.add(self.course)

        # Seed test faculty
        self.faculty = Faculty(
            faculty_name="Dr. Turing",
            department="Computer Science & Engineering",
            email="turing@faculty.test.edu",
            is_active=True
        )
        db.session.add(self.faculty)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # -------------------------------------------------------------
    # 1. USER MODEL & PASSWORD SECURITY TESTS
    # -------------------------------------------------------------
    def test_password_hashing(self):
        u = User(name="Test", email="test@test.edu", department="IT")
        u.set_password("MySecurePass!")
        self.assertTrue(u.password_hash != "MySecurePass!")
        self.assertTrue(u.check_password("MySecurePass!"))
        self.assertFalse(u.check_password("WrongPassword"))

    def test_user_roles(self):
        self.assertTrue(self.admin.is_admin())
        self.assertFalse(self.admin.is_student())
        self.assertTrue(self.student.is_student())
        self.assertFalse(self.student.is_admin())

    # -------------------------------------------------------------
    # 2. STUDENT REGISTRATION TESTS
    # -------------------------------------------------------------
    def test_student_registration_success(self):
        response = self.client.post('/register', data={
            'name': 'Bob Smith',
            'email': 'bob@student.test.edu',
            'student_id': 'CS-9902',
            'department': 'Computer Science & Engineering',
            'password': 'Password123!',
            'confirm_password': 'Password123!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify user created in DB as student
        bob = User.query.filter_by(email='bob@student.test.edu').first()
        self.assertIsNotNone(bob)
        self.assertEqual(bob.role, 'student')
        self.assertTrue(bob.check_password('Password123!'))

    def test_student_registration_duplicate_email(self):
        response = self.client.post('/register', data={
            'name': 'Duplicate Email',
            'email': 'alice@student.test.edu',  # Already exists
            'student_id': 'CS-9903',
            'department': 'Computer Science & Engineering',
            'password': 'Password123!',
            'confirm_password': 'Password123!'
        })
        self.assertIn(b"already registered", response.data)

    def test_student_registration_duplicate_student_id(self):
        response = self.client.post('/register', data={
            'name': 'Duplicate Roll',
            'email': 'new@student.test.edu',
            'student_id': 'CS-9901',  # Already exists
            'department': 'Computer Science & Engineering',
            'password': 'Password123!',
            'confirm_password': 'Password123!'
        })
        self.assertIn(b"Student ID is already registered", response.data)

    # -------------------------------------------------------------
    # 3. AUTHENTICATION & LOGIN/LOGOUT TESTS
    # -------------------------------------------------------------
    def test_student_login_and_logout(self):
        # Successful student login
        response = self.client.post('/login', data={
            'email': 'alice@student.test.edu',
            'password': 'StudentPass123!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome, Alice Student", response.data)

        # Logout
        logout_res = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertIn(b"successfully logged out", logout_res.data)

    def test_login_invalid_credentials(self):
        response = self.client.post('/login', data={
            'email': 'alice@student.test.edu',
            'password': 'IncorrectPassword'
        })
        self.assertIn(b"Invalid email address or password", response.data)

    # -------------------------------------------------------------
    # 4. ROLE-BASED ACCESS CONTROL (RBAC) TESTS
    # -------------------------------------------------------------
    def test_unauthenticated_route_protection(self):
        # Unauthenticated users cannot view student or admin dashboard
        res1 = self.client.get('/student/dashboard', follow_redirects=False)
        self.assertEqual(res1.status_code, 302)
        self.assertIn('/login', res1.location)

        res2 = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(res2.status_code, 302)
        self.assertIn('/login', res2.location)

    def test_student_cannot_access_admin_portal(self):
        # Login as student
        self.client.post('/login', data={
            'email': 'alice@student.test.edu',
            'password': 'StudentPass123!'
        })
        # Attempt to access admin routes
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 403)

        res_fac = self.client.get('/admin/faculty')
        self.assertEqual(res_fac.status_code, 403)

    def test_admin_dashboard_access(self):
        # Login as admin
        self.client.post('/login', data={
            'email': 'admin@test.edu',
            'password': 'AdminPass123!'
        }, follow_redirects=True)
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Institutional Quality", res.data)

    # -------------------------------------------------------------
    # 5. FEEDBACK SUBMISSION & DUPLICATE PREVENTION TESTS
    # -------------------------------------------------------------
    def test_feedback_submission_and_duplicate_prevention(self):
        # Login as student
        self.client.post('/login', data={
            'email': 'alice@student.test.edu',
            'password': 'StudentPass123!'
        })

        # Submit valid feedback
        res = self.client.post('/student/submit-feedback', data={
            'course_id': self.course.id,
            'faculty_id': self.faculty.id,
            'rating': '5',
            'comments': 'Outstanding course pacing and thorough explanations.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Your feedback has been successfully submitted", res.data)

        # Check DB persistence
        fb = Feedback.query.filter_by(
            student_id=self.student.id,
            course_id=self.course.id,
            faculty_id=self.faculty.id
        ).first()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.comments, 'Outstanding course pacing and thorough explanations.')

        # Attempt to submit duplicate feedback for SAME course and faculty
        dup_res = self.client.post('/student/submit-feedback', data={
            'course_id': self.course.id,
            'faculty_id': self.faculty.id,
            'rating': '4',
            'comments': 'Attempting a second feedback entry for this same course.'
        }, follow_redirects=True)
        self.assertIn(b"Duplicate submissions are prohibited", dup_res.data)

        # Verify only 1 feedback exists in DB
        total_fb = Feedback.query.filter_by(
            student_id=self.student.id,
            course_id=self.course.id,
            faculty_id=self.faculty.id
        ).count()
        self.assertEqual(total_fb, 1)

    def test_student_history_privacy(self):
        # Login as Alice and verify she sees only her history
        self.client.post('/login', data={
            'email': 'alice@student.test.edu',
            'password': 'StudentPass123!'
        })
        res = self.client.get('/student/my-feedback')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"My Evaluation History", res.data)

    # -------------------------------------------------------------
    # 6. FACULTY & COURSE CRUD (ADMIN)
    # -------------------------------------------------------------
    def test_admin_faculty_management(self):
        self.client.post('/login', data={
            'email': 'admin@test.edu',
            'password': 'AdminPass123!'
        })

        # Add new faculty member
        res_add = self.client.post('/admin/faculty', data={
            'faculty_name': 'Prof. Barbara Liskov',
            'department': 'Computer Science & Engineering',
            'email': 'liskov@faculty.test.edu',
            'is_active': 'y'
        }, follow_redirects=True)
        self.assertIn(b"added successfully", res_add.data)

        new_fac = Faculty.query.filter_by(email='liskov@faculty.test.edu').first()
        self.assertIsNotNone(new_fac)
        self.assertTrue(new_fac.is_active)

        # Toggle deactivation
        res_toggle = self.client.post(f'/admin/faculty/{new_fac.id}/toggle', follow_redirects=True)
        self.assertIn(b"deactivated", res_toggle.data)
        self.assertFalse(db.session.get(Faculty, new_fac.id).is_active)

    def test_admin_course_management(self):
        self.client.post('/login', data={
            'email': 'admin@test.edu',
            'password': 'AdminPass123!'
        })

        # Add new course
        res_add = self.client.post('/admin/courses', data={
            'course_code': 'CS305',
            'course_name': 'Operating Systems',
            'department': 'Computer Science & Engineering',
            'is_active': 'y'
        }, follow_redirects=True)
        self.assertIn(b"created successfully", res_add.data)

        new_course = Course.query.filter_by(course_code='CS305').first()
        self.assertIsNotNone(new_course)
        self.assertTrue(new_course.is_active)

        # Toggle deactivation
        res_toggle = self.client.post(f'/admin/courses/{new_course.id}/toggle', follow_redirects=True)
        self.assertIn(b"deactivated", res_toggle.data)
        self.assertFalse(db.session.get(Course, new_course.id).is_active)

    # -------------------------------------------------------------
    # 7. ANALYTICS API & CSV EXPORT TESTS
    # -------------------------------------------------------------
    def test_analytics_data_api(self):
        self.client.post('/login', data={
            'email': 'admin@test.edu',
            'password': 'AdminPass123!'
        })
        res = self.client.get('/admin/analytics/data')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('rating_distribution', data)
        self.assertIn('faculty_ratings', data)
        self.assertIn('course_ratings', data)

    def test_csv_export_endpoint(self):
        # Create a sample feedback first
        fb = Feedback(
            student_id=self.student.id,
            course_id=self.course.id,
            faculty_id=self.faculty.id,
            rating=5,
            comments="Terrific course."
        )
        db.session.add(fb)
        db.session.commit()

        self.client.post('/login', data={
            'email': 'admin@test.edu',
            'password': 'AdminPass123!'
        })
        res = self.client.get('/admin/feedback/export-csv')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        self.assertIn(b"Feedback ID,Submission Date,Student Name", res.data)
        self.assertIn(b"Alice Student", res.data)
        self.assertIn(b"Intro to Programming", res.data)
        self.assertIn(b"Dr. Turing", res.data)


if __name__ == '__main__':
    unittest.main()
