from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user


def admin_required(f):
    """
    Decorator to restrict route access exclusively to users with 'admin' role.
    Unauthenticated users are directed to login with the next parameter preserved.
    Non-admin authenticated users receive a 403 Forbidden response.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please sign in to access the administrator portal.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """
    Decorator to restrict route access exclusively to users with 'student' role.
    Unauthenticated users are directed to login.
    If an administrator visits student pages, they are redirected to the admin dashboard.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please sign in to access the student portal.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_student():
            flash("Administrators have dedicated analytics dashboards.", "info")
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
