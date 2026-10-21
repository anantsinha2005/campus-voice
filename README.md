# 🎓 Campus Voice

> **Student Feedback Management System**

A responsive, production-ready, full-stack web application designed for academic institutions to collect, analyze, and manage student feedback on courses and faculty members. Built with Python Flask, SQLite, Flask-SQLAlchemy, Flask-Login, Bootstrap 5, and Chart.js.

---

## 🌟 Key Features

### 👨‍🎓 Student Portal
* **Account Registration:** Dedicated registration with name, institutional email, student roll ID, department, and password. Strict server-side validation prevents self-promotion to administrator.
* **Student Dashboard:** Real-time summary of submitted evaluations, available courses, and active faculty.
* **Course Catalog & Assigned Faculty:** Feedback form displays courses formatted as `<Subject Name> (<Subject Code>)` with automatic selection/locking of the assigned faculty member.
* **Interactive 5-Star Rating Component:**
  * Rating scale calibrated from **1 (Terrible)** to **5 (Excellent)**.
  * Gold visual star highlighting from left to right matching DOM and CSS pseudo-states.
  * Real-time descriptive label displayed upon star selection.
* **Qualitative Comments Field:**
  * **Optional written comments** (0 to 1000 characters) allowing students to submit ratings quickly or provide detailed commentary.
  * Dynamic character counter updates in real time.
* **Duplicate Prevention:** Enforces uniqueness both at the business-logic layer and the relational database level (one evaluation per student-course-faculty combination).
* **Submission History:** View own prior feedback submissions with ratings, descriptive labels (e.g. *5★ (Excellent)*), date stamps, and full commentary. Strictly isolated to protect student privacy.

### 🛡️ Administrator Portal
* **Analytics Dashboard:**
  * Real-time summary metrics:
    * **Total Registered Students**
    * **Total Active Courses**
    * **Total Faculty Members**
    * **Total Feedback Submissions**
    * **Overall Average Rating**
  * **Chart.js Visualizations:**
    1. **Rating Distribution Breakdown:** Doughnut chart categorized as *1 Star (Terrible)*, *2 Stars (Poor)*, *3 Stars (Average)*, *4 Stars (Good)*, and *5 Stars (Excellent)*.
    2. **Faculty Performance Benchmarking:** Horizontal bar chart of average instructor ratings.
    3. **Course Satisfaction Metrics:** Bar chart of average course ratings.
  * Recent activity feed with direct links to full audits.
* **Faculty Management:** Complete CRUD workflow to list, add new faculty, edit details, and toggle active/deactivated status.
* **Course Catalog Management:** Add, edit, and toggle active/deactivated status for academic courses across departments.
* **Student Directory:** Audit registered student accounts, departments, and evaluation submission counts.
* **Searchable & Filterable Feedback Review:**
  * Multi-criteria filtering by Course, Faculty Member, Rating (1 - Terrible to 5 - Excellent), and Date Range (From / To).
  * Full-text search across feedback comments, student names, student IDs, and course codes.
  * Instant calculation of filtered record counts and filtered average ratings.
  * Feedback table displays Feedback ID, Student Roll ID, Student Name, Course, Faculty, Rating (with descriptive text), Comments, and Date.
* **CSV Export Engine:** One-click dynamic export of complete or filtered evaluation datasets to CSV (`student_feedback_report_<timestamp>.csv`) including exact rating numbers and descriptive rating labels.

### 🔒 Security & Architecture
* **Authentication:** Session-based authentication via `Flask-Login` with secure cookie flags (`HttpOnly`, `SameSite=Lax`, configurable `SESSION_COOKIE_SECURE`).
* **Password Hashing:** Passwords hashed with `Werkzeug` PBKDF2/scrypt before persistence. Plaintext passwords are never stored.
* **No Insecure Default Credentials:** Hardcoded default passwords have been eliminated. Initial admin credentials must be configured via environment variables or provisioned interactively via CLI.
* **CSRF Protection:** Form-level CSRF token validation via `Flask-WTF`.
* **Role-Based Access Control (RBAC):** Backend route protection via custom decorators (`@student_required`, `@admin_required`) preventing privilege escalation.
* **SQL Injection Prevention:** Parameterized database queries managed by `Flask-SQLAlchemy` ORM.
* **Health Check Endpoints:** Native `/health` and `/healthz` endpoints verifying application status and active database connectivity.

