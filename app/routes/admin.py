"""
Administrator portal routes for Campus Voice.
Handles Analytics Dashboard, Faculty CRUD, Course CRUD, Student Directory,
Searchable/Filterable Feedback Auditing, and CSV Export using MongoDB.
"""
import csv
import io
import re
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
    Response,
    abort
)
from app.db import get_db
from app.models import User, Course, Faculty, Feedback
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
    db = get_db()
    total_students = User.count({'role': 'student'})
    total_courses = Course.count({'is_active': True})
    total_faculty = Faculty.count({'is_active': True})
    total_feedback = Feedback.count()

    # Overall institution average rating via MongoDB aggregation
    avg_pipeline = [{"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}]
    try:
        avg_result = list(db.feedbacks.aggregate(avg_pipeline))
        overall_avg_rating = round(avg_result[0]["avg_rating"], 2) if avg_result and avg_result[0].get("avg_rating") is not None else 0.0
    except Exception:
        all_fb = Feedback.find()
        overall_avg_rating = round(sum(f.rating for f in all_fb) / len(all_fb), 2) if all_fb else 0.0

    # Rating distribution (1 to 5 stars)
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    try:
        dist_pipeline = [{"$group": {"_id": "$rating", "count": {"$sum": 1}}}]
        for doc in db.feedbacks.aggregate(dist_pipeline):
            r = doc.get("_id")
            if r in rating_counts:
                rating_counts[r] = doc.get("count", 0)
    except Exception:
        all_fb = Feedback.find()
        for fb in all_fb:
            if fb.rating in rating_counts:
                rating_counts[fb.rating] += 1

    # Faculty ratings breakdown (average rating & count)
    faculties = Faculty.all(sort_field='faculty_name')
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
    courses = Course.all(sort_field='course_code')
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
    recent_feedbacks = Feedback.find(sort=[('created_at', -1)], limit=8)

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
    db = get_db()
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    try:
        dist_pipeline = [{"$group": {"_id": "$rating", "count": {"$sum": 1}}}]
        for doc in db.feedbacks.aggregate(dist_pipeline):
            r = doc.get("_id")
            if r in rating_counts:
                rating_counts[r] = doc.get("count", 0)
    except Exception:
        for fb in Feedback.find():
            if fb.rating in rating_counts:
                rating_counts[fb.rating] += 1

    # Top faculty by feedback count and rating
    faculties = Faculty.all(sort_field='faculty_name')
    faculty_labels = []
    faculty_averages = []
    for f in faculties:
        feedbacks = f.feedbacks.all()
        if feedbacks:
            faculty_labels.append(f.faculty_name)
            faculty_averages.append(round(sum(fb.rating for fb in feedbacks) / len(feedbacks), 2))

    # Top courses by rating
    courses = Course.all(sort_field='course_code')
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
            faculty.save()
            flash(f"Faculty member '{faculty.faculty_name}' has been added successfully.", "success")
            return redirect(url_for('admin.faculty_list'))
        except Exception:
            flash("An error occurred while creating the faculty record.", "danger")

    faculties = Faculty.all(sort_field='faculty_name')
    return render_template('admin/faculty.html', faculties=faculties, form=form)


@admin_bp.route('/faculty/<string:id>/edit', methods=['GET', 'POST'])
@admin_required
def faculty_edit(id):
    """Edits an existing faculty member."""
    faculty = Faculty.get_by_id(id)
    if not faculty:
        abort(404)

    form = FacultyForm(original_id=faculty.id, obj=faculty)

    if form.validate_on_submit():
        email_val = form.email.data.strip().lower() if form.email.data and form.email.data.strip() else None
        faculty.faculty_name = form.faculty_name.data.strip()
        faculty.department = form.department.data
        faculty.email = email_val
        faculty.is_active = form.is_active.data

        try:
            faculty.save()
            flash(f"Faculty member '{faculty.faculty_name}' updated successfully.", "success")
            return redirect(url_for('admin.faculty_list'))
        except Exception:
            flash("Failed to update faculty member details.", "danger")

    return render_template('admin/faculty_edit.html', form=form, faculty=faculty)


@admin_bp.route('/faculty/<string:id>/toggle', methods=['POST'])
@admin_required
def faculty_toggle(id):
    """Toggles faculty active / inactive status."""
    faculty = Faculty.get_by_id(id)
    if not faculty:
        abort(404)

    faculty.is_active = not faculty.is_active
    faculty.save()
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
    faculties = Faculty.all({'is_active': True}, sort_field='faculty_name')
    form.faculty_id.choices = [('', '-- None / Unassigned --')] + [
        (f.id, f"{f.faculty_name} ({f.department})") for f in faculties
    ]

    if form.validate_on_submit():
        faculty_id_val = form.faculty_id.data if form.faculty_id.data and form.faculty_id.data.strip() else None
        course = Course(
            course_name=form.course_name.data.strip(),
            course_code=form.course_code.data.strip().upper(),
            department=form.department.data,
            faculty_id=faculty_id_val,
            is_active=form.is_active.data
        )
        try:
            course.save()
            flash(f"Course '{course.course_code}: {course.course_name}' created successfully.", "success")
            return redirect(url_for('admin.course_list'))
        except Exception:
            flash("An error occurred while adding the course.", "danger")

    courses = Course.all(sort_field='course_code')
    return render_template('admin/courses.html', courses=courses, form=form)


@admin_bp.route('/courses/<string:id>/edit', methods=['GET', 'POST'])
@admin_required
def course_edit(id):
    """Edits an existing course."""
    course = Course.get_by_id(id)
    if not course:
        abort(404)

    form = CourseForm(original_id=course.id, obj=course)
    faculties = Faculty.all({'is_active': True}, sort_field='faculty_name')
    form.faculty_id.choices = [('', '-- None / Unassigned --')] + [
        (f.id, f"{f.faculty_name} ({f.department})") for f in faculties
    ]

    if request.method == 'GET':
        form.faculty_id.data = course.faculty_id or ''

    if form.validate_on_submit():
        course.course_name = form.course_name.data.strip()
        course.course_code = form.course_code.data.strip().upper()
        course.department = form.department.data
        course.faculty_id = form.faculty_id.data if form.faculty_id.data and form.faculty_id.data.strip() else None
        course.is_active = form.is_active.data

        try:
            course.save()
            flash(f"Course '{course.course_code}' updated successfully.", "success")
            return redirect(url_for('admin.course_list'))
        except Exception:
            flash("Failed to update course details.", "danger")

    return render_template('admin/course_edit.html', form=form, course=course)


@admin_bp.route('/courses/<string:id>/toggle', methods=['POST'])
@admin_required
def course_toggle(id):
    """Toggles course active / inactive status."""
    course = Course.get_by_id(id)
    if not course:
        abort(404)

    course.is_active = not course.is_active
    course.save()
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
    students = User.all(filter_dict={'role': 'student'}, sort_field='created_at', sort_dir=-1)
    return render_template('admin/students.html', students=students)


# -------------------------------------------------------------
# FEEDBACK REVIEW & SEARCH/FILTER
# -------------------------------------------------------------
def get_filtered_feedback_query():
    """Constructs dynamic MongoDB query filter based on GET parameters."""
    query = {}

    course_id = request.args.get('course_id')
    faculty_id = request.args.get('faculty_id')
    rating = request.args.get('rating', type=int)
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    search = request.args.get('search', '').strip()

    if course_id and course_id.strip():
        # Match either string course_id or ObjectId representation
        course_obj = Course.get_by_id(course_id)
        if course_obj:
            query["course_id"] = {"$in": [str(course_id), course_obj._id]}
        else:
            query["course_id"] = str(course_id)

    if faculty_id and faculty_id.strip():
        faculty_obj = Faculty.get_by_id(faculty_id)
        if faculty_obj:
            query["faculty_id"] = {"$in": [str(faculty_id), faculty_obj._id]}
        else:
            query["faculty_id"] = str(faculty_id)

    if rating:
        query["rating"] = int(rating)

    created_at_filter = {}
    if date_from:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            created_at_filter["$gte"] = start_date
        except ValueError:
            pass

    if date_to:
        try:
            end_date = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            created_at_filter["$lte"] = end_date
        except ValueError:
            pass

    if created_at_filter:
        query["created_at"] = created_at_filter

    if search:
        # Cross-document keyword search across comments, students, courses, and faculties
        matching_user_ids = []
        for u in User.all({
            "$or": [
                {"name": {"$regex": re.escape(search), "$options": "i"}},
                {"student_id": {"$regex": re.escape(search), "$options": "i"}}
            ]
        }):
            matching_user_ids.extend([str(u.id), u._id])

        matching_course_ids = []
        for c in Course.all({
            "$or": [
                {"course_name": {"$regex": re.escape(search), "$options": "i"}},
                {"course_code": {"$regex": re.escape(search), "$options": "i"}}
            ]
        }):
            matching_course_ids.extend([str(c.id), c._id])

        matching_faculty_ids = []
        for f in Faculty.all({
            "faculty_name": {"$regex": re.escape(search), "$options": "i"}
        }):
            matching_faculty_ids.extend([str(f.id), f._id])

        search_or = [
            {"comments": {"$regex": re.escape(search), "$options": "i"}}
        ]
        if matching_user_ids:
            search_or.append({"student_id": {"$in": matching_user_ids}})
        if matching_course_ids:
            search_or.append({"course_id": {"$in": matching_course_ids}})
        if matching_faculty_ids:
            search_or.append({"faculty_id": {"$in": matching_faculty_ids}})

        query["$or"] = search_or

    return query


@admin_bp.route('/feedback')
@admin_required
def feedback_list():
    """
    Searchable, filterable, and paginated table of all submitted student feedback.
    Supports filtering by course, faculty, rating, date range, and keyword search.
    """
    courses = Course.all(sort_field='course_name')
    faculties = Faculty.all(sort_field='faculty_name')

    filter_dict = get_filtered_feedback_query()

    # Pre-calculate summary stats across all matching records
    all_filtered = Feedback.find(filter_dict)
    total_count = len(all_filtered)
    filtered_avg = round(sum(f.rating for f in all_filtered) / total_count, 2) if total_count > 0 else 0.0

    # Pagination handling
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in (10, 25, 50, 100):
        per_page = 10

    pagination = Feedback.paginate(
        filter_dict=filter_dict,
        page=page,
        per_page=per_page,
        sort=[('created_at', -1)]
    )
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
    filter_dict = get_filtered_feedback_query()
    feedbacks = Feedback.find(filter_dict, sort=[('created_at', -1)])

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
        student = fb.student
        course = fb.course
        faculty = fb.faculty

        writer.writerow([
            fb.id,
            fb.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            student.name if student else 'Unknown',
            student.student_id if student else 'N/A',
            student.department if student else 'N/A',
            course.course_code if course else 'N/A',
            course.course_name if course else 'N/A',
            faculty.faculty_name if faculty else 'N/A',
            faculty.department if faculty else 'N/A',
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
