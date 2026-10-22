"""
Entry point and CLI management for Campus Voice.
Provides commands for database initialization, seeding, and administrator provisioning.
"""
import getpass
import os
import sys
import click
from app import create_app
from app.db import get_db, init_indexes
from app.models import User
from seed_data import seed_database

app = create_app()


@app.cli.command("init-db")
def init_db_command():
    """Create all required MongoDB indexes."""
    with app.app_context():
        init_indexes(get_db())
        click.echo("✓ MongoDB indexes created and verified successfully.")


@app.cli.command("seed-db")
def seed_db_command():
    """Seed the database with real academic catalog and initial administrator."""
    seed_database(app)
    click.echo("✓ MongoDB database seeded successfully.")


@app.cli.command("create-admin")
@click.option("--name", prompt="Administrator Full Name", help="Admin's full name.")
@click.option("--email", prompt="Administrator Email", help="Admin's email address.")
@click.option("--department", default="Administration", prompt="Department", help="Admin's department.")
@click.password_option(prompt="Password", confirmation_prompt=True, help="Admin's password.")
def create_admin_command(name, email, department, password):
    """Safely create a new Administrator account."""
    with app.app_context():
        normalized_email = email.strip().lower()
        existing = User.find_by_email(normalized_email)
        if existing:
            click.echo(f"Error: A user with email '{normalized_email}' already exists.", err=True)
            return

        admin = User(
            name=name.strip(),
            email=normalized_email,
            department=department.strip(),
            student_id=None,
            role="admin",
            is_active=True
        )
        admin.set_password(password)

        try:
            admin.save()
            click.echo(f"✓ Administrator account '{admin.email}' created successfully.")
        except Exception as e:
            click.echo(f"Error creating administrator: {e}", err=True)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == 'init-db':
            with app.app_context():
                init_indexes(get_db())
                print("[OK] MongoDB indexes created and verified successfully.")
        elif cmd == 'seed-db':
            seed_database(app)
            print("[OK] MongoDB database seeded successfully.")
        elif cmd == 'create-admin':
            print("=== Safe Administrator Account Creation ===")
            name = input("Administrator Full Name: ").strip()
            email = input("Administrator Email: ").strip().lower()
            dept = input("Department [Administration]: ").strip() or "Administration"
            pwd = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm Password: ")
            if pwd != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                sys.exit(1)
            with app.app_context():
                existing = User.find_by_email(email)
                if existing:
                    print(f"Error: User with email '{email}' already exists.", file=sys.stderr)
                    sys.exit(1)
                admin = User(
                    name=name,
                    email=email,
                    department=dept,
                    student_id=None,
                    role='admin',
                    is_active=True
                )
                admin.set_password(pwd)
                admin.save()
                print(f"[OK] Administrator account '{email}' created successfully.")
        else:
            print(f"Unknown command: {cmd}")
            print("Available commands: init-db, seed-db, create-admin, or run without arguments to start web server.")
    else:
        debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() in ('true', '1')
        host = os.environ.get('FLASK_HOST', '127.0.0.1')
        port = int(os.environ.get('FLASK_PORT', 5000))
        print("\n" + "=" * 60)
        print(" Campus Voice - Student Feedback & Academic Quality System")
        print(f" Access Web Portal: http://{host}:{port}")
        print(" Engine:            MongoDB Atlas (PyMongo)")
        print(" Environment:       " + ("Development (Debug On)" if debug_mode else "Production (Debug Off)"))
        print(" Use 'python run.py create-admin' to securely configure administrators.")
        print("=" * 60 + "\n")
        app.run(host=host, port=port, debug=debug_mode)
