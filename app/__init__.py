from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from app.config import Config
from app.models import db, User

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    """
    Application Factory creating configured Flask instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Please sign in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
            if user is None:
                app.logger.warning(f"[SESSION] User loader: User ID {user_id} not found in current database instance.")
            return user
        except Exception as e:
            app.logger.error(f"[SESSION ERROR] User loader failed for ID {user_id}: {e}")
            return None

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    # Root route
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.is_admin():
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('student.dashboard'))
        return redirect(url_for('auth.login'))

    # Health Check Endpoint
    @app.route('/health')
    @app.route('/healthz')
    def health_check():
        db_status = "connected"
        status_code = 200
        try:
            db.session.execute(text("SELECT 1"))
        except Exception as e:
            db_status = f"error: {str(e)}"
            status_code = 503

        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        db_scheme = db_uri.split('://')[0] if '://' in db_uri else 'unknown'

        return {
            'status': 'healthy' if status_code == 200 else 'unhealthy',
            'service': 'Campus Voice',
            'database': db_status,
            'database_scheme': db_scheme
        }, status_code

    # Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f"500 Internal Server Error: {error}", exc_info=True)
        return render_template('errors/500.html'), 500

    # Custom Jinja Template Filters
    @app.template_filter('star_display')
    def star_display(rating):
        """Generates visual star icons for ratings."""
        try:
            val = round(float(rating))
            full = '★' * val
            empty = '☆' * (5 - val)
            return full + empty
        except (ValueError, TypeError):
            return '☆☆☆☆☆'

    # Auto-create tables if missing (ensures serverless / new environments don't crash with 500)
    with app.app_context():
        try:
            db.create_all()
            from app.models import Course
            if Course.query.count() == 0:
                from seed_data import seed_database
                seed_database(app)
        except Exception as exc:
            app.logger.warning(f"Database schema auto-check: {exc}")

    return app
