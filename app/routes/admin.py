import csv
import io
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
    Response
)
from sqlalchemy import func
from app.models import db, User, Course, Faculty, Feedback
from app.forms import FacultyForm, CourseForm
from app.decorators import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """
    Administrator dashboard with key metrics, ratings distribution,
    faculty/course performance benchmarks, and recent feedback.
    """
    total_students = User.query.filter_by(role='student').count()
    total_courses = Course.query.filter_by(is_active=True).count()
    total_faculty = Faculty.query.filter_by(is_active=True).count()
    total_feedback = Feedback.query.count()

    # Overall institution average rating
    avg_rating_query = db.session.query(func.avg(Feedback.rating)).scalar()
    overall_avg_rating = round(avg_rating_query, 2) if avg_rating_query else 0.0

    # Rating distribution (1 to 5 stars)
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    dist_query = db.session.query(
        Feedback.rating, func.count(Feedback.id)
    ).group_by(Feedback.rating).all()
    for r, count in dist_query:
        if r in rating_counts:
            rating_counts[r] = count

    # Faculty ratings breakdown (average rating & count)
    faculties = Faculty.query.all()
    faculty_stats = []
    for f in faculties:
        feedbacks = f.feedbacks.all()
        avg = round(sum(fb.rating for fb in feedbacks) / len(feedbacks), 2) if feedbacks else 0.0
        faculty_stats.append({
            'id': f.id,
            'name': f.faculty_name,
            'department': f.department,
            'avg_rating': avg,
            'count': len(feedbacks),
            'is_active': f.is_active
        })

    # Course ratings breakdown (average rating & count)
    courses = Course.query.all()
    course_stats = []
    for c in courses:
        feedbacks = c.feedbacks.all()
        avg = round(sum(fb.rating for fb in feedbacks) / len(feedbacks), 2) if feedbacks else 0.0
        course_stats.append({
            'id': c.id,
            'code': c.course_code,
            'name': c.course_name,
            'department': c.department,
            'avg_rating': avg,
            'count': len(feedbacks),
            'is_active': c.is_active
        })

    # Recent feedback submissions
    recent_feedbacks = Feedback.query.order_by(
        Feedback.created_at.desc()
    ).limit(8).all()

    return render_template(
        'admin/dashboard.html',
        total_students=total_students,
        total_courses=total_courses,
        total_faculty=total_faculty,
        total_feedback=total_feedback,
        overall_avg_rating=overall_avg_rating,
        rating_counts=rating_counts,
        faculty_stats=faculty_stats,
        course_stats=course_stats,
        recent_feedbacks=recent_feedbacks
    )


@admin_bp.route('/analytics/data')
@admin_required
def analytics_data():
    """
    API endpoint returning structured analytics data for Chart.js.
    """
    # Distribution of ratings
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    dist_query = db.session.query(
        Feedback.rating, func.count(Feedback.id)
    ).group_by(Feedback.rating).all()
    for r, count in dist_query:
        if r in rating_counts:
            rating_counts[r] = count

    # Top faculty by feedback count and rating
    faculties = Faculty.query.all()
    faculty_labels = []
    faculty_averages = []
    for f in faculties:
        feedbacks = f.feedbacks.all()
        if feedbacks:
            faculty_labels.append(f.faculty_name)
            faculty_averages.append(round(sum(fb.rating for fb in feedbacks) / len(feedbacks), 2))

    # Top courses by rating
    courses = Course.query.all()
    course_labels = []
    course_averages = []
    for c in courses:
        feedbacks = c.feedbacks.all()
        if feedbacks:
            course_labels.append(c.course_code)
            course_averages.append(round(sum(fb.rating for fb in feedbacks) / len(feedbacks), 2))

    return jsonify({
        'rating_distribution': rating_counts,
        'faculty_ratings': {
            'labels': faculty_labels,
            'averages': faculty_averages
        },
        'course_ratings': {
            'labels': course_labels,
            'averages': course_averages
        }
    })


