import io
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file
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

    today_display = datetime.now().strftime("%A, %b %d, %Y")
    return render_template(
        "dashboard.html",
        residents=residents,
        emar_logs=emar_logs,
        alerts=alerts,
        shift_notes=shift_notes,
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


@app.route("/export_pdf")
def export_pdf():
    target_date = datetime.now().strftime("%Y-%m-%d")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Oregon Adult Foster Home — Daily eMAR & Shift Report ({target_date})", styles["Heading1"]))
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

    elements.append(Spacer(1, 18))
    elements.append(Paragraph("Caregiver Shift Notes", styles["Heading2"]))
    elements.append(Spacer(1, 8))

    if notes:
        for n in notes:
            elements.append(Paragraph(
                f"<b>{n['shift_window']}</b> — {n['author_name']} ({n['timestamp']}): {n['note_text']}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 6))
    else:
        elements.append(Paragraph("No shift notes recorded for today.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"AFH_Compliance_Report_{target_date}.pdf", mimetype="application/pdf")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
