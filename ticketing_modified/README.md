# CodeCrafters — DUT Student Ticketing System
## Group 2 | PBDV301 & PBDE401 | Due: 23 March 2026

---

## Run Locally

```bash
pip install flask werkzeug
python app.py
```
Then open: http://localhost:5000

---

## Demo Accounts

| Role        | Email                | Password      |
|-------------|----------------------|---------------|
| Super Admin | admin@dut.ac.za      | Admin@2026    |
| Staff (Finance) | finance@dut.ac.za | Staff@2026  |
| Staff (IT)  | it@dut.ac.za         | Staff@2026    |
| Student     | student@dut.ac.za    | Student@2026  |

---

## Deploy to PythonAnywhere

1. Upload the project zip to PythonAnywhere Files
2. Unzip: `unzip codecrafters.zip`
3. Go to **Web** tab → Add new web app → Flask → Python 3.12
4. Set source directory to `/home/<username>/grievance_portal`
5. Set WSGI file to point to `app` from `app.py`
6. Reload the app

## Deploy to Render

1. Push to GitHub
2. New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`

---

## Features
- Student registration & login
- Submit tickets with department routing, priority, file attachments
- Unique ticket reference numbers (TKT-YYYYMM-XXXXXX)
- Real-time status tracking: Pending → In Progress → Assigned → Resolved
- Staff/Admin dashboard with filters and assignment
- Internal vs public comments on tickets
- Notifications system
- Analytics & reports
- Service rating after resolution
- POPIA compliance notice
- Anonymous submission option
- Super Admin: manage users, departments

## Tech Stack
- Python 3 + Flask
- SQLite (codecrafters.db, auto-created on first run)
- Bootstrap 5 + Font Awesome + Google Fonts
- No external dependencies beyond Flask + Werkzeug
