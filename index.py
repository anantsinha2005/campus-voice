"""
Campus Voice - Flask WSGI Entry Point.
Compatible with Vercel Serverless Functions and local execution.
"""
from app import create_app
from app.models import db

app = create_app()

# Auto-initialize database tables and real catalog if deploying to a new environment (e.g. Vercel)
with app.app_context():
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if not tables or 'users' not in tables:
            db.create_all()
            from seed_data import seed_database
            seed_database(app)
    except Exception as exc:
        app.logger.warning(f"Database auto-initialization check: {exc}")

if __name__ == "__main__":
    app.run()
