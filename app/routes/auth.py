from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
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
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        db_scheme = db_uri.split('://')[0] if '://' in db_uri else 'unknown'
        current_app.logger.info(f"[AUTH] Login attempt for email: {normalized_email} (DB scheme: {db_scheme})")

        try:
            user = User.query.filter_by(email=normalized_email).first()
        except Exception as exc:
            current_app.logger.error(f"[AUTH ERROR] Database exception during lookup for email '{normalized_email}': {exc}")
            flash("A database connection error occurred. Please try again.", "danger")
            return render_template('auth/login.html', form=form)

        if not user:
            current_app.logger.warning(f"[AUTH] Login rejected: No user record found in current database for email: {normalized_email}")
            flash("Invalid email address or password. Please check your credentials.", "danger")
            return render_template('auth/login.html', form=form)

        if not user.check_password(form.password.data):
            current_app.logger.warning(f"[AUTH] Login rejected: Password verification failed for user ID {user.id} ({user.role})")
            flash("Invalid email address or password. Please check your credentials.", "danger")
            return render_template('auth/login.html', form=form)

        if not user.is_active:
            current_app.logger.warning(f"[AUTH] Login rejected: User ID {user.id} ({user.role}) is deactivated")
            flash("Your account has been deactivated. Please contact the administrator.", "danger")
            return render_template('auth/login.html', form=form)

        login_user(user, remember=form.remember_me.data)
        current_app.logger.info(f"[AUTH] Login successful: User ID {user.id} ({user.role}, Name: {user.name})")
        flash(f"Welcome back, {user.name}!", "success")

        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            return redirect(next_page)

        if user.is_admin():
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

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
        normalized_email = form.email.data.strip().lower()
        normalized_student_id = form.student_id.data.strip().upper()
        
        current_app.logger.info(f"[AUTH] Student registration attempt: {normalized_email} ({normalized_student_id})")

        user = User(
            name=form.name.data.strip(),
            email=normalized_email,
            student_id=normalized_student_id,
            department=form.department.data,
            role='student',  # Hardcoded role constraint
            is_active=True
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            current_app.logger.info(f"[AUTH] Student registered successfully: ID {user.id} ({normalized_email})")
            flash("Your student account has been created successfully! You can now log in.", "success")
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[AUTH ERROR] Registration failed for {normalized_email}: {e}")
            flash("An error occurred during registration. Please try again.", "danger")

    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Logs out the active user and terminates the session."""
    user_id = current_user.id if current_user.is_authenticated else 'unknown'
    current_app.logger.info(f"[AUTH] Logout initiated for user ID: {user_id}")
    logout_user()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('auth.login'))
