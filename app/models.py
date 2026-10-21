from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    User model representing both Students and Administrators.
    Role can be 'student' or 'admin'.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    student_id = db.Column(db.String(50), unique=True, index=True, nullable=True)  # Nullable for admins
    department = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='student', nullable=False)  # 'student' or 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    feedbacks = db.relationship(
        'Feedback',
        backref='student',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def set_password(self, password: str):
        """Hashes password using secure Werkzeug pbkdf2/scrypt algorithm."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies given password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        """Checks if current user has administrator privileges."""
        return self.role == 'admin'

    def is_student(self) -> bool:
        """Checks if current user is a registered student."""
        return self.role == 'student'

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


class Course(db.Model):
    """
    Course model representing academic courses available for review.
    """
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(150), nullable=False)
    course_code = db.Column(db.String(50), unique=True, index=True, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculties.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    feedbacks = db.relationship('Feedback', backref='course', lazy='dynamic')
    assigned_faculty = db.relationship('Faculty', backref=db.backref('assigned_courses', lazy='dynamic'))

    def display_name(self) -> str:
        """Formatted display name: Subject Name (Subject Code)."""
        return f"{self.course_name} ({self.course_code})"

    def average_rating(self) -> float:
        """Computes current average rating for this course."""
        ratings = [f.rating for f in self.feedbacks.all()]
        return round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    def feedback_count(self) -> int:
        return self.feedbacks.count()

    def __repr__(self):
        return f'<Course {self.course_code}: {self.course_name}>'


class Faculty(db.Model):
    """
    Faculty model representing academic instructors and professors.
    """
    __tablename__ = 'faculties'

    id = db.Column(db.Integer, primary_key=True)
    faculty_name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    feedbacks = db.relationship('Feedback', backref='faculty', lazy='dynamic')

    def average_rating(self) -> float:
        """Computes current average rating for this faculty member."""
        ratings = [f.rating for f in self.feedbacks.all()]
        return round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    def feedback_count(self) -> int:
        return self.feedbacks.count()

    def __repr__(self):
        return f'<Faculty {self.faculty_name} ({self.department})>'


class Feedback(db.Model):
    """
    Feedback model capturing rating and qualitative review from a student
    for a faculty member teaching a specific course.
    """
    __tablename__ = 'feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculties.id', ondelete='CASCADE'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # Rating from 1 to 5 (1=Terrible, 5=Excellent)
    comments = db.Column(db.Text, nullable=True, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    RATING_SCALE = {
        5: "Excellent",
        4: "Good",
        3: "Average",
        2: "Poor",
        1: "Terrible"
    }

    # Enforce uniqueness so a student cannot submit duplicate feedback for the same course and faculty
    __table_args__ = (
        db.UniqueConstraint('student_id', 'faculty_id', 'course_id', name='uq_student_faculty_course'),
    )

    @property
    def rating_label(self) -> str:
        """Returns the textual rating label corresponding to the corrected 1-5 scale."""
        return self.RATING_SCALE.get(self.rating, "Average")

    def __repr__(self):
        return f'<Feedback Student:{self.student_id} Course:{self.course_id} Faculty:{self.faculty_id} Rating:{self.rating} ({self.rating_label})>'
