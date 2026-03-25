"""
CodeCrafters DUT — Weekly PDF Report Generator
Uses ReportLab to produce a professional multi-page report.
"""
import io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak, KeepTogether)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF

# ── Colours ───────────────────────────────────────────────────────────────────
NAVY    = colors.HexColor('#003B71')
GOLD    = colors.HexColor('#F5A800')
LGREY   = colors.HexColor('#f5f7fa')
DGREY   = colors.HexColor('#555555')
GREEN   = colors.HexColor('#2e7d32')
RED     = colors.HexColor('#c0392b')
ORANGE  = colors.HexColor('#e65100')
BORDER  = colors.HexColor('#dde1e7')
WHITE   = colors.white
BLACK   = colors.black

W, H = A4  # 210 x 297 mm

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    ss = getSampleStyleSheet()
    def s(name, **kw):
        return ParagraphStyle(name, **kw)
    return {
        'h1':      s('H1',      fontName='Helvetica-Bold',   fontSize=20, textColor=NAVY,  spaceAfter=4),
        'h2':      s('H2',      fontName='Helvetica-Bold',   fontSize=13, textColor=NAVY,  spaceBefore=14, spaceAfter=4),
        'h3':      s('H3',      fontName='Helvetica-Bold',   fontSize=10, textColor=NAVY,  spaceBefore=8,  spaceAfter=3),
        'body':    s('Body',    fontName='Helvetica',         fontSize=9,  textColor=DGREY, leading=14),
        'small':   s('Small',   fontName='Helvetica',         fontSize=7.5,textColor=DGREY, leading=11),
        'bold':    s('Bold',    fontName='Helvetica-Bold',    fontSize=9,  textColor=BLACK),
        'center':  s('Center',  fontName='Helvetica',         fontSize=9,  alignment=TA_CENTER, textColor=DGREY),
        'gold':    s('Gold',    fontName='Helvetica-Bold',    fontSize=9,  textColor=colors.HexColor('#9a6200')),
        'green':   s('Green',   fontName='Helvetica-Bold',    fontSize=9,  textColor=GREEN),
        'red':     s('Red',     fontName='Helvetica-Bold',    fontSize=9,  textColor=RED),
        'muted':   s('Muted',   fontName='Helvetica-Oblique', fontSize=8,  textColor=colors.HexColor('#888888')),
        'quote':   s('Quote',   fontName='Helvetica-Oblique', fontSize=8.5,textColor=DGREY, leftIndent=12, rightIndent=12, leading=13),
        'tno':     s('Tno',     fontName='Courier-Bold',      fontSize=8,  textColor=NAVY),
    }

def stars(n, total=5):
    filled = '★' * int(n) + '☆' * (total - int(n))
    return filled

