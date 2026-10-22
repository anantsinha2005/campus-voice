"""
MongoDB data models and document wrappers for Campus Voice.
Provides object-oriented abstractions for Users, Faculties, Courses, and Feedbacks
with complete backward-compatibility for authentication, routes, and Jinja templates.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db, Pagination

# Compatibility alias for legacy imports
db = None


def to_id_query(val: Any) -> Dict[str, Any]:
    """
    Builds a flexible MongoDB query filter for _id matching either
    ObjectId or string representation.
    """
    if isinstance(val, ObjectId):
        return {"_id": val}
    if isinstance(val, str) and ObjectId.is_valid(val):
        return {"$or": [{"_id": ObjectId(val)}, {"_id": val}]}
    return {"_id": val}


class FeedbackQueryProxy:
    """
    Proxy enabling chained query syntax (e.g. user.feedbacks.count(),
    user.feedbacks.all()) compatible with existing Jinja templates and routes.
    """
    def __init__(self, filter_dict: Dict[str, Any]):
        self.filter_dict = filter_dict

    def count(self) -> int:
        db = get_db()
        return db.feedbacks.count_documents(self.filter_dict)

    def all(self) -> List['Feedback']:
        db = get_db()
        cursor = db.feedbacks.find(self.filter_dict).sort("created_at", -1)
        return [Feedback.from_doc(d) for d in cursor]

    def __iter__(self):
        return iter(self.all())

    def __len__(self) -> int:
        return self.count()


class CourseQueryProxy:
    """
    Proxy enabling chained query syntax for assigned courses
    (e.g. faculty.assigned_courses.all()).
    """
    def __init__(self, filter_dict: Dict[str, Any]):
        self.filter_dict = filter_dict

    def count(self) -> int:
        db = get_db()
        return db.courses.count_documents(self.filter_dict)

    def all(self) -> List['Course']:
        db = get_db()
        cursor = db.courses.find(self.filter_dict).sort("course_name", 1)
        return [Course.from_doc(d) for d in cursor]

    def __iter__(self):
        return iter(self.all())

    def __len__(self) -> int:
        return self.count()


class User(UserMixin):
    """
    User model representing both Students and Administrators.
    Role can be 'student' or 'admin'.
    """
    def __init__(
        self,
        name: str,
        email: str,
        department: str,
        password_hash: str = '',
        student_id: Optional[str] = None,
        role: str = 'student',
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        _id: Optional[Any] = None
    ):
        self._id = _id or ObjectId()
        self.name = name
        self.email = email.strip().lower() if email else ''
        self.student_id = student_id.strip().upper() if student_id else None
        self.department = department
        self.password_hash = password_hash
        self.role = role
        self._is_active = is_active
        self.created_at = created_at or datetime.utcnow()

    @property
    def is_active(self) -> bool:
        """Returns account active status."""
        return self._is_active

    @is_active.setter
    def is_active(self, val: bool):
        self._is_active = bool(val)

    @property
    def id(self) -> str:
        """Returns string representation of document _id for routes and templates."""
        return str(self._id)

    def get_id(self) -> str:
        """Flask-Login required method returning the unique identifier as a string."""
        return str(self._id)

    def set_password(self, password: str):
        """Hashes password using secure Werkzeug pbkdf2/scrypt algorithm."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies given password against stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        """Checks if current user has administrator privileges."""
        return self.role == 'admin'

    def is_student(self) -> bool:
        """Checks if current user is a registered student."""
        return self.role == 'student'

    @property
    def feedbacks(self) -> FeedbackQueryProxy:
        """Dynamic feedback query proxy for this user."""
        return FeedbackQueryProxy({
            "$or": [
                {"student_id": str(self._id)},
                {"student_id": self._id}
            ]
        })

    def to_doc(self) -> Dict[str, Any]:
        """Serializes instance to MongoDB document dict."""
        return {
            "_id": self._id,
            "name": self.name,
            "email": self.email,
            "student_id": self.student_id,
            "department": self.department,
            "password_hash": self.password_hash,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at
        }

    @classmethod
    def from_doc(cls, doc: Optional[Dict[str, Any]]) -> Optional['User']:
        """Builds User instance from a MongoDB document."""
        if not doc:
            return None
        return cls(
            _id=doc.get('_id'),
            name=doc.get('name', ''),
            email=doc.get('email', ''),
            student_id=doc.get('student_id'),
            department=doc.get('department', ''),
            password_hash=doc.get('password_hash', ''),
            role=doc.get('role', 'student'),
            is_active=doc.get('is_active', True),
            created_at=doc.get('created_at', datetime.utcnow())
        )

    def save(self) -> 'User':
        """Upserts the user document in MongoDB."""
        db = get_db()
        db.users.replace_one(
            {"_id": self._id},
            self.to_doc(),
            upsert=True
        )
        return self

    @classmethod
    def get_by_id(cls, user_id: Any) -> Optional['User']:
        """Finds user by ObjectId or string ID."""
        if not user_id:
            return None
        db = get_db()
        doc = db.users.find_one(to_id_query(user_id))
        return cls.from_doc(doc)

    @classmethod
    def find_by_email(cls, email: str) -> Optional['User']:
        """Finds user by normalized email address."""
        if not email:
            return None
        db = get_db()
        doc = db.users.find_one({"email": email.strip().lower()})
        return cls.from_doc(doc)

    @classmethod
    def find_by_student_id(cls, student_id: str) -> Optional['User']:
        """Finds student by normalized student ID."""
        if not student_id:
            return None
        db = get_db()
        doc = db.users.find_one({"student_id": student_id.strip().upper()})
        return cls.from_doc(doc)

    @classmethod
    def all(
        cls,
        filter_dict: Optional[Dict[str, Any]] = None,
        sort_field: str = 'created_at',
        sort_dir: int = -1
    ) -> List['User']:
        """Retrieves list of users matching filter."""
        db = get_db()
        cursor = db.users.find(filter_dict or {}).sort(sort_field, sort_dir)
        return [cls.from_doc(d) for d in cursor]

    @classmethod
    def count(cls, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Returns document count matching filter."""
        db = get_db()
        return db.users.count_documents(filter_dict or {})

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