---

## 📚 Real Subject & Faculty Assignments Catalog

The system catalog contains the following 6 active subject-faculty assignments:

| # | Subject Code | Subject Name | Assigned Faculty | Department |
|---|---|---|---|---|
| 1 | **BCO017A** | Formal Languages and Automation Theory | **Gajanand Sharma** | Computer Science & Engineering |
| 2 | **BCO023A** | Design and Analysis of Algorithms | **Sonal Saxena** | Computer Science & Engineering |
| 3 | **BCO037B** | Advance Programming in Java | **Neha Solanki** | Computer Science & Engineering |
| 4 | **BCO019A** | Artificial Intelligence | **Ankur Agrawal** | Computer Science & Engineering |
| 5 | **BCO074C** | Minor Project | **Mahesh Kumar Joshi** | Computer Science & Engineering |
| 6 | **BCO681A** | Web Designing Using AI | **Mohit Parashar** | Computer Science & Engineering |

When a student selects a course on the feedback form, the assigned instructor is automatically selected and locked, preventing invalid or mismatched submissions.

---

## ⭐ Corrected Feedback Rating Scale

The rating scale is calibrated from **1 (lowest/worst)** to **5 (highest/best)**:

| Rating Value | Visual Stars | Descriptive Label | Definition |
|:---:|:---:|:---:|---|
| **5** | ★★★★★ | **5 - Excellent** | Outstanding performance, highest quality instruction |
| **4** | ★★★★☆ | **4 - Good** | Strong competence, effective delivery and guidance |
| **3** | ★★★☆☆ | **3 - Average** | Satisfactory performance meeting baseline requirements |
| **2** | ★★☆☆☆ | **2 - Poor** | Below standard, needs noticeable improvement |
| **1** | ★☆☆☆☆ | **1 - Terrible** | Unsatisfactory experience, severe pedagogical deficiency |

### Rating Consistency Across Application Layers:
* **Interactive Star Input:** Visual stars are laid out 1 on the left to 5 on the right. Hovering over star $N$ highlights stars 1 through $N$ in gold.
* **Student History:** Displays numeric stars and labels (e.g. `5★ (Excellent)`).
* **Admin Review Table:** Displays numeric stars alongside the exact rating label badge.
* **Analytics Doughnut Chart:** Chart segments are labeled `1 Star (Terrible)` through `5 Stars (Excellent)`.
* **CSV Export:** Includes a dedicated `Rating Label` column.
* **Optional Comments:** Written comments are strictly optional. Students can submit ratings with empty comments or qualitative commentary up to 1000 characters.

---

## 🧹 Demo Data Cleanup & Seeding Integrity

* **Removal of Incorrect Demo Feedback:**
  * The historical demo record (Faculty: *Dr. Grace Hopper*, Course: *CS201 Data Structures & Algorithms*, Rating: *1/5*, Comment: *"Good in theory bad in practical"*) has been deleted from the database.
* **Seeder Prevention:**
  * `seed_data.py` has been refactored to seed only the 6 real subject and faculty assignments. It contains zero references to Dr. Grace Hopper or CS201, permanently preventing sample demo anomalies from being reintroduced.

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| **Backend Framework** | Python 3 (Flask 3.x) |
| **Database** | SQLite3 (stored in `instance/feedback.db`) |
| **ORM** | Flask-SQLAlchemy 3.x (SQLAlchemy 2.0 compatible) |
| **Authentication** | Flask-Login |
| **Forms & CSRF** | Flask-WTF & WTForms |
| **Password Security** | Werkzeug Security (`generate_password_hash`, `check_password_hash`) |
| **Frontend Framework** | HTML5, CSS3, JavaScript, Bootstrap 5.3.3, Bootstrap Icons |
| **Data Visualizations**| Chart.js 4.4 |
| **Testing** | Python standard `unittest` (45 automated tests) |