def resolve_time(created_at, resolved_at):
    if not resolved_at:
        return 'Unresolved'
    try:
        fmt = '%Y-%m-%d %H:%M:%S'
        c = datetime.strptime(created_at[:19], fmt)
        r = datetime.strptime(resolved_at[:19], fmt)
        delta = r - c
        hours = int(delta.total_seconds() // 3600)
        mins  = int((delta.total_seconds() % 3600) // 60)
        if hours >= 24:
            days = hours // 24
            rem  = hours % 24
            return f'{days}d {rem}h'
        return f'{hours}h {mins}m'
    except:
        return 'N/A'

def priority_color(p):
    return {
        'Urgent': RED,
        'High':   ORANGE,
        'Medium': GOLD,
        'Low':    GREEN,
    }.get(p, DGREY)

# ── Header / Footer ───────────────────────────────────────────────────────────
class ReportTemplate(SimpleDocTemplate):
    def __init__(self, buf, week_label, generated_at):
        super().__init__(buf, pagesize=A4,
                         leftMargin=18*mm, rightMargin=18*mm,
                         topMargin=28*mm, bottomMargin=22*mm)
        self.week_label    = week_label
        self.generated_at  = generated_at

    def afterPage(self):
        pass

    def handle_pageBegin(self):
        super().handle_pageBegin()
        c = self.canv
        # Top header bar
        c.setFillColor(NAVY)
        c.rect(0, H - 20*mm, W, 20*mm, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(0, H - 21.5*mm, W, 1.5*mm, fill=1, stroke=0)
        # Header text
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 11)
        c.drawString(18*mm, H - 12*mm, 'CodeCrafters — DUT Student Ticketing System')
        c.setFont('Helvetica', 8)
        c.drawRightString(W - 18*mm, H - 12*mm, f'Weekly Report  |  {self.week_label}')
        # Footer
        c.setFillColor(BORDER)
        c.rect(0, 0, W, 14*mm, fill=1, stroke=0)
        c.setFillColor(DGREY)
        c.setFont('Helvetica', 7.5)
        c.drawString(18*mm, 5*mm, f'Generated: {self.generated_at}  |  CONFIDENTIAL — For internal use only')
        c.drawRightString(W - 18*mm, 5*mm, f'Page {self.page}')

# ── Stat Box Row ──────────────────────────────────────────────────────────────
def stat_box_table(items):
    """items = [(label, value, color), ...]"""
    cell_data = []
    cell_styles = []
    for i, (label, val, col) in enumerate(items):
        box = Table([[Paragraph(str(val), ParagraphStyle('SBV', fontName='Helvetica-Bold', fontSize=22, textColor=col, alignment=TA_CENTER))],
                     [Paragraph(label,    ParagraphStyle('SBL', fontName='Helvetica',      fontSize=8,  textColor=DGREY,alignment=TA_CENTER))]],
                    colWidths=[None])
        box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), LGREY),
            ('BOX',        (0,0), (-1,-1), 0.5, BORDER),
            ('ROUNDEDCORNERS', [6]),
            ('TOPPADDING',  (0,0),(-1,-1), 8),
            ('BOTTOMPADDING',(0,0),(-1,-1), 8),
            ('ALIGN',      (0,0),(-1,-1),'CENTER'),
        ]))
        cell_data.append(box)

    col_w = (W - 36*mm) / len(items)
    t = Table([cell_data], colWidths=[col_w]*len(items))
    t.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), 4),
        ('RIGHTPADDING', (0,0),(-1,-1), 4),
        ('VALIGN',       (0,0),(-1,-1),'TOP'),
    ]))
    return t

# ── Section Divider ───────────────────────────────────────────────────────────
def section_header(title, styles):
    d = Drawing(W - 36*mm, 14)
    d.add(Rect(0, 0, W-36*mm, 14, fillColor=NAVY, strokeColor=None))
    d.add(String(8, 3, title, fontName='Helvetica-Bold', fontSize=10, fillColor=WHITE))
    return d

# ── Bar Chart ─────────────────────────────────────────────────────────────────
def dept_bar_chart(dept_data, width=160*mm, height=55*mm):
    if not dept_data:
        return None
    labels = [d['name'][:12] for d in dept_data]
    values = [d['cnt'] for d in dept_data]
    drawing = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x        = 40
    bc.y        = 20
    bc.width    = width - 60
    bc.height   = height - 35
    bc.data     = [values]
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.labels.fontSize  = 7
    bc.categoryAxis.labels.angle     = 25
    bc.categoryAxis.labels.dy        = -6
    bc.bars[0].fillColor             = NAVY
    bc.valueAxis.valueMin            = 0
    bc.valueAxis.labels.fontSize     = 7
    bc.groupSpacing = 5
    drawing.add(bc)
    return drawing

# ── Pie Chart ─────────────────────────────────────────────────────────────────
def priority_pie(prio_data, size=80):
    if not prio_data:
        return None
    pcolors = {'Urgent': RED, 'High': ORANGE, 'Medium': GOLD, 'Low': GREEN}
    labels = [d['priority'] for d in prio_data]
    values = [d['cnt'] for d in prio_data]
    drawing = Drawing(size + 80, size + 20)
    pie = Pie()
    pie.x       = 5
    pie.y       = 10
    pie.width   = size
    pie.height  = size
    pie.data    = values
    pie.labels  = [f'{l} ({v})' for l, v in zip(labels, values)]
    pie.sideLabels = 1
    pie.sideLabelsOffset = 0.05
    for i, lbl in enumerate(labels):
        pie.slices[i].fillColor = pcolors.get(lbl, DGREY)
        pie.slices[i].strokeColor = WHITE
        pie.slices[i].strokeWidth = 1
    drawing.add(pie)
    return drawing