# -------------------------------------------------------------
# FACULTY MANAGEMENT
# -------------------------------------------------------------
@admin_bp.route('/faculty', methods=['GET', 'POST'])
@admin_required
def faculty_list():
    """Lists all faculty members and processes addition of new faculty."""
    form = FacultyForm()
    if form.validate_on_submit():
        email_val = form.email.data.strip().lower() if form.email.data and form.email.data.strip() else None
        faculty = Faculty(
            faculty_name=form.faculty_name.data.strip(),
            department=form.department.data,
            email=email_val,
            is_active=form.is_active.data
        )
        try:
            db.session.add(faculty)
            db.session.commit()
            flash(f"Faculty member '{faculty.faculty_name}' has been added successfully.", "success")
            return redirect(url_for('admin.faculty_list'))
        except Exception:
            db.session.rollback()
            flash("An error occurred while creating the faculty record.", "danger")

    faculties = Faculty.query.order_by(Faculty.faculty_name).all()
    return render_template('admin/faculty.html', faculties=faculties, form=form)


@admin_bp.route('/faculty/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def faculty_edit(id):
    """Edits an existing faculty member."""
    faculty = db.get_or_404(Faculty, id)
    form = FacultyForm(original_id=faculty.id, obj=faculty)

    if form.validate_on_submit():
        email_val = form.email.data.strip().lower() if form.email.data and form.email.data.strip() else None
        faculty.faculty_name = form.faculty_name.data.strip()
        faculty.department = form.department.data
        faculty.email = email_val
        faculty.is_active = form.is_active.data

        try:
            db.session.commit()
            flash(f"Faculty member '{faculty.faculty_name}' updated successfully.", "success")
            return redirect(url_for('admin.faculty_list'))
        except Exception:
            db.session.rollback()
            flash("Failed to update faculty member details.", "danger")

    return render_template('admin/faculty_edit.html', form=form, faculty=faculty)


@admin_bp.route('/faculty/<int:id>/toggle', methods=['POST'])
@admin_required
def faculty_toggle(id):
    """Toggles faculty active / inactive status."""
    faculty = db.get_or_404(Faculty, id)
    faculty.is_active = not faculty.is_active
    db.session.commit()
    status = "activated" if faculty.is_active else "deactivated"
    flash(f"Faculty member '{faculty.faculty_name}' has been {status}.", "info")
    return redirect(url_for('admin.faculty_list'))


# -------------------------------------------------------------
# COURSE MANAGEMENT
# -------------------------------------------------------------
@admin_bp.route('/courses', methods=['GET', 'POST'])
@admin_required
def course_list():
    """Lists all courses and processes addition of new courses."""
    form = CourseForm()
    faculties = Faculty.query.filter_by(is_active=True).order_by(Faculty.faculty_name).all()
    form.faculty_id.choices = [(0, '-- None / Unassigned --')] + [
        (f.id, f"{f.faculty_name} ({f.department})") for f in faculties
    ]

    if form.validate_on_submit():
        faculty_id_val = form.faculty_id.data if form.faculty_id.data and form.faculty_id.data > 0 else None
        course = Course(
            course_name=form.course_name.data.strip(),
            course_code=form.course_code.data.strip().upper(),
            department=form.department.data,
            faculty_id=faculty_id_val,
            is_active=form.is_active.data
        )
        try:
            db.session.add(course)
            db.session.commit()
            flash(f"Course '{course.course_code}: {course.course_name}' created successfully.", "success")
            return redirect(url_for('admin.course_list'))
        except Exception:
            db.session.rollback()
            flash("An error occurred while adding the course.", "danger")

    courses = Course.query.order_by(Course.course_code).all()
    return render_template('admin/courses.html', courses=courses, form=form)


@admin_bp.route('/courses/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def course_edit(id):
    """Edits an existing course."""
    course = db.get_or_404(Course, id)
    form = CourseForm(original_id=course.id, obj=course)
    faculties = Faculty.query.filter_by(is_active=True).order_by(Faculty.faculty_name).all()
    form.faculty_id.choices = [(0, '-- None / Unassigned --')] + [
        (f.id, f"{f.faculty_name} ({f.department})") for f in faculties
    ]

    if request.method == 'GET':
        form.faculty_id.data = course.faculty_id if course.faculty_id else 0

    if form.validate_on_submit():
        course.course_name = form.course_name.data.strip()
        course.course_code = form.course_code.data.strip().upper()
        course.department = form.department.data
        course.faculty_id = form.faculty_id.data if form.faculty_id.data and form.faculty_id.data > 0 else None
        course.is_active = form.is_active.data

        try:
            db.session.commit()
            flash(f"Course '{course.course_code}' updated successfully.", "success")
            return redirect(url_for('admin.course_list'))
        except Exception:
            db.session.rollback()
            flash("Failed to update course details.", "danger")

    return render_template('admin/course_edit.html', form=form, course=course)


@admin_bp.route('/courses/<int:id>/toggle', methods=['POST'])
@admin_required
def course_toggle(id):
    """Toggles course active / inactive status."""
    course = db.get_or_404(Course, id)
    course.is_active = not course.is_active
    db.session.commit()
    status = "activated" if course.is_active else "deactivated"
    flash(f"Course '{course.course_code}' has been {status}.", "info")
    return redirect(url_for('admin.course_list'))


# -------------------------------------------------------------
# STUDENTS OVERVIEW
# -------------------------------------------------------------
@admin_bp.route('/students')
@admin_required
def student_list():
    """Lists registered students with feedback statistics."""
    students = User.query.filter_by(role='student').order_by(User.created_at.desc()).all()
    return render_template('admin/students.html', students=students)


# -------------------------------------------------------------
# FEEDBACK REVIEW & SEARCH/FILTER
# -------------------------------------------------------------
def get_filtered_feedback_query():
    """Constructs dynamic SQLAlchemy query based on GET parameters."""
    query = Feedback.query.join(Feedback.student).join(Feedback.course).join(Feedback.faculty)

    course_id = request.args.get('course_id', type=int)
    faculty_id = request.args.get('faculty_id', type=int)
    rating = request.args.get('rating', type=int)
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    search = request.args.get('search', '').strip()

    if course_id:
        query = query.filter(Feedback.course_id == course_id)
    if faculty_id:
        query = query.filter(Feedback.faculty_id == faculty_id)
    if rating:
        query = query.filter(Feedback.rating == rating)

    if date_from:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Feedback.created_at >= start_date)
        except ValueError:
            pass

    if date_to:
        try:
            # End of day
            end_date = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Feedback.created_at <= end_date)
        except ValueError:
            pass

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Feedback.comments.ilike(search_pattern)) |
            (User.name.ilike(search_pattern)) |
            (User.student_id.ilike(search_pattern)) |
            (Course.course_name.ilike(search_pattern)) |
            (Course.course_code.ilike(search_pattern)) |
            (Faculty.faculty_name.ilike(search_pattern))
        )

    return query.order_by(Feedback.created_at.desc())


