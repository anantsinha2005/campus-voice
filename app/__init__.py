"""
Application Factory for Campus Voice - Student Feedback & Academic Quality System.
Uses PyMongo with MongoDB Atlas and Flask-Login.
"""
from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from app.config import Config
from app.models import User
from app.db import get_db, init_indexes, ping_db

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    """
    Application Factory creating configured Flask instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    csrf.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Please sign in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = User.get_by_id(user_id)
            if user is None:
                app.logger.warning(f"[SESSION] User loader: User ID {user_id} not found in MongoDB.")
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
        is_healthy = ping_db()
        status_code = 200 if is_healthy else 503
        return {
            'status': 'healthy' if is_healthy else 'unhealthy',
            'service': 'Campus Voice',
            'database': 'connected' if is_healthy else 'disconnected',
            'database_engine': 'MongoDB Atlas'
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

    # Safe index initialization (ensures unique constraints exist in MongoDB)
    with app.app_context():
        try:
            init_indexes(get_db())
        except Exception as exc:
            app.logger.warning(f"MongoDB index auto-initialization: {exc}")

    return app