# ── Main Generator ────────────────────────────────────────────────────────────
def generate_weekly_report(db, week_offset=0):
    """
    week_offset: 0 = current week, -1 = last week, etc.
    Returns bytes of the PDF.
    """
    now   = datetime.utcnow()
    # Week boundaries (Mon–Sun)
    start_of_week = now - timedelta(days=now.weekday()) + timedelta(weeks=week_offset)
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week   = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    week_label    = f"{start_of_week.strftime('%d %b')} – {end_of_week.strftime('%d %b %Y')}"
    generated_at  = now.strftime('%d %b %Y, %H:%M UTC')
    w_start_str   = start_of_week.strftime('%Y-%m-%d %H:%M:%S')
    w_end_str     = end_of_week.strftime('%Y-%m-%d %H:%M:%S')

    styles = make_styles()

    # ── Fetch data ─────────────────────────────────────────────────────────────
    # Resolved tickets this week (main table)
    resolved_tickets = db.execute("""
        SELECT t.ticket_no, t.subject, t.priority, t.created_at, t.resolved_at,
               t.rating, t.rating_comment, t.is_anonymous,
               d.name as dept_name,
               s.full_name as student_name, s.student_no,
               a.full_name as staff_name
        FROM tickets t
        JOIN departments d ON t.department_id=d.id
        JOIN users s ON t.student_id=s.id
        LEFT JOIN users a ON t.assigned_to=a.id
        WHERE t.status IN ('Resolved','Closed')
          AND t.resolved_at BETWEEN ? AND ?
        ORDER BY t.resolved_at DESC
    """, (w_start_str, w_end_str)).fetchall()

    # All tickets opened this week
    opened_this_week = db.execute("""
        SELECT COUNT(*) FROM tickets WHERE created_at BETWEEN ? AND ?
    """, (w_start_str, w_end_str)).fetchone()[0]

    # Overall stats for week
    total_resolved = len(resolved_tickets)
    total_opened   = opened_this_week
    still_open     = db.execute("SELECT COUNT(*) FROM tickets WHERE status NOT IN ('Resolved','Closed')").fetchone()[0]
    urgent_open    = db.execute("SELECT COUNT(*) FROM tickets WHERE priority='Urgent' AND status NOT IN ('Resolved','Closed')").fetchone()[0]

    # Avg resolution time (hours)
    rated_tickets  = [t for t in resolved_tickets if t['rating']]
    avg_rating     = round(sum(t['rating'] for t in rated_tickets) / len(rated_tickets), 1) if rated_tickets else None

    # Dept breakdown for week
    dept_stats = db.execute("""
        SELECT d.name, COUNT(t.id) as cnt
        FROM departments d LEFT JOIN tickets t
          ON t.department_id=d.id AND t.created_at BETWEEN ? AND ?
        GROUP BY d.id HAVING cnt>0 ORDER BY cnt DESC
    """, (w_start_str, w_end_str)).fetchall()

    # Priority breakdown
    prio_stats = db.execute("""
        SELECT priority, COUNT(*) as cnt FROM tickets
        WHERE created_at BETWEEN ? AND ?
        GROUP BY priority ORDER BY cnt DESC
    """, (w_start_str, w_end_str)).fetchall()

    # Top performers (staff who resolved most this week)
    top_staff = db.execute("""
        SELECT a.full_name, d.name as dept_name, COUNT(t.id) as resolved,
               ROUND(AVG(t.rating),1) as avg_rating
        FROM tickets t
        JOIN users a ON t.assigned_to=a.id
        JOIN departments d ON a.department_id=d.id
        WHERE t.status IN ('Resolved','Closed') AND t.resolved_at BETWEEN ? AND ?
        GROUP BY a.id ORDER BY resolved DESC LIMIT 10
    """, (w_start_str, w_end_str)).fetchall()

    # SLA — tickets unresolved > 3 days
    sla_breached = db.execute("""
        SELECT COUNT(*) FROM tickets
        WHERE status NOT IN ('Resolved','Closed')
          AND created_at < datetime('now','-3 days')
    """).fetchone()[0]

    # Unresolved high-priority tickets
    unresolved_urgent = db.execute("""
        SELECT t.ticket_no, t.subject, t.priority, t.created_at,
               d.name as dept_name,
               CASE WHEN t.assigned_to IS NULL THEN 'Unassigned' ELSE a.full_name END as assignee
        FROM tickets t JOIN departments d ON t.department_id=d.id
        LEFT JOIN users a ON t.assigned_to=a.id
        WHERE t.status NOT IN ('Resolved','Closed') AND t.priority IN ('Urgent','High')
        ORDER BY CASE t.priority WHEN 'Urgent' THEN 1 ELSE 2 END, t.created_at ASC
        LIMIT 15
    """).fetchall()

    # ── Build PDF ──────────────────────────────────────────────────────────────
    buf  = io.BytesIO()
    doc  = ReportTemplate(buf, week_label, generated_at)
    story = []

    # ── Cover / Title ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph('Weekly Ticket Resolution Report', styles['h1']))
    story.append(Paragraph(f'Period: <b>{week_label}</b>  |  Durban University of Technology', styles['body']))
    story.append(HRFlowable(width='100%', thickness=2, color=GOLD, spaceAfter=10))

    # Stat boxes
    story.append(stat_box_table([
        ('Opened This Week',   total_opened,   NAVY),
        ('Resolved This Week', total_resolved, GREEN),
        ('Still Open',         still_open,     ORANGE),
        ('Urgent Open',        urgent_open,    RED),
        ('SLA Breached (>3d)', sla_breached,   RED if sla_breached else GREEN),
        ('Avg Rating',         f'{avg_rating}/5' if avg_rating else 'N/A', colors.HexColor('#9a6200')),
    ]))
    story.append(Spacer(1, 6*mm))

    # ── Charts Row ─────────────────────────────────────────────────────────────
    if dept_stats or prio_stats:
        story.append(section_header('  TICKET BREAKDOWN — THIS WEEK', styles))
        story.append(Spacer(1, 3*mm))
        chart_data = []
        if dept_stats:
            bc = dept_bar_chart(dept_stats, width=110*mm, height=55*mm)
            if bc:
                chart_data.append([Paragraph('By Department', styles['h3']), Paragraph('By Priority', styles['h3'])])
        if prio_stats:
            pc = priority_pie(prio_stats, size=70)
            if pc and dept_stats and bc:
                inner = Table([[bc, pc]], colWidths=[115*mm, 85*mm])
                inner.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0)]))
                story.append(inner)
        story.append(Spacer(1, 4*mm))

    # ── Resolved Tickets Table ─────────────────────────────────────────────────
    story.append(section_header('  RESOLVED TICKETS THIS WEEK', styles))
    story.append(Spacer(1, 3*mm))

    if resolved_tickets:
        col_w = [(W-36*mm)*f for f in [.13, .22, .12, .12, .11, .10, .10, .10]]
        header = [
            Paragraph('Ticket No',    ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph('Subject',      ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Department',   ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Student',      ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Resolved By',  ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Priority',     ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph('Time Taken',   ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph('Rating',       ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
        ]
        rows = [header]
        for t in resolved_tickets:
            rt   = resolve_time(t['created_at'], t['resolved_at'])
            pcol = priority_color(t['priority'])
            rating_str = stars(t['rating']) if t['rating'] else '—'
            student_str = 'Anonymous' if t['is_anonymous'] else (t['student_name'] or '—')
            rows.append([
                Paragraph(t['ticket_no'],          ParagraphStyle('TD', fontName='Courier-Bold', fontSize=7.5, textColor=NAVY)),
                Paragraph((t['subject'] or '')[:38], ParagraphStyle('TD', fontName='Helvetica', fontSize=8)),
                Paragraph(t['dept_name'] or '—',   ParagraphStyle('TD', fontName='Helvetica', fontSize=8)),
                Paragraph(student_str[:20],         ParagraphStyle('TD', fontName='Helvetica', fontSize=8)),
                Paragraph((t['staff_name'] or 'Unassigned')[:18], ParagraphStyle('TD', fontName='Helvetica', fontSize=8)),
                Paragraph(t['priority'],            ParagraphStyle('TD', fontName='Helvetica-Bold', fontSize=8, textColor=pcol, alignment=TA_CENTER)),
                Paragraph(rt,                       ParagraphStyle('TD', fontName='Helvetica', fontSize=8, alignment=TA_CENTER)),
                Paragraph(rating_str,               ParagraphStyle('TD', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#f59e4b'), alignment=TA_CENTER)),
            ])

        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,0),  NAVY),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE, LGREY]),
            ('GRID',         (0,0),(-1,-1), 0.3, BORDER),
            ('FONTSIZE',     (0,0),(-1,-1), 8),
            ('TOPPADDING',   (0,0),(-1,-1), 5),
            ('BOTTOMPADDING',(0,0),(-1,-1), 5),
            ('LEFTPADDING',  (0,0),(-1,-1), 5),
            ('RIGHTPADDING', (0,0),(-1,-1), 5),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(tbl)

        # ── Student Feedback / Ratings Section ────────────────────────────────
        feedbacks = [t for t in resolved_tickets if t['rating_comment']]
        if feedbacks:
            story.append(Spacer(1, 6*mm))
            story.append(section_header('  STUDENT FEEDBACK & RATINGS', styles))
            story.append(Spacer(1, 3*mm))
            for t in feedbacks:
                student_str = 'Anonymous' if t['is_anonymous'] else t['student_name']
                block = KeepTogether([
                    Table([[
                        Paragraph(t['ticket_no'], ParagraphStyle('FTno', fontName='Courier-Bold', fontSize=8, textColor=NAVY)),
                        Paragraph(f"{t['subject'][:50]}  |  {t['dept_name']}", ParagraphStyle('FSub', fontName='Helvetica-Bold', fontSize=8.5, textColor=BLACK)),
                        Paragraph(stars(t['rating']), ParagraphStyle('FStar', fontName='Helvetica', fontSize=11, textColor=colors.HexColor('#f59e4b'), alignment=TA_RIGHT)),
                    ]], colWidths=[(W-36*mm)*f for f in [.15,.65,.20]],
                    style=TableStyle([
                        ('BACKGROUND',(0,0),(-1,-1),LGREY),
                        ('BOX',(0,0),(-1,-1),0.5,BORDER),
                        ('TOPPADDING',(0,0),(-1,-1),5),
                        ('BOTTOMPADDING',(0,0),(-1,-1),5),
                        ('LEFTPADDING',(0,0),(-1,-1),8),
                        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                    ])),
                    Table([[
                        Paragraph(f'"{t["rating_comment"]}"', styles['quote']),
                    ]], colWidths=[W-36*mm],
                    style=TableStyle([
                        ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#fffde7')),
                        ('LEFTPADDING',(0,0),(-1,-1),12),
                        ('RIGHTPADDING',(0,0),(-1,-1),12),
                        ('TOPPADDING',(0,0),(-1,-1),6),
                        ('BOTTOMPADDING',(0,0),(-1,-1),6),
                        ('BOX',(0,0),(-1,-1),0.5,GOLD),
                    ])),
                    Table([[
                        Paragraph(f'Student: {student_str}  |  Resolved by: {t["staff_name"] or "N/A"}  |  Time taken: {resolve_time(t["created_at"], t["resolved_at"])}', styles['small']),
                    ]], colWidths=[W-36*mm],
                    style=TableStyle([
                        ('TOPPADDING',(0,0),(-1,-1),3),
                        ('BOTTOMPADDING',(0,0),(-1,-1),3),
                        ('LEFTPADDING',(0,0),(-1,-1),8),
                    ])),
                    Spacer(1, 4*mm),
                ])
                story.append(block)
    else:
        story.append(Paragraph('No tickets were resolved during this period.', styles['muted']))
        story.append(Spacer(1, 4*mm))

    # ── Top Performers ─────────────────────────────────────────────────────────
    if top_staff:
        story.append(PageBreak())
        story.append(section_header('  STAFF PERFORMANCE — TOP RESOLVERS', styles))
        story.append(Spacer(1, 3*mm))
        perf_header = [
            Paragraph('#',            ParagraphStyle('PH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph('Staff Member', ParagraphStyle('PH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Department',   ParagraphStyle('PH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Resolved',     ParagraphStyle('PH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph('Avg Rating',   ParagraphStyle('PH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph('Performance',  ParagraphStyle('PH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
        ]
        perf_rows = [perf_header]
        max_resolved = top_staff[0]['resolved'] if top_staff else 1
        for i, s in enumerate(top_staff, 1):
            bar_pct = int((s['resolved'] / max_resolved) * 100)
            medal   = '🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else f'#{i}'
            rating_disp = f"{s['avg_rating']}/5 {stars(s['avg_rating'] or 0)}" if s['avg_rating'] else '—'
            perf_bar = f"{'█' * (bar_pct // 10)}{'░' * (10 - bar_pct // 10)} {s['resolved']}"
            perf_rows.append([
                Paragraph(str(medal),              ParagraphStyle('PC', fontName='Helvetica-Bold', fontSize=9, alignment=TA_CENTER)),
                Paragraph(s['full_name'],           ParagraphStyle('PN', fontName='Helvetica-Bold', fontSize=8.5, textColor=NAVY)),
                Paragraph(s['dept_name'] or '—',   ParagraphStyle('PD', fontName='Helvetica', fontSize=8)),
                Paragraph(str(s['resolved']),       ParagraphStyle('PR', fontName='Helvetica-Bold', fontSize=10, textColor=GREEN, alignment=TA_CENTER)),
                Paragraph(rating_disp,              ParagraphStyle('PRt', fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#f59e4b'), alignment=TA_CENTER)),
                Paragraph(perf_bar,                 ParagraphStyle('PB', fontName='Courier', fontSize=7.5, textColor=NAVY)),
            ])
        perf_tbl = Table(perf_rows, colWidths=[(W-36*mm)*f for f in [.06,.22,.18,.10,.16,.28]], repeatRows=1)
        perf_tbl.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,0),  NAVY),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE, LGREY]),
            ('BACKGROUND',   (0,1),(5,1),   colors.HexColor('#fffde7')),  # Gold for #1
            ('GRID',         (0,0),(-1,-1), 0.3, BORDER),
            ('TOPPADDING',   (0,0),(-1,-1), 6),
            ('BOTTOMPADDING',(0,0),(-1,-1), 6),
            ('LEFTPADDING',  (0,0),(-1,-1), 6),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(perf_tbl)

    # ── Unresolved Urgent/High ─────────────────────────────────────────────────
    if unresolved_urgent:
        story.append(Spacer(1, 6*mm))
        story.append(section_header('  ATTENTION REQUIRED — OPEN URGENT/HIGH TICKETS', styles))
        story.append(Spacer(1, 3*mm))
        urg_header = [
            Paragraph('Ticket No',  ParagraphStyle('UH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Subject',    ParagraphStyle('UH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Dept',       ParagraphStyle('UH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
            Paragraph('Priority',   ParagraphStyle('UH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph('Opened',     ParagraphStyle('UH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph('Assigned To',ParagraphStyle('UH', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
        ]
        urg_rows = [urg_header]
        for t in unresolved_urgent:
            age = resolve_time(t['created_at'], None)
            days_open = (datetime.utcnow() - datetime.strptime(t['created_at'][:19], '%Y-%m-%d %H:%M:%S')).days
            pcol = RED if t['priority']=='Urgent' else ORANGE
            urg_rows.append([
                Paragraph(t['ticket_no'],           ParagraphStyle('UT', fontName='Courier-Bold', fontSize=7.5, textColor=NAVY)),
                Paragraph((t['subject'] or '')[:35], ParagraphStyle('US', fontName='Helvetica', fontSize=8)),
                Paragraph(t['dept_name'] or '—',    ParagraphStyle('UD', fontName='Helvetica', fontSize=8)),
                Paragraph(t['priority'],             ParagraphStyle('UP', fontName='Helvetica-Bold', fontSize=8, textColor=pcol, alignment=TA_CENTER)),
                Paragraph(f'{days_open}d ago',       ParagraphStyle('UA', fontName='Helvetica', fontSize=8, textColor=RED if days_open>3 else DGREY, alignment=TA_CENTER)),
                Paragraph(t['assignee'] or 'Unassigned', ParagraphStyle('UAs', fontName='Helvetica', fontSize=8)),
            ])
        urg_tbl = Table(urg_rows, colWidths=[(W-36*mm)*f for f in [.15,.27,.14,.11,.12,.21]], repeatRows=1)
        urg_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0),  RED),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, colors.HexColor('#fff5f5')]),
            ('GRID',          (0,0),(-1,-1), 0.3, BORDER),
            ('TOPPADDING',    (0,0),(-1,-1), 5),
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING',   (0,0),(-1,-1), 5),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(urg_tbl)

    # ── Closing ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width='100%', thickness=1, color=GOLD))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        f'This report was automatically generated by the CodeCrafters DUT Ticketing System on {generated_at}. '
        f'It covers the week of {week_label}. For queries contact the system administrator.',
        styles['muted']
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read(), week_label
