import sqlite3
import shutil
import os

shutil.copy('instance/backups/feedback_backup_20261015_173159.db', 'instance/sandbox_test.db')
conn = sqlite3.connect('instance/sandbox_test.db')
cur = conn.cursor()

# 1. Add faculty_id to courses if not exists
cur.execute('PRAGMA table_info(courses);')
cols = [c[1] for c in cur.fetchall()]
if 'faculty_id' not in cols:
    cur.execute('ALTER TABLE courses ADD COLUMN faculty_id INTEGER REFERENCES faculties(id);')
    print('Added faculty_id to courses table in sandbox.')

# 2. Check faculties email nullable migration
cur.execute('PRAGMA foreign_keys = OFF;')
cur.execute('''
CREATE TABLE faculties_new (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    faculty_name VARCHAR(150) NOT NULL,
    department VARCHAR(100) NOT NULL,
    email VARCHAR(120),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_faculties_email UNIQUE (email)
);
''')
cur.execute('INSERT INTO faculties_new (id, faculty_name, department, email, is_active, created_at) SELECT id, faculty_name, department, email, is_active, created_at FROM faculties;')
cur.execute('DROP TABLE faculties;')
cur.execute('ALTER TABLE faculties_new RENAME TO faculties;')
cur.execute('PRAGMA foreign_keys = ON;')

# 3. Check foreign key integrity
cur.execute('PRAGMA foreign_key_check;')
fks = cur.fetchall()
print('Foreign key check result:', fks)
assert len(fks) == 0, 'Foreign key errors found!'

# 4. Insert real faculty with NULL email
cur.execute("INSERT INTO faculties (faculty_name, department, email, is_active) VALUES ('Gajanand Sharma', 'Computer Science & Engineering', NULL, 1);")
print('Inserted Gajanand Sharma with NULL email successfully!')

conn.commit()
conn.close()
os.remove('instance/sandbox_test.db')
print('Sandbox test PASSED cleanly!')
