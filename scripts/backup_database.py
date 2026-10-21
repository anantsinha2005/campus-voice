import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
basedir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(basedir))

from app.config import Config

def backup_db():
    src_path = basedir / 'instance' / 'feedback.db'
    if not src_path.exists():
        print(f"Error: Source database does not exist at {src_path}", file=sys.stderr)
        sys.exit(1)

    backup_dir = basedir / 'instance' / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"feedback_backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename

    print(f"[INFO] Initiating consistent SQLite backup...")
    print(f"  Source: {src_path}")
    print(f"  Target: {backup_path}")

    try:
        # Use SQLite backup API for consistent, atomic snapshot
        src_conn = sqlite3.connect(str(src_path))
        dst_conn = sqlite3.connect(str(backup_path))
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        dst_conn.close()
        src_conn.close()

        # Validate backup file
        if not backup_path.exists() or backup_path.stat().st_size == 0:
            raise RuntimeError("Backup file was not created or is zero bytes.")

        # Test readability and integrity of the backup file
        verify_conn = sqlite3.connect(str(backup_path))
        verify_cur = verify_conn.cursor()
        verify_cur.execute("PRAGMA integrity_check;")
        res = verify_cur.fetchone()
        if not res or res[0] != "ok":
            raise RuntimeError(f"Integrity check failed on backup: {res}")

        # Check record counts in backup
        counts = {}
        for table in ['users', 'courses', 'faculties', 'feedbacks']:
            verify_cur.execute(f"SELECT COUNT(*) FROM {table};")
            counts[table] = verify_cur.fetchone()[0]
        verify_conn.close()

        print(f"[SUCCESS] Consistent backup created and verified successfully!")
        print(f"  Backup Path: {backup_path}")
        print(f"  Backup Size: {backup_path.stat().st_size} bytes")
        print(f"  Record Counts in Backup: {counts}")
        return str(backup_path)

    except Exception as e:
        print(f"[ERROR] Backup failed: {e}", file=sys.stderr)
        if backup_path.exists():
            backup_path.unlink()
        sys.exit(1)

if __name__ == '__main__':
    backup_db()
