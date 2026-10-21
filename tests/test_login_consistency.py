import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.config import Config
from app.models import db, User


class LocalTestingConfig(Config):
    WTF_CSRF_ENABLED = False


class LoginConsistencyTestCase(unittest.TestCase):
    def test_01_local_database_repeated_logins(self):
        """Tests that admin logs in consistently on local DB across repeated attempts."""
        app = create_app(LocalTestingConfig)
        for i in range(5):
            with app.test_client() as client:
                res = client.post("/login", data={
                    "email": "admin@university.edu",
                    "password": "AdminSecure2026!"
                })
                self.assertEqual(res.status_code, 302, f"Attempt {i}: Admin login failed")
                self.assertIn("/admin/dashboard", res.headers.get("Location"))

        for i in range(5):
            with app.test_client() as client:
                res = client.post("/login", data={
                    "email": "admin@university.edu",
                    "password": "IncorrectPassword!"
                })
                self.assertEqual(res.status_code, 200)
                self.assertIn("Invalid email address or password", res.data.decode("utf-8"))

    def test_02_multiple_container_admin_consistency(self):
        """Tests that independent containers initialize admin password identically."""
        for c_id in range(1, 4):
            tmp_db = Path(tempfile.gettempdir()) / f"test_container_{c_id}.db"
            if tmp_db.exists():
                try:
                    tmp_db.unlink()
                except OSError:
                    pass

            class MockContainerConfig(Config):
                SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_db.as_posix()}"
                WTF_CSRF_ENABLED = False

            c_app = create_app(MockContainerConfig)
            with c_app.test_client() as c_client:
                # First attempt
                r1 = c_client.post("/login", data={
                    "email": "admin@university.edu",
                    "password": "AdminSecure2026!"
                })
                self.assertEqual(r1.status_code, 302, f"Container {c_id} attempt 1 failed")
                
                # Second attempt
                r2 = c_client.post("/login", data={
                    "email": "admin@university.edu",
                    "password": "AdminSecure2026!"
                })
                self.assertEqual(r2.status_code, 302, f"Container {c_id} attempt 2 failed")

            with c_app.app_context():
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