---

## 📁 Project Structure

```text
student_feedback_system/
│
├── app/
│   ├── __init__.py           # Application factory, extensions, error handlers, /health route
│   ├── config.py             # App configuration, security settings, database URI, session flags
│   ├── models.py             # Database models: User, Course, Faculty, Feedback (with rating_label)
│   ├── forms.py              # WTForms forms with backend validators & corrected rating choices
│   ├── decorators.py         # RBAC decorators (@admin_required, @student_required)
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py           # Authentication routes: login, register, logout
│   │   ├── student.py        # Student routes: dashboard, feedback form, history
│   │   └── admin.py          # Admin routes: dashboard, CRUD, filters, CSV export
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css     # Responsive academic theme & star rating styling
│   │   └── js/
│   │       ├── main.js       # Alerts auto-dismiss, tooltips, confirmations
│   │       ├── student.js    # Star rating synchronization & character counter
│   │       └── admin.js      # Chart.js initialization & dynamic analytics fetching
│   │
│   └── templates/
│       ├── base.html         # Base layout with navbar, alerts, footer, and bundles
│       ├── auth/
│       │   ├── login.html    # Authentication page with demo credentials helper
│       │   └── register.html # Student registration page
│       ├── student/
│       │   ├── dashboard.html        # Student landing page & active courses
│       │   ├── submit_feedback.html  # Star rating feedback submission form
│       │   └── feedback_history.html # Student's own prior evaluations
│       ├── admin/
│       │   ├── dashboard.html        # Admin metrics & Chart.js visualizations
│       │   ├── faculty.html          # Faculty management directory & add modal
│       │   ├── faculty_edit.html     # Faculty edit form
│       │   ├── courses.html          # Course management catalog & add modal
│       │   ├── course_edit.html      # Course edit form
│       │   ├── feedback_list.html    # Searchable/filterable table & CSV exporter
│       │   └── students.html         # Enrolled student accounts directory
│       └── errors/
│           ├── 403.html      # Forbidden / Access Denied error page
│           ├── 404.html      # Page Not Found error page
│           └── 500.html      # Server Error rollback page
│
├── instance/
│   ├── feedback.db           # Configured SQLite database file
│   └── backups/              # Atomic timestamped SQLite backup snapshots
│
├── tests/
│   ├── test_app.py                      # Unit & integration tests (RBAC, duplicate prevention, auth)
│   ├── test_e2e.py                      # End-to-end smoke verification against seeded database
│   ├── test_audit_requirements.py       # Full acceptance criteria verification (persistence, filters, CSV)
│   ├── test_catalog_assignments.py      # Verification of the 6 real subject-faculty assignments
│   └── test_audit_reversal_and_cleanup.py # Verification of rating scale, cleanup, and health endpoints
│
├── .env                      # Local environment configuration
├── .env.example              # Sample environment configuration template
├── requirements.txt          # Python package dependencies
├── seed_data.py              # Real catalog seeder
├── run.py                    # Application launcher with CLI utilities
└── README.md                 # Project documentation
```

---

## 🚀 Installation & Setup Instructions

### 1. Prerequisites
* Python 3.9+ (Python 3.10, 3.11, or 3.12 recommended)
* `pip` package manager

### 2. Clone or Navigate to Project Directory
```powershell
cd student_feedback_system
```

### 3. Create a Virtual Environment (Recommended)
```powershell
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On macOS / Linux:
source venv/bin/activate
```

### 4. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```
Ensure `.env` contains your desired settings:
```ini
FLASK_APP=run.py
FLASK_ENV=development
FLASK_DEBUG=false
SECRET_KEY=replace-with-a-very-long-random-secret-key-32chars
DATABASE_URL=sqlite:///feedback.db
ADMIN_PASSWORD=YourStrongAdminPassword2026!
SESSION_COOKIE_SECURE=false
```

