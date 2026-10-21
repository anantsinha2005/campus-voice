from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from app.models import db, Course, Faculty, Feedback
from app.forms import FeedbackForm
from app.decorators import student_required

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/dashboard')
@student_required
def dashboard():
    """
    Student dashboard displaying academic summary, available courses,
    and a list of the student's recent submissions.
    """
    # Active courses and faculties
    courses = Course.query.filter_by(is_active=True).order_by(Course.course_name).all()
    faculties = Faculty.query.filter_by(is_active=True).order_by(Faculty.faculty_name).all()

    # The student's own feedback submissions
    student_feedbacks = Feedback.query.filter_by(
        student_id=current_user.id
    ).order_by(Feedback.created_at.desc()).all()

    # Create a set of (course_id, faculty_id) pairs already submitted by this student
    submitted_pairs = {(f.course_id, f.faculty_id) for f in student_feedbacks}

    return render_template(
        'student/dashboard.html',
        student=current_user,
        courses=courses,
        faculties=faculties,
        feedbacks=student_feedbacks[:5],  # Recent 5
        total_submitted=len(student_feedbacks),
        submitted_pairs=submitted_pairs
    )


@student_bp.route('/submit-feedback', methods=['GET', 'POST'])
@student_required
def submit_feedback():
    """
    Handles submitting feedback for a course and faculty member.
    Enforces server-side validation and duplicate prevention.
    """
    courses = Course.query.filter_by(is_active=True).order_by(Course.course_name).all()
    faculties = Faculty.query.filter_by(is_active=True).order_by(Faculty.faculty_name).all()

    if not courses or not faculties:
        flash("No active courses or faculty members are currently available for feedback.", "warning")
        return redirect(url_for('student.dashboard'))

    form = FeedbackForm()
    # Populate dropdown choices using exact format: Subject Name (Subject Code)
    form.course_id.choices = [(c.id, f"{c.course_name} ({c.course_code})") for c in courses]
    form.faculty_id.choices = [(f.id, f.faculty_name) for f in faculties]

    # Map each course to its assigned faculty member
    course_faculty_map = {c.id: c.faculty_id for c in courses if c.faculty_id}

    # Pre-select course or faculty if provided via query parameter
    if request.method == 'GET':
        prefill_course = request.args.get('course_id', type=int)
        prefill_faculty = request.args.get('faculty_id', type=int)
        if prefill_course and any(c.id == prefill_course for c in courses):
            form.course_id.data = prefill_course
            course_obj = next((c for c in courses if c.id == prefill_course), None)
            if course_obj and course_obj.faculty_id:
                form.faculty_id.data = course_obj.faculty_id
            elif prefill_faculty and any(f.id == prefill_faculty for f in faculties):
                form.faculty_id.data = prefill_faculty
        elif prefill_faculty and any(f.id == prefill_faculty for f in faculties):
            form.faculty_id.data = prefill_faculty

    if form.validate_on_submit():
        course_id = form.course_id.data
        faculty_id = form.faculty_id.data
        rating = int(form.rating.data)
        comments = form.comments.data.strip() if form.comments.data else ""

        # Check course and faculty existence and active status
        course = db.session.get(Course, course_id)
        faculty = db.session.get(Faculty, faculty_id)
        if not course or not course.is_active or not faculty or not faculty.is_active:
            flash("Selected course or faculty member is inactive or invalid.", "danger")
            return render_template('student/submit_feedback.html', form=form, courses=courses, faculties=faculties, course_faculty_map=course_faculty_map)

        # Validate that the selected faculty is associated with the selected subject
        if course.faculty_id and faculty_id != course.faculty_id:
            assigned = db.session.get(Faculty, course.faculty_id)
            assigned_name = assigned.faculty_name if assigned else "the designated instructor"
            flash(f"Invalid assignment: '{course.course_name} ({course.course_code})' is assigned to {assigned_name}. Please choose the assigned instructor.", "danger")
            return render_template('student/submit_feedback.html', form=form, courses=courses, faculties=faculties, course_faculty_map=course_faculty_map)

        # Check for duplicate feedback by this student
        existing_feedback = Feedback.query.filter_by(
            student_id=current_user.id,
            course_id=course_id,
            faculty_id=faculty_id
        ).first()

        if existing_feedback:
            flash(f"You have already submitted feedback for {course.course_name} ({course.course_code}) taught by {faculty.faculty_name}. Duplicate submissions are prohibited.", "warning")
            return redirect(url_for('student.feedback_history'))

        feedback = Feedback(
            student_id=current_user.id,
            course_id=course_id,
            faculty_id=faculty_id,
            rating=rating,
            comments=comments
        )

        try:
            db.session.add(feedback)
            db.session.commit()
            flash("Your feedback has been successfully submitted! Thank you for your contribution to academic quality in Campus Voice.", "success")
            return redirect(url_for('student.feedback_history'))
        except IntegrityError:
            db.session.rollback()
            flash("A duplicate submission error occurred. You have already reviewed this faculty member for this course.", "warning")
            return redirect(url_for('student.feedback_history'))
        except Exception:
            db.session.rollback()
            flash("An unexpected error occurred while saving your feedback. Please try again.", "danger")

    return render_template(
        'student/submit_feedback.html',
        form=form,
        courses=courses,
        faculties=faculties,
        course_faculty_map=course_faculty_map
    )


@student_bp.route('/my-feedback')
@student_required
def feedback_history():
    """
    Displays the authenticated student's previous submissions.
    Ensures students only see their own feedback and cannot access others.
    """
    student_feedbacks = Feedback.query.filter_by(
        student_id=current_user.id
    ).order_by(Feedback.created_at.desc()).all()

    return render_template(
        'student/feedback_history.html',
        feedbacks=student_feedbacks
    )