class Faculty:
    """
    Faculty model representing academic instructors and professors.
    """
    def __init__(
        self,
        faculty_name: str,
        department: str,
        email: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        _id: Optional[Any] = None
    ):
        self._id = _id or ObjectId()
        self.faculty_name = faculty_name.strip()
        self.department = department.strip()
        self.email = email.strip().lower() if email and email.strip() else None
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()

    @property
    def id(self) -> str:
        return str(self._id)

    @property
    def assigned_courses(self) -> CourseQueryProxy:
        """Returns query proxy for courses assigned to this faculty."""
        return CourseQueryProxy({
            "$or": [
                {"faculty_id": str(self._id)},
                {"faculty_id": self._id}
            ]
        })

    @property
    def feedbacks(self) -> FeedbackQueryProxy:
        """Returns query proxy for feedback evaluations received by this faculty."""
        return FeedbackQueryProxy({
            "$or": [
                {"faculty_id": str(self._id)},
                {"faculty_id": self._id}
            ]
        })

    def average_rating(self) -> float:
        """Computes current average rating for this faculty member."""
        feedbacks = self.feedbacks.all()
        if not feedbacks:
            return 0.0
        return round(sum(f.rating for f in feedbacks) / len(feedbacks), 2)

    def feedback_count(self) -> int:
        """Computes total number of evaluations received."""
        return self.feedbacks.count()

    def to_doc(self) -> Dict[str, Any]:
        """Serializes instance to MongoDB document dict."""
        return {
            "_id": self._id,
            "faculty_name": self.faculty_name,
            "department": self.department,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at
        }

    @classmethod
    def from_doc(cls, doc: Optional[Dict[str, Any]]) -> Optional['Faculty']:
        """Builds Faculty instance from a MongoDB document."""
        if not doc:
            return None
        return cls(
            _id=doc.get('_id'),
            faculty_name=doc.get('faculty_name', ''),
            department=doc.get('department', ''),
            email=doc.get('email'),
            is_active=doc.get('is_active', True),
            created_at=doc.get('created_at', datetime.utcnow())
        )

    def save(self) -> 'Faculty':
        """Upserts the faculty document in MongoDB."""
        db = get_db()
        db.faculties.replace_one(
            {"_id": self._id},
            self.to_doc(),
            upsert=True
        )
        return self

    @classmethod
    def get_by_id(cls, faculty_id: Any) -> Optional['Faculty']:
        """Finds faculty by ObjectId or string ID."""
        if not faculty_id:
            return None
        db = get_db()
        doc = db.faculties.find_one(to_id_query(faculty_id))
        return cls.from_doc(doc)

    @classmethod
    def find_by_name(cls, name: str) -> Optional['Faculty']:
        """Finds faculty by exact name."""
        if not name:
            return None
        db = get_db()
        doc = db.faculties.find_one({"faculty_name": name.strip()})
        return cls.from_doc(doc)

    @classmethod
    def find_by_email(cls, email: str) -> Optional['Faculty']:
        """Finds faculty by normalized email."""
        if not email:
            return None
        db = get_db()
        doc = db.faculties.find_one({"email": email.strip().lower()})
        return cls.from_doc(doc)

    @classmethod
    def all(
        cls,
        filter_dict: Optional[Dict[str, Any]] = None,
        sort_field: str = 'faculty_name',
        sort_dir: int = 1
    ) -> List['Faculty']:
        """Retrieves list of faculties matching filter."""
        db = get_db()
        cursor = db.faculties.find(filter_dict or {}).sort(sort_field, sort_dir)
        return [cls.from_doc(d) for d in cursor]

    @classmethod
    def count(cls, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Returns document count matching filter."""
        db = get_db()
        return db.faculties.count_documents(filter_dict or {})

    def __repr__(self):
        return f'<Faculty {self.faculty_name} ({self.department})>'


class Course:
    """
    Course model representing academic courses available for review.
    """
    def __init__(
        self,
        course_name: str,
        course_code: str,
        department: str,
        faculty_id: Optional[Any] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        _id: Optional[Any] = None
    ):
        self._id = _id or ObjectId()
        self.course_name = course_name.strip()
        self.course_code = course_code.strip().upper()
        self.department = department.strip()
        self.faculty_id = str(faculty_id) if faculty_id else None
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()

    @property
    def id(self) -> str:
        return str(self._id)

    def display_name(self) -> str:
        """Formatted display name: Subject Name (Subject Code)."""
        return f"{self.course_name} ({self.course_code})"

    @property
    def assigned_faculty(self) -> Optional[Faculty]:
        """Resolves assigned Faculty model instance."""
        if not self.faculty_id:
            return None
        return Faculty.get_by_id(self.faculty_id)

    @property
    def feedbacks(self) -> FeedbackQueryProxy:
        """Returns query proxy for evaluations submitted for this course."""
        return FeedbackQueryProxy({
            "$or": [
                {"course_id": str(self._id)},
                {"course_id": self._id}
            ]
        })

    def average_rating(self) -> float:
        """Computes current average rating for this course."""
        feedbacks = self.feedbacks.all()
        if not feedbacks:
            return 0.0
        return round(sum(f.rating for f in feedbacks) / len(feedbacks), 2)

    def feedback_count(self) -> int:
        """Computes total number of evaluations received."""
        return self.feedbacks.count()

    def to_doc(self) -> Dict[str, Any]:
        """Serializes instance to MongoDB document dict."""
        return {
            "_id": self._id,
            "course_name": self.course_name,
            "course_code": self.course_code,
            "department": self.department,
            "faculty_id": self.faculty_id,
            "is_active": self.is_active,
            "created_at": self.created_at
        }

    @classmethod
    def from_doc(cls, doc: Optional[Dict[str, Any]]) -> Optional['Course']:
        """Builds Course instance from a MongoDB document."""
        if not doc:
            return None
        return cls(
            _id=doc.get('_id'),
            course_name=doc.get('course_name', ''),
            course_code=doc.get('course_code', ''),
            department=doc.get('department', ''),
            faculty_id=doc.get('faculty_id'),
            is_active=doc.get('is_active', True),
            created_at=doc.get('created_at', datetime.utcnow())
        )

    def save(self) -> 'Course':
        """Upserts the course document in MongoDB."""
        db = get_db()
        db.courses.replace_one(
            {"_id": self._id},
            self.to_doc(),
            upsert=True
        )
        return self

    @classmethod
    def get_by_id(cls, course_id: Any) -> Optional['Course']:
        """Finds course by ObjectId or string ID."""
        if not course_id:
            return None
        db = get_db()
        doc = db.courses.find_one(to_id_query(course_id))
        return cls.from_doc(doc)

    @classmethod
    def find_by_code(cls, course_code: str) -> Optional['Course']:
        """Finds course by unique course code."""
        if not course_code:
            return None
        db = get_db()
        doc = db.courses.find_one({"course_code": course_code.strip().upper()})
        return cls.from_doc(doc)

    @classmethod
    def all(
        cls,
        filter_dict: Optional[Dict[str, Any]] = None,
        sort_field: str = 'course_name',
        sort_dir: int = 1
    ) -> List['Course']:
        """Retrieves list of courses matching filter."""
        db = get_db()
        cursor = db.courses.find(filter_dict or {}).sort(sort_field, sort_dir)
        return [cls.from_doc(d) for d in cursor]

    @classmethod
    def count(cls, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Returns document count matching filter."""
        db = get_db()
        return db.courses.count_documents(filter_dict or {})

    def __repr__(self):
        return f'<Course {self.course_code}: {self.course_name}>'


class Feedback:
    """
    Feedback model capturing rating and qualitative review from a student
    for a faculty member teaching a specific course.
    """
    RATING_SCALE = {
        5: "Excellent",
        4: "Good",
        3: "Average",
        2: "Poor",
        1: "Terrible"
    }

    def __init__(
        self,
        student_id: Any,
        faculty_id: Any,
        course_id: Any,
        rating: int,
        comments: str = '',
        created_at: Optional[datetime] = None,
        _id: Optional[Any] = None
    ):
        self._id = _id or ObjectId()
        self.student_id = str(student_id)
        self.faculty_id = str(faculty_id)
        self.course_id = str(course_id)
        self.rating = int(rating)
        self.comments = comments or ''
        self.created_at = created_at or datetime.utcnow()

    @property
    def id(self) -> str:
        return str(self._id)

    @property
    def rating_label(self) -> str:
        """Returns the textual rating label corresponding to the 1-5 scale."""
        return self.RATING_SCALE.get(self.rating, "Average")

    @property
    def student(self) -> Optional[User]:
        """Resolves submitting Student User instance."""
        return User.get_by_id(self.student_id)

    @property
    def faculty(self) -> Optional[Faculty]:
        """Resolves evaluated Faculty instance."""
        return Faculty.get_by_id(self.faculty_id)

    @property
    def course(self) -> Optional[Course]:
        """Resolves evaluated Course instance."""
        return Course.get_by_id(self.course_id)

    def to_doc(self) -> Dict[str, Any]:
        """Serializes instance to MongoDB document dict."""
        return {
            "_id": self._id,
            "student_id": self.student_id,
            "faculty_id": self.faculty_id,
            "course_id": self.course_id,
            "rating": self.rating,
            "comments": self.comments,
            "created_at": self.created_at
        }

    @classmethod
    def from_doc(cls, doc: Optional[Dict[str, Any]]) -> Optional['Feedback']:
        """Builds Feedback instance from a MongoDB document."""
        if not doc:
            return None
        return cls(
            _id=doc.get('_id'),
            student_id=doc.get('student_id', ''),
            faculty_id=doc.get('faculty_id', ''),
            course_id=doc.get('course_id', ''),
            rating=doc.get('rating', 3),
            comments=doc.get('comments', ''),
            created_at=doc.get('created_at', datetime.utcnow())
        )

    def save(self) -> 'Feedback':
        """Upserts the feedback document in MongoDB."""
        db = get_db()
        db.feedbacks.replace_one(
            {"_id": self._id},
            self.to_doc(),
            upsert=True
        )
        return self

    @classmethod
    def get_by_id(cls, feedback_id: Any) -> Optional['Feedback']:
        """Finds feedback by ObjectId or string ID."""
        if not feedback_id:
            return None
        db = get_db()
        doc = db.feedbacks.find_one(to_id_query(feedback_id))
        return cls.from_doc(doc)

    @classmethod
    def find_one(cls, filter_dict: Dict[str, Any]) -> Optional['Feedback']:
        """Finds a single feedback document matching filter."""
        db = get_db()
        doc = db.feedbacks.find_one(filter_dict)
        return cls.from_doc(doc)

    @classmethod
    def find(
        cls,
        filter_dict: Optional[Dict[str, Any]] = None,
        sort: Optional[List[tuple]] = None,
        limit: Optional[int] = None,
        skip: int = 0
    ) -> List['Feedback']:
        """Finds feedbacks matching filter."""
        db = get_db()
        cursor = db.feedbacks.find(filter_dict or {})
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [cls.from_doc(d) for d in cursor]

    @classmethod
    def count(cls, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Returns document count matching filter."""
        db = get_db()
        return db.feedbacks.count_documents(filter_dict or {})

    @classmethod
    def paginate(
        cls,
        filter_dict: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 10,
        sort: Optional[List[tuple]] = None
    ) -> Pagination:
        """
        Retrieves paginated feedbacks with total count and helper methods.
        """
        query_filter = filter_dict or {}
        db = get_db()
        total = db.feedbacks.count_documents(query_filter)
        skip = (page - 1) * per_page
        items = cls.find(query_filter, sort=sort or [("created_at", -1)], limit=per_page, skip=skip)
        return Pagination(items=items, page=page, per_page=per_page, total=total)

    def __repr__(self):
        return f'<Feedback Student:{self.student_id} Course:{self.course_id} Faculty:{self.faculty_id} Rating:{self.rating} ({self.rating_label})>'
