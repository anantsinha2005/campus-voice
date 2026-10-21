import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import re
import requests
from bs4 import BeautifulSoup
from app import create_app
from app.config import Config
from app.models import db, User, Course, Faculty, Feedback

BASE_URL = "http://127.0.0.1:5000"


def extract_csrf(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    if csrf_input and csrf_input.get('value'):
        return csrf_input['value']
    # Regex fallback
    match = re.search(r'name=["\']csrf_token["\'].*?value=["\']([^"\']+)["\']', html_text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r'value=["\']([^"\']+)["\'].*?name=["\']csrf_token["\']', html_text, re.DOTALL)
    if match:
        return match.group(1)
    raise ValueError("Could not find csrf_token in HTML")


def run_live_verification():
    print("=" * 70)
    print("STARTING LIVE HTTP END-TO-END VERIFICATION")
    print("=" * 70)

    session = requests.Session()

    # 1. Check Server Liveness
    res = session.get(f"{BASE_URL}/login")
    assert res.status_code == 200, f"Server /login returned {res.status_code}"
    print("[PASS] 1. Live server reachable at http://127.0.0.1:5000/login")

    # 2. Student Login
    csrf_login = extract_csrf(res.text)
    login_res = session.post(f"{BASE_URL}/login", data={
        'csrf_token': csrf_login,
        'email': 'rahul.s@student.university.edu',
        'password': 'Student123!'
    }, allow_redirects=True)
    assert login_res.status_code == 200, "Student login failed"
    assert "Rahul Sharma" in login_res.text, "Student name not found in dashboard"
    print("[PASS] 2. Student logged in successfully (Rahul Sharma)")

    # 3. Student Submit Feedback
    form_res = session.get(f"{BASE_URL}/student/submit-feedback")
    assert form_res.status_code == 200, "Failed to load submit feedback page"
    csrf_fb = extract_csrf(form_res.text)

    # Ensure clean state for the test combo before submitting
    app = create_app(Config)
    with app.app_context():
        course = Course.query.filter_by(course_code="BCO017A").first()
        faculty = Faculty.query.filter_by(faculty_name="Gajanand Sharma").first()
        c_id = course.id
        f_id = faculty.id
        student = User.query.filter_by(email='rahul.s@student.university.edu').first()
        Feedback.query.filter_by(student_id=student.id, course_id=c_id, faculty_id=f_id).delete()
        db.session.commit()

    unique_comment = "End-to-End Live HTTP Verification: Outstanding course pacing and exceptional teaching in BCO017A."
    submit_res = session.post(f"{BASE_URL}/student/submit-feedback", data={
        'csrf_token': csrf_fb,
        'course_id': c_id,
        'faculty_id': f_id,
        'rating': '5',
        'comments': unique_comment
    }, allow_redirects=True)
    assert submit_res.status_code == 200, "Submit feedback request failed"
    assert "successfully submitted" in submit_res.text, "Success message missing after submission"
    print("[PASS] 3. Feedback successfully submitted by student")

    # 4. Confirm Record in SQLite Database
    app = create_app(Config)
    with app.app_context():
        student = User.query.filter_by(email='rahul.s@student.university.edu').first()
        fb_record = Feedback.query.filter_by(
            student_id=student.id,
            course_id=c_id,
            faculty_id=f_id
        ).first()
        assert fb_record is not None, "Record not found in database!"
        assert fb_record.rating == 5, f"Rating mismatch: {fb_record.rating}"
        assert fb_record.comments == unique_comment, "Comments mismatch in database!"
        fb_id = fb_record.id
    print(f"[PASS] 4. Record permanently verified in instance/feedback.db (Feedback ID: #{fb_id})")

    # 5. Verify Student CANNOT Access Admin Feedback Page Directly
    admin_access_res = session.get(f"{BASE_URL}/admin/feedback")
    assert admin_access_res.status_code == 403, f"Expected 403 Forbidden, got {admin_access_res.status_code}"
    assert "403" in admin_access_res.text or "Access Prohibited" in admin_access_res.text
    print("[PASS] 5. Student access to /admin/feedback blocked with 403 Forbidden")

    # 6. Admin Login
    admin_session = requests.Session()
    admin_login_page = admin_session.get(f"{BASE_URL}/login")
    admin_csrf = extract_csrf(admin_login_page.text)
    admin_post = admin_session.post(f"{BASE_URL}/login", data={
        'csrf_token': admin_csrf,
        'email': 'admin@university.edu',
        'password': 'AdminSecure2026!'
    }, allow_redirects=True)
    assert admin_post.status_code == 200, "Admin login failed"
    assert "Administrator Control Center" in admin_post.text, "Admin dashboard not displayed"
    print("[PASS] 6. Administrator logged in successfully")

    # 7. Verify Record in Administrator Feedback Review Page
    admin_fb_page = admin_session.get(f"{BASE_URL}/admin/feedback")
    assert admin_fb_page.status_code == 200, "Failed to load /admin/feedback"
    assert f"#{fb_id}" in admin_fb_page.text, f"Feedback ID #{fb_id} not found in admin table"
    assert "Rahul Sharma" in admin_fb_page.text, "Student name not found in admin table"
    assert "BCO017A" in admin_fb_page.text, "Course code BCO017A not found in admin table"
    assert "Gajanand Sharma" in admin_fb_page.text, "Faculty Gajanand Sharma not found in admin table"
    assert unique_comment in admin_fb_page.text, "Comment text not found in admin table"
    print(f"[PASS] 7. Feedback #{fb_id} visible in central Administrator Feedback Review dashboard")

    # 8. Verify Search and CSV Export with Filter
    csv_res = admin_session.get(f"{BASE_URL}/admin/feedback/export-csv?search=End-to-End+Live+HTTP+Verification")
    assert csv_res.status_code == 200, "CSV export failed"
    assert csv_res.headers.get('Content-Type') == 'text/csv; charset=utf-8' or 'text/csv' in csv_res.headers.get('Content-Type', '')
    assert f"#{fb_id}" in csv_res.text or str(fb_id) in csv_res.text
    assert "Rahul Sharma" in csv_res.text
    assert "Gajanand Sharma" in csv_res.text
    assert "Password" not in csv_res.text and "pbkdf2" not in csv_res.text
    print("[PASS] 8. CSV export successfully generated with filtered feedback record")

    print("=" * 70)
    print("ALL LIVE HTTP CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == '__main__':
    run_live_verification()
