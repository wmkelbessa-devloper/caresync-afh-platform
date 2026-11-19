import io
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, send_file, Response
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = Flask(__name__)
DB_NAME = "afh_web.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS residents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                room_number TEXT NOT NULL,
                care_level TEXT,
                allergies TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emar_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                medication TEXT NOT NULL,
                dosage TEXT NOT NULL,
                administered_by TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'Administered',
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                systolic INTEGER,
                diastolic INTEGER,
                heart_rate INTEGER,
                timestamp TEXT NOT NULL,
                is_abnormal INTEGER DEFAULT 0,
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shift_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_window TEXT NOT NULL,
                author_name TEXT NOT NULL,
                note_text TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                provider_name TEXT NOT NULL,
                clinic_location TEXT NOT NULL,
                appt_date TEXT NOT NULL,
                appt_time TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS behavior_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                behavior_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                trigger_notes TEXT,
                intervention TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS physician_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                form_title TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                due_date TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.commit()


@app.route("/")
def home():
    return render_template("landing.html")


@app.route("/dashboard")
def dashboard():
    with get_db() as conn:
        residents = conn.execute("SELECT * FROM residents ORDER BY room_number ASC").fetchall()
        emar_logs = conn.execute("""
            SELECT e.*, r.name AS resident_name, r.room_number
            FROM emar_logs e
            JOIN residents r ON e.resident_id = r.id
            ORDER BY e.id DESC LIMIT 10
        """).fetchall()
        alerts = conn.execute("""
            SELECT v.*, r.name AS resident_name, r.room_number
            FROM vitals v
            JOIN residents r ON v.resident_id = r.id
            WHERE v.is_abnormal = 1
            ORDER BY v.id DESC LIMIT 5
        """).fetchall()
        shift_notes = conn.execute("""
            SELECT * FROM shift_notes ORDER BY id DESC LIMIT 6
        """).fetchall()
        appointments = conn.execute("""
            SELECT a.*, r.name AS resident_name, r.room_number
            FROM appointments a
            JOIN residents r ON a.resident_id = r.id
            ORDER BY a.appt_date ASC, a.appt_time ASC
        """).fetchall()
        behavior_logs = conn.execute("""
            SELECT b.*, r.name AS resident_name, r.room_number
            FROM behavior_logs b
            JOIN residents r ON b.resident_id = r.id
            ORDER BY b.id DESC LIMIT 8
        """).fetchall()
        physician_forms = conn.execute("""
            SELECT f.*, r.name AS resident_name, r.room_number
            FROM physician_forms f
            JOIN residents r ON f.resident_id = r.id
            ORDER BY f.id DESC LIMIT 10
        """).fetchall()

    today_display = datetime.now().strftime("%A, %b %d, %Y")
    return render_template(
        "dashboard.html",
        residents=residents,
        emar_logs=emar_logs,
        alerts=alerts,
        shift_notes=shift_notes,
        appointments=appointments,
        behavior_logs=behavior_logs,
        physician_forms=physician_forms,
        today_display=today_display
    )


@app.route("/add_resident", methods=["POST"])
def add_resident():
    name = request.form.get("name", "").strip()
    room_number = request.form.get("room_number", "").strip()
    care_level = request.form.get("care_level", "Level 2")
    allergies = request.form.get("allergies", "NKDA").strip() or "NKDA"

    if name and room_number:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO residents (name, room_number, care_level, allergies) VALUES (?, ?, ?, ?)",
                (name, room_number, care_level, allergies)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/log_medication", methods=["POST"])
def log_medication():
    resident_id = request.form.get("resident_id")
    medication = request.form.get("medication", "").strip()
    dosage = request.form.get("dosage", "").strip()
    administered_by = request.form.get("administered_by", "Caregiver").strip()
    timestamp = datetime.now().strftime("%I:%M %p • %Y-%m-%d")

    if resident_id and medication:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO emar_logs (resident_id, medication, dosage, administered_by, timestamp) VALUES (?, ?, ?, ?, ?)",
                (resident_id, medication, dosage, administered_by, timestamp)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/log_vitals", methods=["POST"])
