"""
Safe, repeatable SQLite to MongoDB Atlas migration script for Campus Voice.

Guarantees:
1. Strict read-only access to local SQLite database (uses URI mode=ro).
2. Never modifies, deletes, or recreates local SQLite files or backups.
3. Idempotent: checks for existing records before inserting.
4. Stops and reports if conflicting records are found; never silently overwrites.
5. Accurately maps foreign key relationships (student_id, faculty_id, course_id)
   to corresponding MongoDB ObjectIds.
6. Provides --dry-run flag to preview migration actions safely.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import PyMongoError

# Ensure parent directory is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.db import get_mongo_client, get_db, init_indexes


def parse_datetime(val: Any) -> datetime:
    """Parses various SQLite datetime string formats into Python datetime."""
    if isinstance(val, datetime):
        return val
    if not val:
        return datetime.utcnow()
    val_str = str(val).strip()
    for fmt in (
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d'
    ):
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def run_migration(sqlite_path: Path, mongo_uri: Optional[str] = None, dry_run: bool = False):
    """
    Executes safe migration from SQLite to MongoDB Atlas.
    """
    print("=" * 70)
    print(" Campus Voice: SQLite -> MongoDB Atlas Safe Migration")
    print("=" * 70)
    print(f" Source SQLite DB: {sqlite_path} (Read-Only Mode)")
    print(f" Dry Run Mode:     {'ENABLED (No changes will be written)' if dry_run else 'DISABLED (Live Migration)'}")

    if not sqlite_path.exists():
        print(f"ERROR: SQLite database file not found at: {sqlite_path}", file=sys.stderr)
        sys.exit(1)

    # 1. Connect to SQLite in STRICT READ-ONLY mode using SQLite URI
    sqlite_uri = f"file:{sqlite_path.resolve().as_posix()}?mode=ro"
    try:
        sqlite_conn = sqlite3.connect(sqlite_uri, uri=True)
        sqlite_conn.row_factory = sqlite3.Row
        cur = sqlite_conn.cursor()
    except Exception as e:
        print(f"ERROR: Failed to open SQLite database in read-only mode: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Connect to MongoDB Atlas
    try:
        db = get_db(uri=mongo_uri)
        # Verify connection
        db.command('ping')
        print(f" Connected to MongoDB database: '{db.name}'")
    except Exception as e:
        if dry_run:
            print(f" [NOTE] Live MongoDB connection unavailable ({e}). Using in-memory simulation for dry-run.")
            try:
                import mongomock
                client = mongomock.MongoClient()
                db = client['campus_voice_dryrun']
            except ImportError:
                print(f"ERROR: Failed to connect to MongoDB: {e}", file=sys.stderr)
                sqlite_conn.close()
                sys.exit(1)
        else:
            print(f"ERROR: Failed to connect to MongoDB Atlas: {e}", file=sys.stderr)
            sqlite_conn.close()
            sys.exit(1)

    if not dry_run:
        init_indexes(db)

    # 3. Read SQLite records
    users = cur.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    faculties = cur.execute("SELECT * FROM faculties ORDER BY id ASC").fetchall()
    courses = cur.execute("SELECT * FROM courses ORDER BY id ASC").fetchall()
    feedbacks = cur.execute("SELECT * FROM feedbacks ORDER BY id ASC").fetchall()

    print(f"\n[READ] SQLite Records Discovered:")
    print(f"  - Users:     {len(users)}")
    print(f"  - Faculties: {len(faculties)}")
    print(f"  - Courses:   {len(courses)}")
    print(f"  - Feedbacks: {len(feedbacks)}")

    user_id_map: Dict[int, str] = {}
    faculty_id_map: Dict[int, str] = {}
    course_id_map: Dict[int, str] = {}

    conflicts = []

    # 4. Migrate Users
    print("\n--- [Phase 1/4] Migrating Users ---")
    users_to_insert = []
    for u in users:
        sqlite_id = u['id']
        email = u['email'].strip().lower()
        existing = db.users.find_one({"email": email})

        if existing:
            # Check for conflicting student_id or role
            existing_sid = (existing.get('student_id') or '').upper()
            sqlite_sid = (u['student_id'] or '').upper()
            if existing_sid != sqlite_sid and (existing_sid and sqlite_sid):
                conflicts.append(f"User conflict for email '{email}': existing student_id='{existing_sid}' vs sqlite student_id='{sqlite_sid}'")
            user_id_map[sqlite_id] = str(existing['_id'])
            print(f"  [*] User '{email}' already exists in MongoDB (ID: {existing['_id']}). Preserving existing record.")
        else:
            new_id = ObjectId()
            user_id_map[sqlite_id] = str(new_id)
            doc = {
                "_id": new_id,
                "name": u['name'],
                "email": email,
                "student_id": u['student_id'].strip().upper() if u['student_id'] else None,
                "department": u['department'],
                "password_hash": u['password_hash'],
                "role": u['role'],
                "is_active": bool(u['is_active']),
                "created_at": parse_datetime(u['created_at']),
                "_migrated_from_sqlite_id": sqlite_id
            }
            users_to_insert.append(doc)
            print(f"  [+] Prepared User: {u['name']} <{email}> (Role: {u['role']})")

    # 5. Migrate Faculties
    print("\n--- [Phase 2/4] Migrating Faculties ---")
    faculties_to_insert = []
    for f in faculties:
        sqlite_id = f['id']
        name = f['faculty_name'].strip()
        email = f['email'].strip().lower() if f['email'] else None

        query = {"faculty_name": name}
        if email:
            query = {"$or": [{"faculty_name": name}, {"email": email}]}
        existing = db.faculties.find_one(query)

        if existing:
            if email and existing.get('email') == email and existing.get('faculty_name') != name:
                conflicts.append(f"Faculty conflict for email '{email}': existing name='{existing.get('faculty_name')}' vs sqlite name='{name}'")
            faculty_id_map[sqlite_id] = str(existing['_id'])
            print(f"  [*] Faculty '{name}' already exists in MongoDB (ID: {existing['_id']}). Preserving existing record.")
        else:
            new_id = ObjectId()
            faculty_id_map[sqlite_id] = str(new_id)
            doc = {
                "_id": new_id,
                "faculty_name": name,
                "department": f['department'],
                "email": email,
                "is_active": bool(f['is_active']),
                "created_at": parse_datetime(f['created_at']),
                "_migrated_from_sqlite_id": sqlite_id
            }
            faculties_to_insert.append(doc)
            print(f"  [+] Prepared Faculty: {name} ({f['department']})")

    # 6. Migrate Courses
    print("\n--- [Phase 3/4] Migrating Courses ---")
    courses_to_insert = []
    for c in courses:
        sqlite_id = c['id']
        code = c['course_code'].strip().upper()
        existing = db.courses.find_one({"course_code": code})

        # Map assigned faculty
        sqlite_fac_id = c['faculty_id']
        mongo_fac_id = faculty_id_map.get(sqlite_fac_id) if sqlite_fac_id else None

        if existing:
            if existing.get('course_name') != c['course_name']:
                conflicts.append(f"Course conflict for code '{code}': existing name='{existing.get('course_name')}' vs sqlite name='{c['course_name']}'")
            course_id_map[sqlite_id] = str(existing['_id'])
            print(f"  [*] Course '{code}' already exists in MongoDB (ID: {existing['_id']}). Preserving existing record.")
        else:
            new_id = ObjectId()
            course_id_map[sqlite_id] = str(new_id)
            doc = {
                "_id": new_id,
                "course_name": c['course_name'],
                "course_code": code,
                "department": c['department'],
                "faculty_id": mongo_fac_id,
                "is_active": bool(c['is_active']),
                "created_at": parse_datetime(c['created_at']),
                "_migrated_from_sqlite_id": sqlite_id
            }
            courses_to_insert.append(doc)
            print(f"  [+] Prepared Course: {code} - {c['course_name']}")

    # 7. Migrate Feedbacks
    print("\n--- [Phase 4/4] Migrating Feedbacks ---")
    feedbacks_to_insert = []
    for fb in feedbacks:
        sqlite_id = fb['id']
        sqlite_stu = fb['student_id']
        sqlite_fac = fb['faculty_id']
        sqlite_crs = fb['course_id']

        mongo_stu = user_id_map.get(sqlite_stu)
        mongo_fac = faculty_id_map.get(sqlite_fac)
        mongo_crs = course_id_map.get(sqlite_crs)

        if not mongo_stu or not mongo_fac or not mongo_crs:
            conflicts.append(f"Feedback ID {sqlite_id} refers to missing entity mapping: Student={mongo_stu}, Faculty={mongo_fac}, Course={mongo_crs}")
            continue

        existing = db.feedbacks.find_one({
            "student_id": mongo_stu,
            "faculty_id": mongo_fac,
            "course_id": mongo_crs
        })

        if existing:
            if existing.get('rating') != int(fb['rating']):
                conflicts.append(f"Feedback conflict for Student:{mongo_stu} Course:{mongo_crs} Faculty:{mongo_fac}: existing rating={existing.get('rating')} vs sqlite rating={fb['rating']}")
            print(f"  [*] Feedback for Student:{mongo_stu} Course:{mongo_crs} Faculty:{mongo_fac} already exists. Preserving.")
        else:
            new_id = ObjectId()
            doc = {
                "_id": new_id,
                "student_id": mongo_stu,
                "faculty_id": mongo_fac,
                "course_id": mongo_crs,
                "rating": int(fb['rating']),
                "comments": fb['comments'] or '',
                "created_at": parse_datetime(fb['created_at']),
                "_migrated_from_sqlite_id": sqlite_id
            }
            feedbacks_to_insert.append(doc)
            print(f"  [+] Prepared Feedback: Student:{mongo_stu} -> Course:{mongo_crs} ({fb['rating']}/5 stars)")

    # 8. Check for conflicts
    if conflicts:
        print("\n" + "!" * 70, file=sys.stderr)
        print("MIGRATION HALTED DUE TO CONFLICTS / INTEGRITY ISSUES:", file=sys.stderr)
        for conf in conflicts:
            print(f"  - {conf}", file=sys.stderr)
        print("!" * 70, file=sys.stderr)
        sqlite_conn.close()
        sys.exit(1)

    # 9. Perform Live Migration or Dry Run Summary
    print("\n" + "=" * 70)
    print(" MIGRATION PLAN SUMMARY:")
    print(f"  - Users to insert:     {len(users_to_insert)}")
    print(f"  - Faculties to insert: {len(faculties_to_insert)}")
    print(f"  - Courses to insert:   {len(courses_to_insert)}")
    print(f"  - Feedbacks to insert: {len(feedbacks_to_insert)}")
    print("=" * 70)

    if dry_run:
        print("\n[DRY RUN COMPLETE] No records were written to MongoDB Atlas. SQLite database was untouched.")
        sqlite_conn.close()
        return

    # Execute batch inserts
    if users_to_insert:
        db.users.insert_many(users_to_insert)
    if faculties_to_insert:
        db.faculties.insert_many(faculties_to_insert)
    if courses_to_insert:
        db.courses.insert_many(courses_to_insert)
    if feedbacks_to_insert:
        db.feedbacks.insert_many(feedbacks_to_insert)

    # 10. Post-migration verification
    final_users = db.users.count_documents({})
    final_faculties = db.faculties.count_documents({})
    final_courses = db.courses.count_documents({})
    final_feedbacks = db.feedbacks.count_documents({})

    print("\n[VERIFICATION] Final MongoDB Atlas Collection Counts:")
    print(f"  - Users:     {final_users}")
    print(f"  - Faculties: {final_faculties}")
    print(f"  - Courses:   {final_courses}")
    print(f"  - Feedbacks: {final_feedbacks}")
    print("\n[SUCCESS] Migration completed successfully without overwriting existing data!")

    sqlite_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Campus Voice SQLite to MongoDB Atlas Migration Tool")
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path("instance/feedback.db"),
        help="Path to the source SQLite database file (default: instance/feedback.db)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the migration without modifying MongoDB Atlas"
    )
    parser.add_argument(
        "--mongodb-uri",
        type=str,
        default=None,
        help="MongoDB connection URI (defaults to MONGODB_URI environment variable)"
    )
    args = parser.parse_args()

    run_migration(args.sqlite_path, args.mongodb_uri, args.dry_run)


if __name__ == "__main__":
    main()