### 6. Initialize & Seed Database
Initialize database tables and populate the 6 real subject and faculty records:
```powershell
# 1. Initialize tables:
python run.py init-db

# 2. Seed catalog, demo students, and evaluations:
python run.py seed-db
```

### 7. Create a Custom Administrator
You can safely create additional administrator accounts at any time via the secure CLI utility:
```powershell
python run.py create-admin
```
Follow the interactive prompts to set the administrator's name, email, department, and password.

---

## 🏃 Running the Application

### Development Server:
```powershell
python run.py
```
Open your web browser and navigate to:
👉 **`http://127.0.0.1:5000`**

### Production WSGI Deployment:

#### Option A: Waitress (Recommended for Windows)
```powershell
pip install waitress
waitress-serve --listen=127.0.0.1:5000 run:app
```

#### Option B: Gunicorn (Recommended for Linux/macOS)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "run:create_app()"
```

---

## 🛡️ Production Deployment & Security Checklist

| Configuration Variable | Recommended Production Value | Description |
|---|---|---|
| `FLASK_DEBUG` | `false` / `0` | Disables Flask interactive debugger and stack trace exposure |
| `FLASK_ENV` | `production` | Sets standard production environment |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` | Cryptographically secure random session signing secret |
| `SESSION_COOKIE_SECURE` | `true` | Ensures session cookies are transmitted exclusively over HTTPS |
| `SESSION_COOKIE_HTTPONLY` | `True` (default) | Prevents client-side JavaScript access to session cookies |
| `SESSION_COOKIE_SAMESITE` | `'Lax'` (default) | Mitigates Cross-Site Request Forgery (CSRF) attacks |
| `ADMIN_PASSWORD` | Strong password | Master password for initial CLI admin generation |

---

## 💓 Health Check Endpoints

The application exposes two standardized health monitoring endpoints:
* **`GET /health`**
* **`GET /healthz`**

### Response Example:
```json
{
  "status": "healthy",
  "database": "connected"
}
```
* **Status Code:** `200 OK` when Flask and SQLite are operational.
* **Status Code:** `503 Service Unavailable` if the database query fails.

---

## 💾 Database Backup & Restore Procedures

Database files and backups are stored deterministically under `instance/`:
* Active Database: `instance/feedback.db`
* Backup Directory: `instance/backups/`

### 1. Creating an Atomic Backup
Using the SQLite Backup API guarantees a consistent snapshot even while the application is active:
```powershell
python -c "
import sqlite3, shutil, datetime, os
os.makedirs('instance/backups', exist_ok=True)
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
dest_path = f'instance/backups/feedback_backup_{ts}.db'
src = sqlite3.connect('instance/feedback.db')
dst = sqlite3.connect(dest_path)
with dst:
    src.backup(dst)
dst.close()
src.close()
# Verify backup integrity
chk = sqlite3.connect(dest_path).execute('PRAGMA integrity_check;').fetchone()[0]
print(f'Backup created: {dest_path} (Integrity: {chk})')
"
```

### 2. Restoring from a Backup
1. Stop the application server.
2. Select your backup file from `instance/backups/`.
3. Copy the backup file over `instance/feedback.db`:
```powershell
copy instance\backups\feedback_backup_<timestamp>.db instance\feedback.db
```
4. Verify integrity and restart the application:
```powershell
python -c "import sqlite3; print(sqlite3.connect('instance/feedback.db').execute('PRAGMA integrity_check;').fetchone()[0])"
python run.py
```

---

## 🔑 Pre-Seeded Demonstration Accounts

| Role | Email Address | Password | Description |
|---|---|---|---|
| **Administrator** | `admin@university.edu` | `AdminSecure2026!` | Full administrator dashboard, faculty/course CRUD, analytics, CSV export |
| **Student (1)** | `john.doe@student.university.edu` | `Student123!` | Enrolled student (CSE), prior feedback submissions |
| **Student (2)** | `emily.w@student.university.edu` | `Student123!` | Enrolled student (IT) |
| **Student (3)** | `rahul.s@student.university.edu` | `Student123!` | Enrolled student (ECE) |
| **Student (4)** | `sophia.m@student.university.edu` | `Student123!` | Enrolled student (Business Administration) |