def log_vitals():
    resident_id = request.form.get("resident_id")
    systolic = int(request.form.get("systolic", 120))
    diastolic = int(request.form.get("diastolic", 80))
    heart_rate = int(request.form.get("heart_rate", 72))
    timestamp = datetime.now().strftime("%I:%M %p")

    is_abnormal = 1 if (systolic >= 140 or diastolic >= 90 or systolic <= 90) else 0

    if resident_id:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO vitals (resident_id, systolic, diastolic, heart_rate, timestamp, is_abnormal) VALUES (?, ?, ?, ?, ?, ?)",
                (resident_id, systolic, diastolic, heart_rate, timestamp, is_abnormal)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/log_shift_note", methods=["POST"])
def log_shift_note():
    shift_window = request.form.get("shift_window", "Day Shift").strip()
    author_name = request.form.get("author_name", "Caregiver").strip() or "Caregiver"
    note_text = request.form.get("note_text", "").strip()
    timestamp = datetime.now().strftime("%I:%M %p • %Y-%m-%d")

    if note_text:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO shift_notes (shift_window, author_name, note_text, timestamp) VALUES (?, ?, ?, ?)",
                (shift_window, author_name, note_text, timestamp)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/add_appointment", methods=["POST"])
def add_appointment():
    resident_id = request.form.get("resident_id")
    provider_name = request.form.get("provider_name", "").strip()
    clinic_location = request.form.get("clinic_location", "Clinic / Office").strip() or "Clinic / Office"
    appt_date = request.form.get("appt_date", "").strip()
    appt_time = request.form.get("appt_time", "09:00").strip() or "09:00"
    notes = request.form.get("notes", "").strip()

    if resident_id and provider_name and appt_date:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO appointments
                   (resident_id, provider_name, clinic_location, appt_date, appt_time, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (resident_id, provider_name, clinic_location, appt_date, appt_time, notes)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/appointment_ics/<int:appt_id>")
def appointment_ics(appt_id):
    with get_db() as conn:
        appt = conn.execute("""
            SELECT a.*, r.name AS resident_name, r.room_number
            FROM appointments a
            JOIN residents r ON a.resident_id = r.id
            WHERE a.id = ?
        """, (appt_id,)).fetchone()

    if not appt:
        return redirect(url_for("dashboard"))

    try:
        start_dt = datetime.strptime(f"{appt['appt_date']} {appt['appt_time']}", "%Y-%m-%d %H:%M")
    except ValueError:
        start_dt = datetime.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=1)

    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
    dtend = end_dt.strftime("%Y%m%dT%H%M%S")

    summary = f"AFH Appt: {appt['resident_name']} (Room {appt['room_number']}) — {appt['provider_name']}"
    description = (appt["notes"] or "Resident medical appointment").replace("\n", "\\n")
    location = appt["clinic_location"]

    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//CareSync AFH//Calendar//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:caresync-appt-{appt['id']}@caresync-afh.local\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART:{dtstart}\r\n"
        f"DTEND:{dtend}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"LOCATION:{location}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=appointment_{appt['id']}.ics"}
    )


