import sqlite3, os, secrets
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'codecrafters.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def now_iso():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def generate_ticket_no():
    return f"TKT-{datetime.utcnow().strftime('%Y%m')}-{secrets.token_hex(3).upper()}"

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS departments (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name  TEXT UNIQUE NOT NULL,
        email TEXT,
        head  TEXT
    );

    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        student_no    TEXT UNIQUE,
        full_name     TEXT NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        phone         TEXT,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL DEFAULT 'student',
        department_id INTEGER,
        is_active     INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT NOT NULL,
        FOREIGN KEY(department_id) REFERENCES departments(id)
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_no     TEXT UNIQUE NOT NULL,
        student_id    INTEGER NOT NULL,
        department_id INTEGER NOT NULL,
        assigned_to   INTEGER,
        subject       TEXT NOT NULL,
        description   TEXT NOT NULL,
        priority      TEXT NOT NULL DEFAULT 'Medium',
        status        TEXT NOT NULL DEFAULT 'Pending',
        is_anonymous  INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        resolved_at   TEXT,
        rating        INTEGER,
        rating_comment TEXT,
        FOREIGN KEY(student_id)    REFERENCES users(id),
        FOREIGN KEY(department_id) REFERENCES departments(id),
        FOREIGN KEY(assigned_to)   REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS ticket_updates (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id   INTEGER NOT NULL,
        author_id   INTEGER NOT NULL,
        old_status  TEXT,
        new_status  TEXT,
        message     TEXT,
        is_internal INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL,
        FOREIGN KEY(ticket_id)  REFERENCES tickets(id),
        FOREIGN KEY(author_id)  REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS attachments (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id     INTEGER NOT NULL,
        filename      TEXT NOT NULL,
        original_name TEXT NOT NULL,
        file_size     INTEGER,
        uploaded_at   TEXT NOT NULL,
        FOREIGN KEY(ticket_id) REFERENCES tickets(id)
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        ticket_id  INTEGER,
        title      TEXT NOT NULL,
        message    TEXT NOT NULL,
        is_read    INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id)   REFERENCES users(id),
        FOREIGN KEY(ticket_id) REFERENCES tickets(id)
    );
    """)

    depts = [
        ('Finance',         'finance@dut.ac.za',          'Finance Department'),
        ('IT & Systems',    'itsupport@dut.ac.za',        'IT Support'),
        ('Academic',        'academic@dut.ac.za',         'Academic Affairs'),
        ('Student Affairs', 'studentaffairs@dut.ac.za',   'Student Affairs'),
        ('Accommodation',   'residence@dut.ac.za',        'Residence Office'),
        ('Library',         'library@dut.ac.za',          'Library Services'),
        ('Health Sciences', 'health@dut.ac.za',           'Health Sciences Faculty'),
        ('Management',      'management@dut.ac.za',       'Faculty of Management'),
        ('Engineering',     'engineering@dut.ac.za',      'Faculty of Engineering'),
        ('Other',           'info@dut.ac.za',             'General Enquiries'),
    ]
    for name, email, head in depts:
        c.execute("INSERT OR IGNORE INTO departments(name,email,head) VALUES(?,?,?)", (name, email, head))

    from werkzeug.security import generate_password_hash
    now = now_iso()
    pw_staff = generate_password_hash('Staff@2026')
    # Format: (student_no, full_name, email, password_hash, role, dept_name)
    # Emails follow name.surname@dut.ac.za — max 3 staff per department
    seed = [
        # System accounts
        (None,       'Super Administrator', 'admin@dut.ac.za',          generate_password_hash('Admin@2026'),   'superadmin', None),
        ('21000001', 'Demo Student',        'student@dut.ac.za',         generate_password_hash('Student@2026'), 'student',    None),
        # Finance (3)
        (None, 'Thandi Nkosi',      'thandi.nkosi@dut.ac.za',      pw_staff, 'staff', 'Finance'),
        (None, 'Sipho Dlamini',     'sipho.dlamini@dut.ac.za',     pw_staff, 'staff', 'Finance'),
        (None, 'Nomsa Mthembu',     'nomsa.mthembu@dut.ac.za',     pw_staff, 'staff', 'Finance'),
        # IT & Systems (3)
        (None, 'Ravi Pillay',       'ravi.pillay@dut.ac.za',       pw_staff, 'staff', 'IT & Systems'),
        (None, 'Lungelo Zungu',     'lungelo.zungu@dut.ac.za',     pw_staff, 'staff', 'IT & Systems'),
        (None, 'Priya Naidoo',      'priya.naidoo@dut.ac.za',      pw_staff, 'staff', 'IT & Systems'),
        # Academic (3)
        (None, 'Zanele Mokoena',    'zanele.mokoena@dut.ac.za',    pw_staff, 'staff', 'Academic'),
        (None, 'James Reddy',       'james.reddy@dut.ac.za',       pw_staff, 'staff', 'Academic'),
        (None, 'Fatima Hassan',     'fatima.hassan@dut.ac.za',     pw_staff, 'staff', 'Academic'),
        # Student Affairs (3)
        (None, 'Bongani Shabalala', 'bongani.shabalala@dut.ac.za', pw_staff, 'staff', 'Student Affairs'),
        (None, 'Ayanda Mhlongo',    'ayanda.mhlongo@dut.ac.za',    pw_staff, 'staff', 'Student Affairs'),
        (None, 'Lerato Sithole',    'lerato.sithole@dut.ac.za',    pw_staff, 'staff', 'Student Affairs'),
        # Accommodation (3)
        (None, 'Mandla Ngcobo',     'mandla.ngcobo@dut.ac.za',     pw_staff, 'staff', 'Accommodation'),
        (None, 'Thandeka Zulu',     'thandeka.zulu@dut.ac.za',     pw_staff, 'staff', 'Accommodation'),
        (None, 'Sifiso Ntuli',      'sifiso.ntuli@dut.ac.za',      pw_staff, 'staff', 'Accommodation'),
        # Library (3)
        (None, 'Phumzile Cele',     'phumzile.cele@dut.ac.za',     pw_staff, 'staff', 'Library'),
        (None, 'Sandile Majola',    'sandile.majola@dut.ac.za',    pw_staff, 'staff', 'Library'),
        (None, 'Nokukhanya Dube',   'nokukhanya.dube@dut.ac.za',   pw_staff, 'staff', 'Library'),
        # Health Sciences (3)
        (None, 'Aisha Patel',       'aisha.patel@dut.ac.za',       pw_staff, 'staff', 'Health Sciences'),
        (None, 'Thabo Khumalo',     'thabo.khumalo@dut.ac.za',     pw_staff, 'staff', 'Health Sciences'),
        (None, 'Nompumelelo Gumede','nompumelelo.gumede@dut.ac.za',pw_staff, 'staff', 'Health Sciences'),
        # Management (3)
        (None, 'Sibusiso Mthiyane', 'sibusiso.mthiyane@dut.ac.za', pw_staff, 'staff', 'Management'),
        (None, 'Lindiwe Buthelezi', 'lindiwe.buthelezi@dut.ac.za', pw_staff, 'staff', 'Management'),
        (None, 'Khulekani Hadebe',  'khulekani.hadebe@dut.ac.za',  pw_staff, 'staff', 'Management'),
        # Engineering (3)
        (None, 'Arjun Singh',       'arjun.singh@dut.ac.za',       pw_staff, 'staff', 'Engineering'),
        (None, 'Nhlanhla Msweli',   'nhlanhla.msweli@dut.ac.za',   pw_staff, 'staff', 'Engineering'),
        (None, 'Yusuf Essack',      'yusuf.essack@dut.ac.za',      pw_staff, 'staff', 'Engineering'),
        # Other (3)
        (None, 'Nokwanda Mthembu',  'nokwanda.mthembu@dut.ac.za',  pw_staff, 'staff', 'Other'),
        (None, 'Mthokozisi Ntanzi', 'mthokozisi.ntanzi@dut.ac.za', pw_staff, 'staff', 'Other'),
        (None, 'Zanele Zwane',      'zanele.zwane@dut.ac.za',      pw_staff, 'staff', 'Other'),
    ]
    for sno, name, email, pw, role, dept_name in seed:
        dept_id = None
        if dept_name:
            row = c.execute("SELECT id FROM departments WHERE name=?", (dept_name,)).fetchone()
            if row: dept_id = row[0]
        c.execute("INSERT OR IGNORE INTO users (student_no,full_name,email,password_hash,role,department_id,is_active,created_at) VALUES(?,?,?,?,?,?,1,?)",
                  (sno, name, email, pw, role, dept_id, now))
    conn.commit()
    conn.close()