@admin_bp.route('/feedback')
@admin_required
def feedback_list():
    """
    Searchable, filterable, and paginated table of all submitted student feedback.
    Supports filtering by course, faculty, rating, date range, and keyword search.
    """
    courses = Course.query.order_by(Course.course_name).all()
    faculties = Faculty.query.order_by(Faculty.faculty_name).all()

    query = get_filtered_feedback_query()
    
    # Pre-calculate summary stats across all matching records (before pagination)
    all_filtered = query.all()
    total_count = len(all_filtered)
    filtered_avg = round(sum(f.rating for f in all_filtered) / total_count, 2) if total_count > 0 else 0.0

    # Pagination handling
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in (10, 25, 50, 100):
        per_page = 10

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    feedbacks = pagination.items

    return render_template(
        'admin/feedback_list.html',
        feedbacks=feedbacks,
        pagination=pagination,
        courses=courses,
        faculties=faculties,
        filtered_count=total_count,
        filtered_avg=filtered_avg,
        filters=request.args
    )


@admin_bp.route('/feedback/export-csv')
@admin_required
def export_csv():
    """
    Exports filtered or complete feedback records to CSV.
    """
    feedbacks = get_filtered_feedback_query().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV Header
    writer.writerow([
        'Feedback ID',
        'Submission Date',
        'Student Name',
        'Student Roll ID',
        'Student Department',
        'Course Code',
        'Course Name',
        'Faculty Name',
        'Faculty Department',
        'Rating (1-5)',
        'Comments',
        'Rating Label'
    ])

    for fb in feedbacks:
        writer.writerow([
            fb.id,
            fb.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            fb.student.name if fb.student else 'Unknown',
            fb.student.student_id if fb.student else 'N/A',
            fb.student.department if fb.student else 'N/A',
            fb.course.course_code if fb.course else 'N/A',
            fb.course.course_name if fb.course else 'N/A',
            fb.faculty.faculty_name if fb.faculty else 'N/A',
            fb.faculty.department if fb.faculty else 'N/A',
            fb.rating,
            fb.comments if fb.comments else '',
            fb.rating_label
        ])

    csv_data = output.getvalue()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"campus_voice_feedback_report_{timestamp}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