---

## 🧪 Automated Test Suite

The project includes **45 automated tests** covering unit operations, integration workflows, catalog assignments, rating scale correctness, and security policies.

### Run All Tests:
```powershell
python -m unittest discover -s tests -p "test_*.py"
```

### Test Suite Overview:
* **`tests/test_audit_reversal_and_cleanup.py`** (12 tests):
  * Verifies removal of demo feedback record (Dr. Grace Hopper / CS201).
  * Confirms 1-to-5 rating scale labels (1=Terrible, 2=Poor, 3=Average, 4=Good, 5=Excellent).
  * Checks unreversed DOM star rendering for CSS hover alignment.
  * Verifies optional written comments submission.
  * Tests admin dashboard stat cards, filter options, CSV export with rating labels, and `/health` endpoints.
* **`tests/test_catalog_assignments.py`** (7 tests):
  * Verifies all 6 real subject and faculty records and their strict assignments.
  * Confirms auto-mapping and invalid pairing rejection.
* **`tests/test_audit_requirements.py`** (5 tests):
  * Tests persistence across re-login, restart persistence, aggregates, filtering, CSV export, and database transaction rollback safety.
* **`tests/test_app.py`** (19 tests):
  * Unit tests for password hashing, user registration, role boundaries, and duplicate feedback prevention.
* **`tests/test_e2e.py`** (2 tests):
  * End-to-end smoke verification against seeded database records.

---

## 📋 Step-by-Step Feature Walkthrough

### 1. Student Registration & Login
1. Navigate to `http://127.0.0.1:5000/register`.
2. Enter your Name, Student ID (e.g. `CS-2024-1001`), Department, Email, and Password (min 8 chars).
3. Sign in at `http://127.0.0.1:5000/login`.

### 2. Submitting Feedback
1. Click **"Submit Feedback"** in the navigation bar.
2. Choose one of the 6 active courses (e.g., `Formal Languages and Automation Theory (BCO017A)`).
3. Notice the assigned faculty member (**Gajanand Sharma**) is automatically populated.
4. Select a star rating (e.g., 5 Stars - Excellent).
5. (Optional) Enter qualitative remarks or leave the comments field blank.
6. Click **"Submit Feedback"**. A success notification appears, and your evaluation is permanently stored in the database.
7. Attempting to submit feedback again for the same course and faculty member is blocked with a duplicate warning.

### 3. Reviewing Personal Feedback History
1. Click **"My Submissions"** in the student navigation bar.
2. Verify that only your own evaluations are displayed, complete with course codes, assigned faculty, rating stars, rating labels (e.g. `5★ (Excellent)`), and date stamps.

### 4. Administrator Dashboard & Analytics
1. Sign in with administrator credentials: `admin@university.edu` / `AdminSecure2026!`.
2. Inspect the summary cards:
   * **Total Registered Students**
   * **Total Active Courses**
   * **Total Faculty Members**
   * **Total Feedback Submissions**
   * **Overall Average Rating**
3. Review the Chart.js visualizations (Rating distribution doughnut chart, faculty performance benchmarks, and course satisfaction averages).

### 5. Searchable Feedback Table & CSV Export
1. Click **"Feedback Review"** in the admin header.
2. Filter evaluations by:
   * **Course** (e.g., `BCO017A`)
   * **Faculty Member** (e.g., `Gajanand Sharma`)
   * **Rating** (e.g., `5 - Excellent` or `1 - Terrible`)
   * **Date Range** or **Keyword Search** (e.g. student roll number or comment text).
3. Click **"Apply Filters"** to update results and calculate filtered averages.
4. Click **"Export Filtered CSV"** to download the clean CSV report with rating labels and full submission metadata.

---

## 📄 License
This project is open-source and intended for academic institutional use.