@app.route("/log_behavior", methods=["POST"])
def log_behavior():
    resident_id = request.form.get("resident_id")
    behavior_type = request.form.get("behavior_type", "Agitation / Restlessness").strip()
    severity = request.form.get("severity", "Moderate").strip()
    trigger_notes = request.form.get("trigger_notes", "").strip()
    intervention = request.form.get("intervention", "").strip()
    timestamp = datetime.now().strftime("%I:%M %p • %Y-%m-%d")

    if resident_id and behavior_type:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO behavior_logs
                   (resident_id, behavior_type, severity, trigger_notes, intervention, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (resident_id, behavior_type, severity, trigger_notes, intervention, timestamp)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/add_physician_form", methods=["POST"])
def add_physician_form():
    resident_id = request.form.get("resident_id")
    form_title = request.form.get("form_title", "").strip()
    provider_name = request.form.get("provider_name", "").strip() or "Primary Care Provider"
    due_date = request.form.get("due_date", "").strip()
    status = request.form.get("status", "Needed").strip()
    notes = request.form.get("notes", "").strip()

    if resident_id and form_title:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO physician_forms
                   (resident_id, form_title, provider_name, due_date, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (resident_id, form_title, provider_name, due_date, status, notes)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/update_form_status/<int:form_id>", methods=["POST"])
def update_form_status(form_id):
    new_status = request.form.get("status", "Signed / On File").strip()
    with get_db() as conn:
        conn.execute("UPDATE physician_forms SET status = ? WHERE id = ?", (new_status, form_id))
        conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/export_pdf")
def export_pdf():
    target_date = datetime.now().strftime("%Y-%m-%d")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Oregon Adult Foster Home — Daily Compliance & Care Report ({target_date})", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    with get_db() as conn:
        logs = conn.execute("""
            SELECT r.name, r.room_number, e.medication, e.dosage, e.administered_by, e.timestamp
            FROM emar_logs e
            JOIN residents r ON e.resident_id = r.id
            ORDER BY e.id DESC
        """).fetchall()
        notes = conn.execute("""
            SELECT shift_window, author_name, note_text, timestamp
            FROM shift_notes
            ORDER BY id DESC
        """).fetchall()
        appts = conn.execute("""
            SELECT r.name, r.room_number, a.provider_name, a.clinic_location, a.appt_date, a.appt_time, a.notes
            FROM appointments a
            JOIN residents r ON a.resident_id = r.id
            ORDER BY a.appt_date ASC, a.appt_time ASC
        """).fetchall()
        behaviors = conn.execute("""
            SELECT r.name, r.room_number, b.behavior_type, b.severity, b.trigger_notes, b.intervention, b.timestamp
            FROM behavior_logs b
            JOIN residents r ON b.resident_id = r.id
            ORDER BY b.id DESC
        """).fetchall()
        forms = conn.execute("""
            SELECT r.name, r.room_number, f.form_title, f.provider_name, f.due_date, f.status, f.notes
            FROM physician_forms f
            JOIN residents r ON f.resident_id = r.id
            ORDER BY f.id DESC
        """).fetchall()

    elements.append(Paragraph("Medication Administration Records (eMAR)", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    table_data = [["Resident", "Room", "Medication", "Dosage", "Caregiver", "Time Recorded"]]
    for row in logs:
        table_data.append([row["name"], row["room_number"], row["medication"], row["dosage"], row["administered_by"], row["timestamp"]])
    if len(table_data) == 1:
        table_data.append(["No records", "-", "-", "-", "-", "-"])

    table = Table(table_data, colWidths=[110, 45, 110, 70, 85, 110])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#065F46")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Scheduled Doctor Appointments", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    if appts:
        for a in appts:
            extra = f" — {a['notes']}" if a["notes"] else ""
            elements.append(Paragraph(
                f"<b>{a['appt_date']} at {a['appt_time']}</b>: {a['name']} (Room {a['room_number']}) with {a['provider_name']} ({a['clinic_location']}){extra}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("No appointments scheduled.", styles["Normal"]))

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Behavior Tracking Log", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    if behaviors:
        for b in behaviors:
            trig = f" | Trigger: {b['trigger_notes']}" if b["trigger_notes"] else ""
            interv = f" | Intervention: {b['intervention']}" if b["intervention"] else ""
            elements.append(Paragraph(
                f"<b>{b['name']} (Room {b['room_number']})</b> — {b['behavior_type']} [{b['severity']}] ({b['timestamp']}){trig}{interv}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("No behavior logs recorded.", styles["Normal"]))

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Physician Forms & Orders", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    if forms:
        for f in forms:
            due = f" | Due: {f['due_date']}" if f["due_date"] else ""
            fnotes = f" — {f['notes']}" if f["notes"] else ""
            elements.append(Paragraph(
                f"<b>{f['form_title']}</b> [{f['status']}] for {f['name']} (Room {f['room_number']}) • Provider: {f['provider_name']}{due}{fnotes}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("No physician forms tracked.", styles["Normal"]))

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Caregiver Shift Notes", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    if notes:
        for n in notes:
            elements.append(Paragraph(
                f"<b>{n['shift_window']}</b> — {n['author_name']} ({n['timestamp']}): {n['note_text']}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("No shift notes recorded for today.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"AFH_Compliance_Report_{target_date}.pdf", mimetype="application/pdf")


@app.route("/seed_demo_data", methods=["POST"])
def seed_demo_data():
    with get_db() as conn:
        existing = conn.execute("SELECT COUNT(*) AS cnt FROM residents").fetchone()["cnt"]
        if existing == 0:
            conn.executemany(
                "INSERT INTO residents (name, room_number, care_level, allergies) VALUES (?, ?, ?, ?)",
                [
                    ("Arthur Pendelton", "101", "Level 2", "Penicillin"),
                    ("Eleanor Vance", "102", "Level 3", "NKDA"),
                    ("Harold Jenkins", "104", "Level 1", "Sulfa"),
                ]
            )
            res_rows = conn.execute("SELECT id, name FROM residents").fetchall()
            res_map = {r["name"]: r["id"] for r in res_rows}

            conn.executemany(
                "INSERT INTO emar_logs (resident_id, medication, dosage, administered_by, timestamp, status) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (res_map["Arthur Pendelton"], "Lisinopril", "10 mg PO", "M. Rivera, CNA", "08:15 AM • Today", "Administered"),
                    (res_map["Eleanor Vance"], "Memantine", "10 mg PO", "M. Rivera, CNA", "08:30 AM • Today", "Administered"),
                ]
            )
            conn.executemany(
                "INSERT INTO vitals (resident_id, systolic, diastolic, heart_rate, timestamp, is_abnormal) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (res_map["Arthur Pendelton"], 154, 92, 78, "08:20 AM", 1),
                    (res_map["Harold Jenkins"], 122, 76, 68, "08:40 AM", 0),
                ]
            )
            conn.execute(
                "INSERT INTO shift_notes (shift_window, author_name, note_text, timestamp) VALUES (?, ?, ?, ?)",
                ("Day Shift", "M. Rivera, CNA", "Morning meds completed on time; BP recheck scheduled for Arthur in Room 101.", "09:00 AM • Today")
            )
            conn.execute(
                "INSERT INTO appointments (resident_id, provider_name, clinic_location, appt_date, appt_time, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (res_map["Eleanor Vance"], "Dr. Sarah Chen, MD", "Oregon Geriatrics Clinic, Portland", "2026-12-03", "10:30", "Bring current med sheet and behavior log.")
            )
            conn.execute(
                "INSERT INTO behavior_logs (resident_id, behavior_type, severity, trigger_notes, intervention, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (res_map["Eleanor Vance"], "Late-Afternoon Restlessness", "Moderate", "Pacing near front door around 4:30 PM", "Guided to quiet lounge with warm tea and music; settled in 15 mins.", "04:40 PM • Yesterday")
            )
            conn.execute(
                "INSERT INTO physician_forms (resident_id, form_title, provider_name, due_date, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (res_map["Arthur Pendelton"], "Annual Physician Assessment & Orders", "Dr. David Morales, MD", "2026-12-15", "Sent to Provider", "Faxed to clinic; awaiting signed return.")
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/discharge_resident/<int:resident_id>", methods=["POST"])
def discharge_resident(resident_id):
    with get_db() as conn:
        conn.execute("DELETE FROM emar_logs WHERE resident_id = ?", (resident_id,))
        conn.execute("DELETE FROM vitals WHERE resident_id = ?", (resident_id,))
        conn.execute("DELETE FROM appointments WHERE resident_id = ?", (resident_id,))
        conn.execute("DELETE FROM behavior_logs WHERE resident_id = ?", (resident_id,))
        conn.execute("DELETE FROM physician_forms WHERE resident_id = ?", (resident_id,))
        conn.execute("DELETE FROM residents WHERE id = ?", (resident_id,))
        conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/reset_demo_data", methods=["POST"])
def reset_demo_data():
    with get_db() as conn:
        conn.execute("DELETE FROM emar_logs")
        conn.execute("DELETE FROM vitals")
        conn.execute("DELETE FROM shift_notes")
        conn.execute("DELETE FROM appointments")
        conn.execute("DELETE FROM behavior_logs")
        conn.execute("DELETE FROM physician_forms")
        conn.execute("DELETE FROM residents")
        conn.commit()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
EOFcat << 'EOF' > app.py
import io
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, send_file, Response
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = Flask(__name__)
DB_NAME = "afh_web.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS residents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                room_number TEXT NOT NULL,
                care_level TEXT,
                allergies TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emar_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                medication TEXT NOT NULL,
                dosage TEXT NOT NULL,
                administered_by TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'Administered',
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                systolic INTEGER,
                diastolic INTEGER,
                heart_rate INTEGER,
                timestamp TEXT NOT NULL,
                is_abnormal INTEGER DEFAULT 0,
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shift_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_window TEXT NOT NULL,
                author_name TEXT NOT NULL,
                note_text TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                provider_name TEXT NOT NULL,
                clinic_location TEXT NOT NULL,
                appt_date TEXT NOT NULL,
                appt_time TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS behavior_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                behavior_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                trigger_notes TEXT,
                intervention TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS physician_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                form_title TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                due_date TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY(resident_id) REFERENCES residents(id)
            )
        """)
        conn.commit()


@app.route("/")
def home():
    return render_template("landing.html")


@app.route("/dashboard")
def dashboard():
    with get_db() as conn:
        residents = conn.execute("SELECT * FROM residents ORDER BY room_number ASC").fetchall()
        emar_logs = conn.execute("""
            SELECT e.*, r.name AS resident_name, r.room_number
            FROM emar_logs e
            JOIN residents r ON e.resident_id = r.id
            ORDER BY e.id DESC LIMIT 10
        """).fetchall()
        alerts = conn.execute("""
            SELECT v.*, r.name AS resident_name, r.room_number
            FROM vitals v
            JOIN residents r ON v.resident_id = r.id
            WHERE v.is_abnormal = 1
            ORDER BY v.id DESC LIMIT 5
        """).fetchall()
        shift_notes = conn.execute("""
            SELECT * FROM shift_notes ORDER BY id DESC LIMIT 6
        """).fetchall()
        appointments = conn.execute("""
            SELECT a.*, r.name AS resident_name, r.room_number
            FROM appointments a
            JOIN residents r ON a.resident_id = r.id
            ORDER BY a.appt_date ASC, a.appt_time ASC
        """).fetchall()
        behavior_logs = conn.execute("""
            SELECT b.*, r.name AS resident_name, r.room_number
            FROM behavior_logs b
            JOIN residents r ON b.resident_id = r.id
            ORDER BY b.id DESC LIMIT 8
        """).fetchall()
        physician_forms = conn.execute("""
            SELECT f.*, r.name AS resident_name, r.room_number
            FROM physician_forms f
            JOIN residents r ON f.resident_id = r.id
            ORDER BY f.id DESC LIMIT 10
        """).fetchall()

    today_display = datetime.now().strftime("%A, %b %d, %Y")
    return render_template(
        "dashboard.html",
        residents=residents,
        emar_logs=emar_logs,
        alerts=alerts,
        shift_notes=shift_notes,
        appointments=appointments,
        behavior_logs=behavior_logs,
        physician_forms=physician_forms,
        today_display=today_display
    )


@app.route("/add_resident", methods=["POST"])
def add_resident():
    name = request.form.get("name", "").strip()
    room_number = request.form.get("room_number", "").strip()
    care_level = request.form.get("care_level", "Level 2")
    allergies = request.form.get("allergies", "NKDA").strip() or "NKDA"

    if name and room_number:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO residents (name, room_number, care_level, allergies) VALUES (?, ?, ?, ?)",
                (name, room_number, care_level, allergies)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/log_medication", methods=["POST"])
def log_medication():
    resident_id = request.form.get("resident_id")
    medication = request.form.get("medication", "").strip()
    dosage = request.form.get("dosage", "").strip()
    administered_by = request.form.get("administered_by", "Caregiver").strip()
    timestamp = datetime.now().strftime("%I:%M %p • %Y-%m-%d")

    if resident_id and medication:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO emar_logs (resident_id, medication, dosage, administered_by, timestamp) VALUES (?, ?, ?, ?, ?)",
                (resident_id, medication, dosage, administered_by, timestamp)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/log_vitals", methods=["POST"])
def log_vitals():
    resident_id = request.form.get("resident_id")
    systolic = int(request.form.get("systolic", 120))
    diastolic = int(request.form.get("diastolic", 80))
    heart_rate = int(request.form.get("heart_rate", 72))
    timestamp = datetime.now().strftime("%I:%M %p")

    is_abnormal = 1 if (systolic >= 140 or diastolic >= 90 or systolic <= 90) else 0

    if resident_id:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO vitals (resident_id, systolic, diastolic, heart_rate, timestamp, is_abnormal) VALUES (?, ?, ?, ?, ?, ?)",
                (resident_id, systolic, diastolic, heart_rate, timestamp, is_abnormal)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/log_shift_note", methods=["POST"])
def log_shift_note():
    shift_window = request.form.get("shift_window", "Day Shift").strip()
    author_name = request.form.get("author_name", "Caregiver").strip() or "Caregiver"
    note_text = request.form.get("note_text", "").strip()
    timestamp = datetime.now().strftime("%I:%M %p • %Y-%m-%d")

    if note_text:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO shift_notes (shift_window, author_name, note_text, timestamp) VALUES (?, ?, ?, ?)",
                (shift_window, author_name, note_text, timestamp)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/add_appointment", methods=["POST"])
def add_appointment():
    resident_id = request.form.get("resident_id")
    provider_name = request.form.get("provider_name", "").strip()
    clinic_location = request.form.get("clinic_location", "Clinic / Office").strip() or "Clinic / Office"
    appt_date = request.form.get("appt_date", "").strip()
    appt_time = request.form.get("appt_time", "09:00").strip() or "09:00"
    notes = request.form.get("notes", "").strip()

    if resident_id and provider_name and appt_date:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO appointments
                   (resident_id, provider_name, clinic_location, appt_date, appt_time, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (resident_id, provider_name, clinic_location, appt_date, appt_time, notes)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/appointment_ics/<int:appt_id>")
def appointment_ics(appt_id):
    with get_db() as conn:
        appt = conn.execute("""
            SELECT a.*, r.name AS resident_name, r.room_number
            FROM appointments a
            JOIN residents r ON a.resident_id = r.id
            WHERE a.id = ?
        """, (appt_id,)).fetchone()

    if not appt:
        return redirect(url_for("dashboard"))

    try:
        start_dt = datetime.strptime(f"{appt['appt_date']} {appt['appt_time']}", "%Y-%m-%d %H:%M")
    except ValueError:
        start_dt = datetime.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=1)

    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
    dtend = end_dt.strftime("%Y%m%dT%H%M%S")

    summary = f"AFH Appt: {appt['resident_name']} (Room {appt['room_number']}) — {appt['provider_name']}"
    description = (appt["notes"] or "Resident medical appointment").replace("\n", "\\n")
    location = appt["clinic_location"]

    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//CareSync AFH//Calendar//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:caresync-appt-{appt['id']}@caresync-afh.local\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART:{dtstart}\r\n"
        f"DTEND:{dtend}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"LOCATION:{location}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=appointment_{appt['id']}.ics"}
    )


@app.route("/log_behavior", methods=["POST"])
def log_behavior():
    resident_id = request.form.get("resident_id")
    behavior_type = request.form.get("behavior_type", "Agitation / Restlessness").strip()
    severity = request.form.get("severity", "Moderate").strip()
    trigger_notes = request.form.get("trigger_notes", "").strip()
    intervention = request.form.get("intervention", "").strip()
    timestamp = datetime.now().strftime("%I:%M %p • %Y-%m-%d")

    if resident_id and behavior_type:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO behavior_logs
                   (resident_id, behavior_type, severity, trigger_notes, intervention, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (resident_id, behavior_type, severity, trigger_notes, intervention, timestamp)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/add_physician_form", methods=["POST"])
def add_physician_form():
    resident_id = request.form.get("resident_id")
    form_title = request.form.get("form_title", "").strip()
    provider_name = request.form.get("provider_name", "").strip() or "Primary Care Provider"
    due_date = request.form.get("due_date", "").strip()
    status = request.form.get("status", "Needed").strip()
    notes = request.form.get("notes", "").strip()

    if resident_id and form_title:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO physician_forms
                   (resident_id, form_title, provider_name, due_date, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (resident_id, form_title, provider_name, due_date, status, notes)
            )
            conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/update_form_status/<int:form_id>", methods=["POST"])
def update_form_status(form_id):
    new_status = request.form.get("status", "Signed / On File").strip()
    with get_db() as conn:
        conn.execute("UPDATE physician_forms SET status = ? WHERE id = ?", (new_status, form_id))
        conn.commit()
    return redirect(url_for("dashboard"))


@app.route("/export_pdf")
def export_pdf():
    target_date = datetime.now().strftime("%Y-%m-%d")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Oregon Adult Foster Home — Daily Compliance & Care Report ({target_date})", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    with get_db() as conn:
        logs = conn.execute("""
            SELECT r.name, r.room_number, e.medication, e.dosage, e.administered_by, e.timestamp
            FROM emar_logs e
            JOIN residents r ON e.resident_id = r.id
            ORDER BY e.id DESC
        """).fetchall()
        notes = conn.execute("""
            SELECT shift_window, author_name, note_text, timestamp
            FROM shift_notes
            ORDER BY id DESC
        """).fetchall()
        appts = conn.execute("""
            SELECT r.name, r.room_number, a.provider_name, a.clinic_location, a.appt_date, a.appt_time, a.notes
            FROM appointments a
            JOIN residents r ON a.resident_id = r.id
            ORDER BY a.appt_date ASC, a.appt_time ASC
        """).fetchall()
        behaviors = conn.execute("""
            SELECT r.name, r.room_number, b.behavior_type, b.severity, b.trigger_notes, b.intervention, b.timestamp
            FROM behavior_logs b
            JOIN residents r ON b.resident_id = r.id
            ORDER BY b.id DESC
        """).fetchall()
        forms = conn.execute("""
            SELECT r.name, r.room_number, f.form_title, f.provider_name, f.due_date, f.status, f.notes
            FROM physician_forms f
            JOIN residents r ON f.resident_id = r.id
            ORDER BY f.id DESC
        """).fetchall()

    elements.append(Paragraph("Medication Administration Records (eMAR)", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    table_data = [["Resident", "Room", "Medication", "Dosage", "Caregiver", "Time Recorded"]]
    for row in logs:
        table_data.append([row["name"], row["room_number"], row["medication"], row["dosage"], row["administered_by"], row["timestamp"]])
    if len(table_data) == 1:
        table_data.append(["No records", "-", "-", "-", "-", "-"])

    table = Table(table_data, colWidths=[110, 45, 110, 70, 85, 110])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#065F46")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Scheduled Doctor Appointments", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    if appts:
        for a in appts:
            extra = f" — {a['notes']}" if a["notes"] else ""
            elements.append(Paragraph(
                f"<b>{a['appt_date']} at {a['appt_time']}</b>: {a['name']} (Room {a['room_number']}) with {a['provider_name']} ({a['clinic_location']}){extra}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("No appointments scheduled.", styles["Normal"]))

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Behavior Tracking Log", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    if behaviors:
        for b in behaviors:
            trig = f" | Trigger: {b['trigger_notes']}" if b["trigger_notes"] else ""
            interv = f" | Intervention: {b['intervention']}" if b["intervention"] else ""
            elements.append(Paragraph(
                f"<b>{b['name']} (Room {b['room_number']})</b> — {b['behavior_type']} [{b['severity']}] ({b['timestamp']}){trig}{interv}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("No behavior logs recorded.", styles["Normal"]))

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Physician Forms & Orders", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    if forms:
        for f in forms:
            due = f" | Due: {f['due_date']}" if f["due_date"] else ""
            fnotes = f" — {f['notes']}" if f["notes"] else ""
            elements.append(Paragraph(
                f"<b>{f['form_title']}</b> [{f['status']}] for {f['name']} (Room {f['room_number']}) • Provider: {f['provider_name']}{due}{fnotes}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("No physician forms tracked.", styles["Normal"]))

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Caregiver Shift Notes", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    if notes:
        for n in notes:
            elements.append(Paragraph(
                f"<b>{n['shift_window']}</b> — {n['author_name']} ({n['timestamp']}): {n['note_text']}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 4))
    else:
        elements.append(Paragraph("No shift notes recorded for today.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"AFH_Compliance_Report_{target_date}.pdf", mimetype="application/pdf")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
