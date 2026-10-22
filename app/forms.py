"""
WTForms definitions for Campus Voice.
Adapted for MongoDB with string ObjectIds and PyMongo validation queries.
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SubmitField,
    SelectField,
    TextAreaField,
    RadioField
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    ValidationError,
    Optional
)
from app.models import User, Faculty, Course

DEPARTMENT_CHOICES = [
    ('', '-- Select Academic Department --'),
    ('Computer Science & Engineering', 'Computer Science & Engineering'),
    ('Information Technology', 'Information Technology'),
    ('Electronics & Communication', 'Electronics & Communication'),
    ('Mechanical Engineering', 'Mechanical Engineering'),
    ('Electrical & Electronics', 'Electrical & Electronics'),
    ('Civil Engineering', 'Civil Engineering'),
    ('Business Administration', 'Business Administration'),
    ('Applied Sciences & Mathematics', 'Applied Sciences & Mathematics')
]


class LoginForm(FlaskForm):
    """User authentication form."""
    email = StringField('Email Address', validators=[
        DataRequired(message="Email is required."),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required.")
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class StudentRegistrationForm(FlaskForm):
    """Student account registration form."""
    name = StringField('Full Name', validators=[
        DataRequired(message="Full name is required."),
        Length(min=2, max=120, message="Name must be between 2 and 120 characters.")
    ])
    email = StringField('Institutional Email', validators=[
        DataRequired(message="Email is required."),
        Email(message="Please enter a valid institutional email address."),
        Length(max=120)
    ])
    student_id = StringField('Student Roll / ID', validators=[
        DataRequired(message="Student ID is required."),
        Length(min=3, max=50, message="Student ID must be between 3 and 50 characters.")
    ])
    department = SelectField('Department', choices=DEPARTMENT_CHOICES, validators=[
        DataRequired(message="Please select your department.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required."),
        Length(min=8, message="Password must be at least 8 characters long.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password."),
        EqualTo('password', message="Passwords do not match.")
    ])
    submit = SubmitField('Register as Student')

    def validate_email(self, field):
        normalized_email = field.data.strip().lower()
        if User.find_by_email(normalized_email):
            raise ValidationError("This email address is already registered. Please log in instead.")

    def validate_student_id(self, field):
        normalized_id = field.data.strip().upper()
        if User.find_by_student_id(normalized_id):
            raise ValidationError("This Student ID is already registered in the system.")


class FeedbackForm(FlaskForm):
    """Student feedback submission form."""
    course_id = SelectField('Course', coerce=str, validators=[
        DataRequired(message="Please select a course.")
    ])
    faculty_id = SelectField('Faculty Member', coerce=str, validators=[
        DataRequired(message="Please select a faculty member.")
    ])
    rating = RadioField(
        'Rating',
        choices=[
            ('5', '5 - Excellent'),
            ('4', '4 - Good'),
            ('3', '3 - Average'),
            ('2', '2 - Poor'),
            ('1', '1 - Terrible')
        ],
        validators=[DataRequired(message="Please choose a rating from 1 to 5.")]
    )
    comments = TextAreaField('Detailed Comments & Feedback (Optional)', validators=[
        Optional(),
        Length(max=1000, message="Comments must not exceed 1000 characters.")
    ])
    submit = SubmitField('Submit Feedback')


class FacultyForm(FlaskForm):
    """Form for administrators to create or edit faculty members."""
    faculty_name = StringField('Faculty Name', validators=[
        DataRequired(message="Faculty name is required."),
        Length(min=2, max=150)
    ])
    department = SelectField('Department', choices=DEPARTMENT_CHOICES, validators=[
        DataRequired(message="Please select a department.")
    ])
    email = StringField('Faculty Email (Optional)', validators=[
        Optional(),
        Email(message="Please enter a valid email address.")
    ])
    is_active = BooleanField('Active Status', default=True)
    submit = SubmitField('Save Faculty')

    def __init__(self, original_id=None, *args, **kwargs):
        super(FacultyForm, self).__init__(*args, **kwargs)
        self.original_id = str(original_id) if original_id else None

    def validate_email(self, field):
        if field.data and field.data.strip():
            normalized_email = field.data.strip().lower()
            existing = Faculty.find_by_email(normalized_email)
            if existing and (self.original_id is None or str(existing.id) != self.original_id):
                raise ValidationError("Another faculty member with this email already exists.")


class CourseForm(FlaskForm):
    """Form for administrators to create or edit courses."""
    course_name = StringField('Course Name', validators=[
        DataRequired(message="Course name is required."),
        Length(min=2, max=150)
    ])
    course_code = StringField('Course Code', validators=[
        DataRequired(message="Course code is required."),
        Length(min=2, max=50)
    ])
    department = SelectField('Department', choices=DEPARTMENT_CHOICES, validators=[
        DataRequired(message="Please select a department.")
    ])
    faculty_id = SelectField('Assigned Faculty Member', coerce=str, validators=[
        Optional()
    ])
    is_active = BooleanField('Active Status', default=True)
    submit = SubmitField('Save Course')

    def __init__(self, original_id=None, *args, **kwargs):
        super(CourseForm, self).__init__(*args, **kwargs)
        self.original_id = str(original_id) if original_id else None

    def validate_course_code(self, field):
        normalized_code = field.data.strip().upper()
        existing = Course.find_by_code(normalized_code)
        if existing and (self.original_id is None or str(existing.id) != self.original_id):
            raise ValidationError("A course with this code already exists.")
