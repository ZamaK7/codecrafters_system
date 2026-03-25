import os, uuid, random, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from flask import (Flask, render_template, redirect, url_for, flash,
                   request, session, send_from_directory, jsonify, send_file)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db, now_iso, generate_ticket_no
from report_generator import generate_weekly_report

app = Flask(__name__)
app.secret_key = 'codecrafters-dut-group2-2026'

# ── OTP / Email / SMS Config ─────────────────────────────────────────────────
# Gmail: replace with your Gmail and App Password (myaccount.google.com > Security > App Passwords)
GMAIL_USER     = 'p.themba3468@gmail.com'
GMAIL_PASSWORD = 'otnhjbtaznwnqdor'
# Africa's Talking: replace with your credentials from africastalking.com
AT_USERNAME    = 'sandbox'          # use 'sandbox' for testing
AT_API_KEY     = 'atsk_bce6b1a5d23d261f2e92581fb96dc24552489a03a53d6f58be6b30313601b0833f41e61d'
AT_SENDER_ID   = 'CodeCraft'

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ALLOWED = {'pdf','png','jpg','jpeg','doc','docx'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def allowed(fn): return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED

def current_user():
    if 'uid' not in session: return None
    db = get_db()
    u = db.execute("""SELECT u.*, d.name as dept_name
                      FROM users u LEFT JOIN departments d ON u.department_id=d.id
                      WHERE u.id=? AND u.is_active=1""", (session['uid'],)).fetchone()
    db.close()
    return u

def login_required(f):
    @wraps(f)
    def dec(*a,**k):
        if 'uid' not in session:
            flash('Please log in first.','warning')
            return redirect(url_for('login'))
        return f(*a,**k)
    return dec

def staff_required(f):
    @wraps(f)
    def dec(*a,**k):
        u = current_user()
        if not u or u['role'] not in ('staff','superadmin'):
            flash('Staff access required.','danger')
            return redirect(url_for('dashboard'))
        return f(*a,**k)
    return dec

def superadmin_required(f):
    @wraps(f)
    def dec(*a,**k):
        u = current_user()
        if not u or u['role'] != 'superadmin':
            flash('Super Admin access required.','danger')
            return redirect(url_for('admin_dashboard'))
        return f(*a,**k)
    return dec

@app.context_processor
def ctx():
    u = current_user()
    unread, notifs = 0, []
    if u:
        db = get_db()
        unread = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",(u['id'],)).fetchone()[0]
        notifs = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20",(u['id'],)).fetchall()
        db.close()
    return dict(cu=u, unread=unread, notifs=notifs)

def notify(user_id, title, message, ticket_id=None):
    db = get_db()
    db.execute("INSERT INTO notifications(user_id,ticket_id,title,message,is_read,created_at) VALUES(?,?,?,?,0,?)",
               (user_id, ticket_id, title, message, now_iso()))
    db.commit(); db.close()

# ── Landing ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    u = current_user()
    if u:
        return redirect(url_for('staff_dashboard') if u['role']=='staff' else url_for('admin_dashboard') if u['role']=='superadmin' else url_for('dashboard'))
    return render_template('index.html')

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if current_user(): return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pw    = request.form.get('password','')
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE email=? AND is_active=1",(email,)).fetchone()
        db.close()
        if u and check_password_hash(u['password_hash'], pw):
            session['uid'] = u['id']
            session.permanent = request.form.get('remember')=='on'
            flash(f"Welcome back, {u['full_name'].split()[0]}!",'success')
            return redirect(url_for('staff_dashboard') if u['role']=='staff' else url_for('admin_dashboard') if u['role']=='superadmin' else url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('auth/login.html')


# ── OTP Helpers ───────────────────────────────────────────────────────────────
def generate_otp():
    return str(random.randint(100000, 999999))

def send_email_otp(to_email, otp, name):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'CodeCrafters — Your OTP Verification Code'
        msg['From']    = GMAIL_USER
        msg['To']      = to_email
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#f0f4f9;padding:30px;border-radius:12px">
          <div style="background:#003B71;padding:20px;border-radius:10px 10px 0 0;text-align:center">
            <h2 style="color:#F5A800;margin:0">CodeCrafters</h2>
            <p style="color:rgba(255,255,255,.7);font-size:12px;margin:4px 0 0">DUT Student Ticketing System</p>
          </div>
          <div style="background:#fff;padding:28px;border-radius:0 0 10px 10px">
            <p style="color:#1a2035">Hi <strong>{name}</strong>,</p>
            <p style="color:#555">Use the OTP below to verify your account. It expires in <strong>10 minutes</strong>.</p>
            <div style="text-align:center;margin:28px 0">
              <span style="font-size:2.2rem;font-weight:800;letter-spacing:10px;color:#003B71;background:#eef2f8;padding:14px 24px;border-radius:10px;font-family:monospace">{otp}</span>
            </div>
            <p style="color:#888;font-size:12px">If you did not request this, please ignore this email.</p>
          </div>
        </div>"""
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(GMAIL_USER, GMAIL_PASSWORD)
            s.sendmail(GMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email OTP error: {e}")
        return False

def send_sms_otp(phone, otp):
    try:
        import urllib.request, urllib.parse
        # Ensure phone is in international format for SA numbers
        if phone.startswith('0'): phone = '+27' + phone[1:]
        elif not phone.startswith('+'): phone = '+27' + phone
        data = urllib.parse.urlencode({
            'username': AT_USERNAME,
            'to':       phone,
            'message':  f'Your CodeCrafters OTP is: {otp}. Valid for 10 minutes. Do not share this code.',
            'from':     AT_SENDER_ID
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.africastalking.com/version1/messaging',
            data=data,
            headers={'apiKey': AT_API_KEY, 'Accept': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"SMS OTP error: {e}")
        return False

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user(): return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        step  = request.form.get('step','details')

        # ── STEP 1: Collect details & send OTP ───────────────────────────────
        if step == 'details':
            name  = request.form.get('full_name','').strip()
            email = request.form.get('email','').strip().lower()
            sno   = request.form.get('student_no','').strip() or None
            phone = request.form.get('phone','').strip() or None
            pw    = request.form.get('password','')
            cpw   = request.form.get('confirm_password','')
            errs  = []
            if not name:  errs.append('Full name is required.')
            # Email domain validation
            allowed_domains = ('@gmail.com', '@dut4life.ac.za')
            if not email or '@' not in email:
                errs.append('Valid email address is required.')
            elif not any(email.endswith(d) for d in allowed_domains):
                errs.append('Email must be a @gmail.com or @dut4life.ac.za address.')
            if db.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone(): errs.append('Email already registered.')
            # Student number validation: 8 digits, starts with 2
            import re
            if sno:
                if not re.fullmatch(r'2\d{7}', sno):
                    errs.append('Student number must be exactly 8 digits and start with 2 (e.g. 21234567).')
                elif db.execute("SELECT id FROM users WHERE student_no=?",(sno,)).fetchone():
                    errs.append('Student number already registered.')
            # Password strength validation
            if len(pw) < 8:
                errs.append('Password must be at least 8 characters.')
            else:
                pw_errs = []
                if not re.search(r'[A-Z]', pw): pw_errs.append('one uppercase letter')
                if not re.search(r'[a-z]', pw): pw_errs.append('one lowercase letter')
                if not re.search(r'[0-9]', pw): pw_errs.append('one number')
                if not re.search(r'[^A-Za-z0-9]', pw): pw_errs.append('one special character')
                if pw_errs:
                    errs.append('Password must contain at least: ' + ', '.join(pw_errs) + '.')
            if pw != cpw: errs.append('Passwords do not match.')
            if not phone: errs.append('Phone number is required for OTP verification.')
            if errs:
                db.close()
                for e in errs: flash(e,'danger')
                return render_template('auth/register.html', step='details', v={'name':name,'email':email,'sno':sno or '','phone':phone or ''})
            # Generate OTP and store pending registration in session
            otp = generate_otp()
            session['pending_reg'] = {
                'name':name,'email':email,'sno':sno,'phone':phone,
                'pw_hash': generate_password_hash(pw), 'otp': otp
            }
            # Send OTP via Email and SMS
            email_ok = send_email_otp(email, otp, name)
            sms_ok   = send_sms_otp(phone, otp) if phone else False
            db.close()
            if email_ok or sms_ok:
                channels = []
                if email_ok: channels.append(f'email ({email})')
                if sms_ok:   channels.append(f'SMS ({phone})')
                flash(f'OTP sent via {" and ".join(channels)}. Enter it below to complete registration.', 'success')
            else:
                flash('Could not send OTP — check your email/SMS config. For testing, use OTP: ' + otp, 'warning')
            return render_template('auth/register.html', step='verify', v={'name':name,'email':email,'phone':phone or ''})

        # ── STEP 2: Verify OTP & create account ──────────────────────────────
        elif step == 'verify':
            entered_otp = request.form.get('otp','').strip()
            reg = session.get('pending_reg')
            if not reg:
                flash('Session expired. Please register again.','danger')
                db.close()
                return render_template('auth/register.html', step='details', v={'name':'','email':'','sno':'','phone':''})
            if entered_otp != reg['otp']:
                flash('Incorrect OTP. Please try again.','danger')
                db.close()
                return render_template('auth/register.html', step='verify', v={'name':reg['name'],'email':reg['email'],'phone':reg['phone'] or ''})
            # OTP correct — create account
            db.execute("INSERT INTO users(student_no,full_name,email,phone,password_hash,role,is_active,created_at) VALUES(?,?,?,?,?,?,1,?)",
                       (reg['sno'], reg['name'], reg['email'], reg['phone'], reg['pw_hash'], 'student', now_iso()))
            db.commit()
            uid = db.execute("SELECT id FROM users WHERE email=?",(reg['email'],)).fetchone()['id']
            session.pop('pending_reg', None)
            db.close()
            session['uid'] = uid
            notify(uid,'Welcome to CodeCrafters!','Your account is verified and ready. You can now submit support tickets.')
            flash('Account verified and created! Welcome to CodeCrafters.','success')
            return redirect(url_for('dashboard'))

        # ── Resend OTP ────────────────────────────────────────────────────────
        elif step == 'resend':
            reg = session.get('pending_reg')
            if not reg:
                flash('Session has expired. Please register again.','danger')
                db.close()
                return render_template('auth/register.html', step='details', v={'name':'','email':'','sno':'','phone':''})
            new_otp = generate_otp()
            reg['otp'] = new_otp
            session['pending_reg'] = reg
            email_ok = send_email_otp(reg['email'], new_otp, reg['name'])
            sms_ok   = send_sms_otp(reg['phone'], new_otp) if reg.get('phone') else False
            db.close()
            if email_ok or sms_ok:
                flash('A new OTP has been sent.','success')
            else:
                flash('Could not resend OTP. For testing, use OTP: ' + new_otp,'warning')
            return render_template('auth/register.html', step='verify', v={'name':reg['name'],'email':reg['email'],'phone':reg.get('phone','')})

    db.close()
    return render_template('auth/register.html', step='details', v={'name':'','email':'','sno':'','phone':''})

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.','info')
    return redirect(url_for('login'))

# ── Student ───────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    u = current_user()
    if u['role'] in ('staff','superadmin'): return redirect(url_for('admin_dashboard'))
    db = get_db()
    tickets = db.execute("""
        SELECT t.*, d.name as dept_name, a.full_name as assignee_name
        FROM tickets t JOIN departments d ON t.department_id=d.id
        LEFT JOIN users a ON t.assigned_to=a.id
        WHERE t.student_id=? ORDER BY t.created_at DESC
    """,(u['id'],)).fetchall()
    stats = {
        'total':       len(tickets),
        'pending':     sum(1 for t in tickets if t['status']=='Pending'),
        'in_progress': sum(1 for t in tickets if t['status']=='In Progress'),
        'resolved':    sum(1 for t in tickets if t['status'] in ('Resolved','Closed')),
    }
    recent_notifs = db.execute("SELECT * FROM notifications WHERE user_id=? AND is_read=0 ORDER BY created_at DESC LIMIT 5",(u['id'],)).fetchall()
    db.close()
    return render_template('student/dashboard.html', tickets=tickets, stats=stats, notifications=recent_notifs)

@app.route('/submit', methods=['GET','POST'])
@login_required
def submit_ticket():
    u = current_user()
    if u['role'] in ('staff','superadmin'): return redirect(url_for('admin_dashboard'))
    db = get_db()
    departments = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    if request.method == 'POST':
        dept_id  = request.form.get('department_id')
        subject  = request.form.get('subject','').strip()
        desc     = request.form.get('description','').strip()
        priority = 'Medium'
        is_anon  = 0
        errs = []
        if not dept_id:            errs.append('Please select a department.')
        if not subject:            errs.append('Subject is required.')
        if not desc or len(desc)<10: errs.append('Description must be at least 10 characters.')
        if errs:
            db.close()
            for e in errs: flash(e,'danger')
            return render_template('student/submit.html', departments=departments)

        tno = generate_ticket_no()
        while db.execute("SELECT id FROM tickets WHERE ticket_no=?",(tno,)).fetchone(): tno = generate_ticket_no()
        now = now_iso()
        db.execute("""INSERT INTO tickets(ticket_no,student_id,department_id,subject,description,priority,status,is_anonymous,created_at,updated_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?)""",
                   (tno, u['id'], int(dept_id), subject, desc, priority, 'Pending', is_anon, now, now))
        db.commit()
        tid = db.execute("SELECT id FROM tickets WHERE ticket_no=?",(tno,)).fetchone()['id']

        # Attachments
        for f in request.files.getlist('attachments'):
            if f and f.filename and allowed(f.filename):
                ext  = f.filename.rsplit('.',1)[1].lower()
                fname = f"{uuid.uuid4().hex}.{ext}"
                f.save(os.path.join(UPLOAD_FOLDER, fname))
                db.execute("INSERT INTO attachments(ticket_id,filename,original_name,file_size,uploaded_at) VALUES(?,?,?,?,?)",
                           (tid, fname, f.filename, os.path.getsize(os.path.join(UPLOAD_FOLDER,fname)), now_iso()))

        # Initial audit log
        db.execute("INSERT INTO ticket_updates(ticket_id,author_id,new_status,message,is_internal,created_at) VALUES(?,?,?,?,0,?)",
                   (tid, u['id'], 'Pending', 'Ticket submitted successfully.', now_iso()))
        db.commit()

        # Notify student
        notify(u['id'], 'Ticket Submitted', f'Ticket "{subject}" submitted. Ref: {tno}', tid)
        # Notify all staff in that department + superadmins
        staff = db.execute("SELECT id FROM users WHERE (department_id=? OR role='superadmin') AND is_active=1 AND role IN ('staff','superadmin')",(int(dept_id),)).fetchall()
        db.close()
        for s in staff: notify(s['id'], 'New Ticket Received', f'New {priority} ticket in your department. Ref: {tno}', tid)

        flash(f'Ticket submitted! Reference: <strong>{tno}</strong>','success')
        return redirect(url_for('view_ticket', tno=tno))
    db.close()
    return render_template('student/submit.html', departments=departments)

@app.route('/ticket/<tno>', methods=['GET','POST'])
@login_required
def view_ticket(tno):
    u = current_user()
    db = get_db()
    ticket = db.execute("""
        SELECT t.*, d.name as dept_name, s.full_name as student_name, s.email as student_email,
               s.student_no, a.full_name as assignee_name
        FROM tickets t JOIN departments d ON t.department_id=d.id
        JOIN users s ON t.student_id=s.id LEFT JOIN users a ON t.assigned_to=a.id
        WHERE t.ticket_no=?
    """,(tno,)).fetchone()
    if not ticket: db.close(); flash('Ticket not found.','danger'); return redirect(url_for('dashboard'))
    is_staff = u['role'] in ('staff','superadmin')
    if not is_staff and ticket['student_id'] != u['id']:
        db.close(); flash('Access denied.','danger'); return redirect(url_for('dashboard'))

    if request.method == 'POST':
        action  = request.form.get('action')
        message = request.form.get('message','').strip()
        now     = now_iso()
        if action == 'student_comment' and not is_staff:
            if ticket['status'] in ('Resolved','Closed'):
                flash('This ticket is already resolved. You cannot add updates.','warning')
            elif message:
                db.execute("UPDATE tickets SET updated_at=? WHERE id=?", (now, ticket['id']))
                db.execute("INSERT INTO ticket_updates(ticket_id,author_id,message,is_internal,created_at) VALUES(?,?,?,0,?)",
                           (ticket['id'], u['id'], message, now))
                db.commit()
                # Notify assigned staff if any, otherwise notify all dept staff
                if ticket['assigned_to']:
                    notify(ticket['assigned_to'], 'Student Added an Update',
                           f"Student added a comment on ticket {tno}: {message[:80]}", ticket['id'])
                else:
                    db2 = get_db()
                    dept_id = db2.execute("SELECT department_id FROM tickets WHERE id=?", (ticket['id'],)).fetchone()['department_id']
                    staff = db2.execute("SELECT id FROM users WHERE department_id=? AND role='staff' AND is_active=1", (dept_id,)).fetchall()
                    db2.close()
                    for s in staff:
                        notify(s['id'], 'Student Added an Update',
                               f"Student commented on ticket {tno}: {message[:80]}", ticket['id'])
                flash('Your update has been posted.', 'success')
            else:
                flash('Please enter a message.', 'warning')
        db.close()
        return redirect(url_for('view_ticket', tno=tno))
    q = "SELECT tu.*, u.full_name as author_name, u.role as author_role FROM ticket_updates tu JOIN users u ON tu.author_id=u.id WHERE tu.ticket_id=?"
    if not is_staff: q += " AND tu.is_internal=0"
    q += " ORDER BY tu.created_at ASC"
    updates = db.execute(q,(ticket['id'],)).fetchall()
    attachments = db.execute("SELECT * FROM attachments WHERE ticket_id=?",(ticket['id'],)).fetchall()
    db.close()
    return render_template('student/ticket_detail.html', ticket=ticket, updates=updates, attachments=attachments, is_staff=is_staff)

@app.route('/ticket/<tno>/rate', methods=['POST'])
@login_required
def rate_ticket(tno):
    u = current_user()
    db = get_db()
    ticket = db.execute("SELECT * FROM tickets WHERE ticket_no=? AND student_id=?",(tno, u['id'])).fetchone()
    if ticket and ticket['status'] in ('Resolved','Closed') and not ticket['rating']:
        rating  = request.form.get('rating','5')
        comment = request.form.get('rating_comment','').strip()
        db.execute("UPDATE tickets SET rating=?,rating_comment=? WHERE id=?",(int(rating), comment or None, ticket['id']))
        db.commit()
        flash('Thank you for your feedback!','success')
    db.close()
    return redirect(url_for('view_ticket', tno=tno))

@app.route('/my-tickets')
@login_required
def my_tickets():
    u = current_user()
    if u['role'] in ('staff','superadmin'): return redirect(url_for('admin_dashboard'))
    db = get_db()
    status = request.args.get('status','')
    dept   = request.args.get('dept','')
    q      = request.args.get('q','')
    sql = "SELECT t.*, d.name as dept_name FROM tickets t JOIN departments d ON t.department_id=d.id WHERE t.student_id=?"
    params = [u['id']]
    if status: sql += " AND t.status=?"; params.append(status)
    if dept:   sql += " AND t.department_id=?"; params.append(int(dept))
    if q:      sql += " AND (t.subject LIKE ? OR t.ticket_no LIKE ?)"; params += [f'%{q}%',f'%{q}%']
    sql += " ORDER BY t.created_at DESC"
    tickets = db.execute(sql, params).fetchall()
    departments = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    db.close()
    return render_template('student/my_tickets.html', tickets=tickets, departments=departments,
                           status=status, dept=dept, q=q)

@app.route('/notifications/read/<int:nid>')
@login_required
def mark_read(nid):
    u = current_user()
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",(nid,u['id']))
    db.commit(); db.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/notifications/read-all')
@login_required
def mark_all_read():
    u = current_user()
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(u['id'],))
    db.commit(); db.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    u = current_user()
    db = get_db()
    if request.method == 'POST':
        name  = request.form.get('full_name','').strip()
        phone = request.form.get('phone','').strip() or None
        npw   = request.form.get('new_password','')
        cpw   = request.form.get('confirm_password','')
        if npw:
            if len(npw)<8: flash('Password must be at least 8 characters.','danger'); db.close(); return redirect(url_for('profile'))
            if npw!=cpw:   flash('Passwords do not match.','danger'); db.close(); return redirect(url_for('profile'))
            db.execute("UPDATE users SET full_name=?,phone=?,password_hash=? WHERE id=?",(name,phone,generate_password_hash(npw),u['id']))
        else:
            db.execute("UPDATE users SET full_name=?,phone=? WHERE id=?",(name,phone,u['id']))
        db.commit(); db.close()
        flash('Profile updated.','success')
        return redirect(url_for('profile'))
    total = db.execute("SELECT COUNT(*) FROM tickets WHERE student_id=?",(u['id'],)).fetchone()[0]
    db.close()
    return render_template('student/profile.html', u=u, total_tickets=total)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ── Admin / Staff ─────────────────────────────────────────────────────────────
@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
@staff_required
def admin_dashboard():
    u = current_user()
    db = get_db()
    stats = {
        'total':       db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0],
        'pending':     db.execute("SELECT COUNT(*) FROM tickets WHERE status='Pending'").fetchone()[0],
        'in_progress': db.execute("SELECT COUNT(*) FROM tickets WHERE status='In Progress'").fetchone()[0],
        'resolved':    db.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved','Closed')").fetchone()[0],
        'urgent':      db.execute("SELECT COUNT(*) FROM tickets WHERE priority='Urgent'").fetchone()[0],
    }
    # Dept filter for staff
    dept_filter = ""
    params = []
    if u['role'] == 'staff' and u['department_id']:
        dept_filter = " WHERE t.department_id=?"; params = [u['department_id']]

    recent = db.execute(f"""SELECT t.*, d.name as dept_name, s.full_name as student_name,
                                   a.full_name as assignee_name
                            FROM tickets t JOIN departments d ON t.department_id=d.id
                            JOIN users s ON t.student_id=s.id LEFT JOIN users a ON t.assigned_to=a.id
                            {dept_filter}
                            ORDER BY t.created_at DESC LIMIT 10""", params).fetchall()

    dept_stats = db.execute("""SELECT d.name, COUNT(t.id) as cnt FROM departments d
                               LEFT JOIN tickets t ON t.department_id=d.id
                               GROUP BY d.id ORDER BY cnt DESC""").fetchall()
    db.close()
    return render_template('admin/dashboard.html', stats=stats, recent=recent, dept_stats=dept_stats)

@app.route('/admin/tickets')
@login_required
@staff_required
def admin_tickets():
    u = current_user()
    db = get_db()
    status   = request.args.get('status','')
    priority = request.args.get('priority','')
    dept_id  = request.args.get('dept','')
    assigned = request.args.get('assigned','')
    q        = request.args.get('q','')

    sql = """SELECT t.*, d.name as dept_name, s.full_name as student_name,
                    s.student_no, a.full_name as assignee_name
             FROM tickets t JOIN departments d ON t.department_id=d.id
             JOIN users s ON t.student_id=s.id LEFT JOIN users a ON t.assigned_to=a.id
             WHERE 1=1"""
    params = []
    # Staff only see their dept
    if u['role'] == 'staff' and u['department_id']:
        sql += " AND t.department_id=?"; params.append(u['department_id'])
    if status:   sql += " AND t.status=?";       params.append(status)
    if priority: sql += " AND t.priority=?";     params.append(priority)
    if dept_id and u['role']=='superadmin': sql += " AND t.department_id=?"; params.append(int(dept_id))
    if assigned == 'me':           sql += " AND t.assigned_to=?";  params.append(u['id'])
    elif assigned == 'unassigned': sql += " AND t.assigned_to IS NULL"
    if q: sql += " AND (t.subject LIKE ? OR t.ticket_no LIKE ? OR s.full_name LIKE ?)"; params += [f'%{q}%']*3
    sql += """ ORDER BY
      CASE WHEN t.status IN ('Resolved','Closed') THEN 1 ELSE 0 END,
      CASE WHEN ? = 'priority'
        THEN CASE t.priority WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END
        ELSE 0
      END,
      t.created_at ASC"""
    params.append(request.args.get('sort','fcfs'))

    tickets = db.execute(sql, params).fetchall()
    departments = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    db.close()
    return render_template('admin/tickets.html', tickets=tickets, departments=departments,
                           status=status, priority=priority, dept_id=dept_id, assigned=assigned, q=q,
                           sort=request.args.get('sort','fcfs'))

@app.route('/admin/ticket/<tno>', methods=['GET','POST'])
@login_required
@staff_required
def admin_view_ticket(tno):
    u = current_user()
    db = get_db()
    ticket = db.execute("""
        SELECT t.*, d.name as dept_name, d.id as dept_id,
               s.full_name as student_name, s.email as student_email, s.student_no, s.phone as student_phone,
               a.full_name as assignee_name
        FROM tickets t JOIN departments d ON t.department_id=d.id
        JOIN users s ON t.student_id=s.id LEFT JOIN users a ON t.assigned_to=a.id
        WHERE t.ticket_no=?
    """,(tno,)).fetchone()
    if not ticket: db.close(); flash('Ticket not found.','danger'); return redirect(url_for('admin_tickets'))

    if request.method == 'POST':
        action      = request.form.get('action')
        message     = request.form.get('message','').strip()
        is_internal = 1 if request.form.get('is_internal')=='on' else 0
        now = now_iso()

        if action == 'assign':
            aid = request.form.get('staff_id') or None
            db.execute("UPDATE tickets SET assigned_to=?,status=?,updated_at=? WHERE id=?",
                       (aid, 'Assigned' if aid else 'Pending', now, ticket['id']))
            if aid:
                aname = db.execute("SELECT full_name FROM users WHERE id=?",(int(aid),)).fetchone()['full_name']
                db.execute("INSERT INTO ticket_updates(ticket_id,author_id,message,is_internal,created_at) VALUES(?,?,?,1,?)",
                           (ticket['id'],u['id'],f"Ticket assigned to {aname}",now))
                db.commit()
                # Notify the assigned staff member
                notify(int(aid), f"Ticket Assigned to You",
                       f"Ticket {tno} ({ticket['subject'][:40]}) has been assigned to you.", ticket['id'])
                # Notify the student
                notify(ticket['student_id'], 'Your Ticket Has Been Assigned',
                       f"Ticket {tno} has been assigned to {aname} and is being handled.", ticket['id'])
                flash(f'Ticket assigned to {aname}.','success')
            else:
                db.execute("INSERT INTO ticket_updates(ticket_id,author_id,message,is_internal,created_at) VALUES(?,?,?,1,?)",
                           (ticket['id'],u['id'],"Ticket unassigned",now))
                db.commit()
                flash('Ticket unassigned.','warning')

        elif action == 'comment':
            if message:
                db.execute("INSERT INTO ticket_updates(ticket_id,author_id,message,is_internal,created_at) VALUES(?,?,?,?,?)",
                           (ticket['id'],u['id'],message,is_internal,now))
                db.commit()
                if not is_internal:
                    notify(ticket['student_id'],'New Update on Your Ticket',
                           f"Staff added a comment to ticket {tno}.",ticket['id'])
                flash('Comment added.','success')

        elif action == 'reopen':
            db.execute("UPDATE tickets SET status='In Progress',resolved_at=NULL,updated_at=? WHERE id=?",
                       (now, ticket['id']))
            db.execute("INSERT INTO ticket_updates(ticket_id,author_id,old_status,new_status,message,is_internal,created_at) VALUES(?,?,?,?,?,0,?)",
                       (ticket['id'], u['id'], ticket['status'], 'In Progress',
                        f"Ticket reopened by {u['full_name']} — student was not satisfied with the resolution.", now))
            db.commit()
            notify(ticket['student_id'], 'Your Ticket Has Been Reopened',
                   f"Ticket {tno} has been reopened and is being worked on again.", ticket['id'])
            if ticket['assigned_to']:
                notify(ticket['assigned_to'], 'Ticket Reopened',
                       f"Ticket {tno} has been reopened. Please follow up with the student.", ticket['id'])
            flash('Ticket reopened and set back to In Progress.', 'success')

        elif action == 'change_priority':
            new_priority = request.form.get('new_priority')
            old_priority = ticket['priority']
            valid_priorities = ('Low', 'Medium', 'High', 'Urgent')
            if new_priority in valid_priorities and new_priority != old_priority:
                db.execute("UPDATE tickets SET priority=?,updated_at=? WHERE id=?",
                           (new_priority, now, ticket['id']))
                db.execute("INSERT INTO ticket_updates(ticket_id,author_id,message,is_internal,created_at) VALUES(?,?,?,1,?)",
                           (ticket['id'], u['id'],
                            f"Priority changed from {old_priority} to {new_priority} by {u['full_name']}.", now))
                db.commit()
                notify(ticket['student_id'], 'Ticket Priority Updated',
                       f"Ticket {tno} priority has been updated to {new_priority}.", ticket['id'])
                if ticket['assigned_to']:
                    notify(ticket['assigned_to'], 'Ticket Priority Changed',
                           f"Ticket {tno} priority changed to {new_priority}. Please adjust accordingly.", ticket['id'])
                flash(f'Priority updated to {new_priority}.', 'success')
            else:
                flash('No priority change made.', 'info')

        db.close()
        return redirect(url_for('admin_view_ticket', tno=tno))

    staff_list = db.execute("SELECT * FROM users WHERE department_id=? AND is_active=1 AND role='staff'",(ticket['dept_id'],)).fetchall()
    updates    = db.execute("""SELECT tu.*, u.full_name as author_name, u.role as author_role
                               FROM ticket_updates tu JOIN users u ON tu.author_id=u.id
                               WHERE tu.ticket_id=? ORDER BY tu.created_at ASC""",(ticket['id'],)).fetchall()
    attachments = db.execute("SELECT * FROM attachments WHERE ticket_id=?",(ticket['id'],)).fetchall()
    db.close()
    return render_template('admin/ticket_detail.html', ticket=ticket, staff_list=staff_list,
                           updates=updates, attachments=attachments)

@app.route('/admin/users')
@login_required
@staff_required
def admin_users():
    db = get_db()
    role  = request.args.get('role','')
    q     = request.args.get('q','')
    sql   = "SELECT u.*, d.name as dept_name, (SELECT COUNT(*) FROM tickets WHERE student_id=u.id) as ticket_count FROM users u LEFT JOIN departments d ON u.department_id=d.id WHERE 1=1"
    params = []
    if role: sql += " AND u.role=?"; params.append(role)
    if q:    sql += " AND (u.full_name LIKE ? OR u.email LIKE ?)"; params += [f'%{q}%']*2
    sql += " ORDER BY u.created_at DESC"
    users = db.execute(sql, params).fetchall()
    departments = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    db.close()
    return render_template('admin/users.html', users=users, departments=departments, role=role, q=q)

@app.route('/admin/users/add', methods=['GET','POST'])
@login_required
@staff_required
def add_user():
    u = current_user()
    db = get_db()
    # Attach staff counts to each dept
    depts_raw = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    departments = []
    for d in depts_raw:
        cnt = db.execute("SELECT COUNT(*) FROM users WHERE department_id=? AND role='staff' AND is_active=1",(d['id'],)).fetchone()[0]
        departments.append({'id':d['id'],'name':d['name'],'email':d['email'],'staff_count':cnt})

    if request.method == 'POST':
        name    = request.form.get('full_name','').strip()
        role    = request.form.get('role','student')
        dept_id = request.form.get('department_id') or None
        pw      = request.form.get('password','') or 'Staff@2026'

        if u['role'] != 'superadmin' and role in ('staff','superadmin'):
            flash('Only Super Admins can create staff accounts.','danger'); db.close(); return redirect(url_for('admin_users'))

        # Auto-generate email for staff: firstname.lastname@dut.ac.za
        if role == 'staff' and name:
            parts = name.lower().split()
            # Strip titles
            titles = {'dr','prof','mr','mrs','ms','miss'}
            parts  = [p for p in parts if p not in titles]
            if len(parts) >= 2:
                email = f"{parts[0]}.{parts[-1]}@dut.ac.za"
            else:
                email = f"{parts[0]}@dut.ac.za"
        else:
            email = request.form.get('email','').strip().lower()

        # Enforce max 3 staff per department
        if role == 'staff' and dept_id:
            staff_count = db.execute("SELECT COUNT(*) FROM users WHERE department_id=? AND role='staff' AND is_active=1",(dept_id,)).fetchone()[0]
            if staff_count >= 3:
                dept_name = db.execute("SELECT name FROM departments WHERE id=?",(dept_id,)).fetchone()['name']
                flash(f'{dept_name} already has the maximum of 3 technicians. Remove one before adding another.','danger')
                db.close(); return redirect(url_for('add_user'))

        if db.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone():
            flash(f'Email {email} already exists. Try a different name or adjust manually.','danger'); db.close(); return redirect(url_for('add_user'))

        db.execute("INSERT INTO users(full_name,email,password_hash,role,department_id,is_active,created_at) VALUES(?,?,?,?,?,1,?)",
                   (name, email, generate_password_hash(pw), role, dept_id, now_iso()))
        db.commit(); db.close()
        flash(f'Technician {name} created with login: {email} / {pw}','success')
        return redirect(url_for('admin_users'))
    db.close()
    return render_template('admin/add_user.html', departments=departments)


@app.route('/admin/users/<int:uid>/reset-password', methods=['POST'])
@login_required
@superadmin_required
def reset_password(uid):
    new_pw = request.form.get('new_password','').strip()
    if len(new_pw) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('admin_users'))
    db = get_db()
    user = db.execute("SELECT full_name, role FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        db.close(); flash('User not found.', 'danger'); return redirect(url_for('admin_users'))
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_pw), uid))
    db.commit(); db.close()
    flash(f"Password updated for {user['full_name']}.", 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:uid>/toggle')
@login_required
@staff_required
def toggle_user(uid):
    u = current_user()
    if uid == u['id']: flash("You can't deactivate yourself.",'warning'); return redirect(url_for('admin_users'))
    db = get_db()
    cur = db.execute("SELECT is_active FROM users WHERE id=?",(uid,)).fetchone()['is_active']
    db.execute("UPDATE users SET is_active=? WHERE id=?",(0 if cur else 1, uid))
    db.commit(); db.close()
    flash(f'User {"deactivated" if cur else "activated"}.','success')
    return redirect(url_for('admin_users'))

@app.route('/admin/departments', methods=['GET','POST'])
@login_required
@superadmin_required
def admin_departments():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action','add_dept')
        if action == 'add_dept':
            name  = request.form.get('name','').strip()
            email = request.form.get('email','').strip()
            head  = request.form.get('head','').strip()
            if name:
                if db.execute("SELECT id FROM departments WHERE name=?",(name,)).fetchone():
                    flash('Department already exists.','warning')
                else:
                    db.execute("INSERT INTO departments(name,email,head) VALUES(?,?,?)",(name,email,head))
                    db.commit(); flash('Department added.','success')
        elif action == 'assign_staff':
            uid     = request.form.get('user_id')
            dept_id = request.form.get('dept_id')
            if uid and dept_id:
                staff_count = db.execute("SELECT COUNT(*) FROM users WHERE department_id=? AND role='staff' AND is_active=1",(dept_id,)).fetchone()[0]
                if staff_count >= 3:
                    dept_name = db.execute("SELECT name FROM departments WHERE id=?",(dept_id,)).fetchone()['name']
                    flash(f'{dept_name} already has 3 technicians (maximum). Remove one first.','danger')
                else:
                    db.execute("UPDATE users SET department_id=? WHERE id=? AND role='staff'",(dept_id,uid))
                    db.commit(); flash('Technician assigned to department.','success')
        elif action == 'remove_staff':
            uid = request.form.get('user_id')
            if uid:
                db.execute("UPDATE users SET department_id=NULL WHERE id=?",(uid,))
                db.commit(); flash('Staff member removed from department.','success')
        db.close(); return redirect(url_for('admin_departments'))
    depts = db.execute("SELECT d.*,(SELECT COUNT(*) FROM tickets WHERE department_id=d.id) as cnt FROM departments d ORDER BY d.name").fetchall()
    # Fetch staff per department
    dept_staff = {}
    for d in depts:
        staff = db.execute("SELECT id,full_name,email FROM users WHERE department_id=? AND role='staff' AND is_active=1 ORDER BY full_name",(d['id'],)).fetchall()
        dept_staff[d['id']] = staff
    # Unassigned staff (no department)
    unassigned_staff = db.execute("SELECT id,full_name,email FROM users WHERE role='staff' AND (department_id IS NULL) AND is_active=1 ORDER BY full_name").fetchall()
    db.close()
    return render_template('admin/departments.html', departments=depts, dept_staff=dept_staff, unassigned_staff=unassigned_staff)


# ── Staff Dashboard & Task Routes ─────────────────────────────────────────────

@app.route('/staff/dashboard')
@login_required
def staff_dashboard():
    u = current_user()
    if u['role'] not in ('staff','superadmin'):
        return redirect(url_for('dashboard'))
    db = get_db()
    # Tickets assigned to this staff member
    my_tasks = db.execute("""
        SELECT t.*, d.name as dept_name, s.full_name as student_name, s.student_no
        FROM tickets t JOIN departments d ON t.department_id=d.id
        JOIN users s ON t.student_id=s.id
        WHERE t.assigned_to=? ORDER BY
        CASE t.priority WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END,
        t.created_at DESC
    """, (u['id'],)).fetchall()
    # Unassigned tickets in my department
    dept_queue = db.execute("""
        SELECT t.*, d.name as dept_name, s.full_name as student_name, s.student_no
        FROM tickets t JOIN departments d ON t.department_id=d.id
        JOIN users s ON t.student_id=s.id
        WHERE t.department_id=? AND t.assigned_to IS NULL AND t.status NOT IN ('Resolved','Closed')
        ORDER BY CASE t.priority WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END,
        t.created_at ASC
    """, (u['department_id'],)).fetchall() if u['department_id'] else []
    # Stats for this staff member
    stats = {
        'total':    db.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to=?", (u['id'],)).fetchone()[0],
        'active':   db.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to=? AND status='In Progress'", (u['id'],)).fetchone()[0],
        'resolved': db.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to=? AND status IN ('Resolved','Closed')", (u['id'],)).fetchone()[0],
        'pending':  db.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to=? AND status IN ('Pending','Assigned')", (u['id'],)).fetchone()[0],
    }
    notifications = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (u['id'],)).fetchall()
    unread = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (u['id'],)).fetchone()[0]
    db.close()
    return render_template('staff/dashboard.html', my_tasks=my_tasks, dept_queue=dept_queue,
                           stats=stats, notifications=notifications, unread=unread)

@app.route('/staff/ticket/<tno>', methods=['GET','POST'])
@login_required
def staff_ticket(tno):
    u = current_user()
    if u['role'] not in ('staff','superadmin'):
        return redirect(url_for('dashboard'))
    db = get_db()
    ticket = db.execute("""
        SELECT t.*, d.name as dept_name, d.id as dept_id,
               s.full_name as student_name, s.email as student_email,
               s.student_no, s.phone as student_phone,
               a.full_name as assignee_name
        FROM tickets t JOIN departments d ON t.department_id=d.id
        JOIN users s ON t.student_id=s.id LEFT JOIN users a ON t.assigned_to=a.id
        WHERE t.ticket_no=?
    """, (tno,)).fetchone()
    if not ticket:
        db.close(); flash('Ticket not found.','danger')
        return redirect(url_for('staff_dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')
        now = now_iso()

        if action == 'accept':
            # Staff accepts the task — sets status to In Progress
            db.execute("UPDATE tickets SET assigned_to=?,status='In Progress',updated_at=? WHERE id=?",
                       (u['id'], now, ticket['id']))
            db.execute("INSERT INTO ticket_updates(ticket_id,author_id,message,is_internal,created_at) VALUES(?,?,?,0,?)",
                       (ticket['id'], u['id'], f"{u['full_name']} accepted this ticket and is now working on it.", now))
            db.commit()
            notify(ticket['student_id'], 'Your Ticket is Being Handled',
                   f"Good news! {u['full_name']} has accepted ticket {tno} and is working on it.", ticket['id'])
            flash('Task accepted! Status set to In Progress.','success')

        elif action == 'update':
            message     = request.form.get('message','').strip()
            is_internal = 1 if request.form.get('is_internal') == 'on' else 0
            if message:
                db.execute("UPDATE tickets SET updated_at=? WHERE id=?", (now, ticket['id']))
                db.execute("INSERT INTO ticket_updates(ticket_id,author_id,message,is_internal,created_at) VALUES(?,?,?,?,?)",
                           (ticket['id'], u['id'], message, is_internal, now))
                db.commit()
                if not is_internal:
                    notify(ticket['student_id'], 'Update on Your Ticket',
                           f"{u['full_name']} added an update to ticket {tno}: {message[:80]}", ticket['id'])
                flash('Update posted successfully.','success')
            else:
                flash('Please enter a message.','warning')

        elif action == 'resolve':
            message = request.form.get('message','').strip()
            if not message:
                flash('Please provide a resolution summary.','warning')
            elif ticket['status'] != 'In Progress':
                flash('Only In Progress tickets can be resolved.','warning')
            else:
                db.execute("UPDATE tickets SET status='Resolved',resolved_at=?,updated_at=? WHERE id=?",
                           (now, now, ticket['id']))
                db.execute("INSERT INTO ticket_updates(ticket_id,author_id,old_status,new_status,message,is_internal,created_at) VALUES(?,?,?,?,?,0,?)",
                           (ticket['id'], u['id'], 'In Progress', 'Resolved', message, now))
                db.commit()
                notify(ticket['student_id'], 'Your Ticket Has Been Resolved',
                       f"Great news! {u['full_name']} has resolved ticket {tno}. Please rate your experience.", ticket['id'])
                flash('Ticket marked as resolved. Student has been notified.','success')

        db.close()
        return redirect(url_for('staff_ticket', tno=tno))

    updates = db.execute("""SELECT tu.*, u.full_name as author_name, u.role as author_role
                            FROM ticket_updates tu JOIN users u ON tu.author_id=u.id
                            WHERE tu.ticket_id=? ORDER BY tu.created_at ASC""", (ticket['id'],)).fetchall()
    attachments = db.execute("SELECT * FROM attachments WHERE ticket_id=?", (ticket['id'],)).fetchall()
    db.close()
    return render_template('staff/ticket.html', ticket=ticket, updates=updates, attachments=attachments)

@app.route('/staff/ticket/<tno>/updates')
@login_required
def staff_ticket_updates(tno):
    """API endpoint for real-time polling of ticket updates"""
    u = current_user()
    if u['role'] not in ('staff','superadmin','student'):
        return jsonify([])
    db = get_db()
    ticket = db.execute("SELECT id,student_id FROM tickets WHERE ticket_no=?", (tno,)).fetchone()
    if not ticket:
        db.close(); return jsonify([])
    updates = db.execute("""SELECT tu.id, tu.message, tu.is_internal, tu.old_status, tu.new_status,
                                   tu.created_at, u.full_name as author_name, u.role as author_role
                            FROM ticket_updates tu JOIN users u ON tu.author_id=u.id
                            WHERE tu.ticket_id=? ORDER BY tu.created_at DESC LIMIT 20""", (ticket['id'],)).fetchall()
    ticket_status = db.execute("SELECT status FROM tickets WHERE id=?", (ticket['id'],)).fetchone()['status']
    db.close()
    return jsonify({
        'updates': [dict(r) for r in updates],
        'status': ticket_status
    })

@app.route('/admin/reports')
@login_required
@staff_required
def admin_reports():
    db = get_db()
    total    = db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    resolved = db.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved','Closed')").fetchone()[0]
    pending  = db.execute("SELECT COUNT(*) FROM tickets WHERE status='Pending'").fetchone()[0]
    in_prog  = db.execute("SELECT COUNT(*) FROM tickets WHERE status='In Progress'").fetchone()[0]
    dept_stats = db.execute("""SELECT d.name, COUNT(t.id) as cnt FROM departments d
                               LEFT JOIN tickets t ON t.department_id=d.id
                               GROUP BY d.name HAVING cnt>0 ORDER BY cnt DESC""").fetchall()
    prio_stats = db.execute("SELECT priority, COUNT(*) as cnt FROM tickets GROUP BY priority ORDER BY cnt DESC").fetchall()
    avg_rating = db.execute("SELECT ROUND(AVG(rating),1) as avg FROM tickets WHERE rating IS NOT NULL").fetchone()['avg']
    db.close()
    return render_template('admin/reports.html', total=total, resolved=resolved,
                           pending=pending, in_prog=in_prog, dept_stats=dept_stats,
                           prio_stats=prio_stats, avg_rating=avg_rating or 'N/A')

@app.route('/admin/api/stats')
@login_required
@staff_required
def api_stats():
    db = get_db()
    data = {
        'total':    db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0],
        'pending':  db.execute("SELECT COUNT(*) FROM tickets WHERE status='Pending'").fetchone()[0],
        'resolved': db.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved','Closed')").fetchone()[0],
    }
    db.close()
    return jsonify(data)


@app.route('/admin/reports/weekly')
@login_required
@superadmin_required
def weekly_report_page():
    """Page to select week and preview report stats before downloading."""
    db = get_db()
    # Get available weeks that have resolved tickets
    weeks_data = []
    for offset in range(0, -8, -1):
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        sow = now - timedelta(days=now.weekday()) + timedelta(weeks=offset)
        sow = sow.replace(hour=0, minute=0, second=0, microsecond=0)
        eow = sow + timedelta(days=6, hours=23, minutes=59, seconds=59)
        cnt = db.execute("SELECT COUNT(*) FROM tickets WHERE resolved_at BETWEEN ? AND ?",
                         (sow.strftime('%Y-%m-%d %H:%M:%S'), eow.strftime('%Y-%m-%d %H:%M:%S'))).fetchone()[0]
        opened = db.execute("SELECT COUNT(*) FROM tickets WHERE created_at BETWEEN ? AND ?",
                            (sow.strftime('%Y-%m-%d %H:%M:%S'), eow.strftime('%Y-%m-%d %H:%M:%S'))).fetchone()[0]
        weeks_data.append({
            'offset':  offset,
            'label':   f"{sow.strftime('%d %b')} – {eow.strftime('%d %b %Y')}",
            'resolved': cnt,
            'opened':   opened,
            'is_current': offset == 0,
        })
    db.close()
    return render_template('admin/weekly_report.html', weeks=weeks_data)

@app.route('/admin/reports/weekly/download')
@login_required
@superadmin_required
def download_weekly_report():
    """Generate and stream the PDF report."""
    import io
    week_offset = int(request.args.get('week', 0))
    db = get_db()
    try:
        pdf_bytes, week_label = generate_weekly_report(db, week_offset)
        db.close()
        safe_label = week_label.replace(' ', '_').replace('–', '-').replace('/', '-')
        filename   = f"DUT_Weekly_Report_{safe_label}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        db.close()
        flash(f'Error generating report: {str(e)}', 'danger')
        return redirect(url_for('weekly_report_page'))

# ── Boot ──────────────────────────────────────────────────────────────────────
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
