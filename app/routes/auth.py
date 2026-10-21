from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app.models import db, User
from app.forms import LoginForm, StudentRegistrationForm

auth_bp = Blueprint('auth', __name__)


def is_safe_url(target):
    """Ensures target URL is local and safe for redirection."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ('', 'http', 'https') and ref_url.netloc == test_url.netloc or not test_url.netloc


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticates both Student and Administrator accounts."""
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        user = User.query.filter_by(email=normalized_email).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash("Your account has been deactivated. Please contact the administrator.", "danger")
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            flash(f"Welcome back, {user.name}!", "success")

            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)

            if user.is_admin():
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('student.dashboard'))
        else:
            flash("Invalid email address or password. Please check your credentials.", "danger")

    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Registers a new student. 
    Role is strictly hardcoded to 'student' to prevent privilege escalation.
    """
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    form = StudentRegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            student_id=form.student_id.data.strip().upper(),
            department=form.department.data,
            role='student',  # Hardcoded role constraint
            is_active=True
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash("Your student account has been created successfully! You can now log in.", "success")
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.", "danger")

    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Logs out the active user and terminates the session."""
    logout_user()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('auth.login'))
