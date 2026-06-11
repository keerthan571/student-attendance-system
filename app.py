from flask import Flask, render_template, request, redirect, flash, session
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
from urllib.parse import unquote
from werkzeug.security import generate_password_hash
from openpyxl import Workbook
from flask import send_file
from io import BytesIO
import oracledb
import qrcode
import os
from io import BytesIO

from flask import send_file

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from flask import jsonify
from urllib.parse import unquote

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")


# -----------------------------
# Database Connection
# -----------------------------
def get_db():
    dsn = oracledb.makedsn(
        os.getenv("DB_HOST"),
        int(os.getenv("DB_PORT")),
        service_name=os.getenv("DB_SERVICE")
    )

    return oracledb.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dsn=dsn
    )


# -----------------------------
# Home Page / Dashboard
# -----------------------------
@app.route("/")
def index():

    # Check login
    if "admin" not in session:
        return redirect("/login")

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        # -----------------------------
        # Total Students
        # -----------------------------
        cur.execute("""
            SELECT COUNT(*)
            FROM students
        """)

        total_students = cur.fetchone()[0]

        # -----------------------------
        # Total Attendance Records
        # -----------------------------
        cur.execute("""
            SELECT COUNT(*)
            FROM attendance
        """)

        total_attendance = cur.fetchone()[0]

        # -----------------------------
        # Today's Attendance
        # -----------------------------
        cur.execute("""
            SELECT COUNT(*)
            FROM attendance
            WHERE TRUNC(date_attended) = TRUNC(SYSDATE)
        """)

        today_attendance = cur.fetchone()[0]

        # -----------------------------
        # Attendance Percentage
        # -----------------------------
        if total_students > 0:

            attendance_percentage = round(

                (today_attendance / total_students) * 100,

                2

            )

        else:

            attendance_percentage = 0

        # -----------------------------
        # Recent Attendance
        # -----------------------------
        cur.execute("""
            SELECT
                s.name,
                s.usn,
                a.date_attended,
                a.status
            FROM students s
            JOIN attendance a
                ON s.student_id = a.student_id
            ORDER BY a.date_attended DESC
            FETCH FIRST 5 ROWS ONLY
        """)

        recent = cur.fetchall()

        # -----------------------------
        # Monthly Attendance Data
        # (Last 6 Months)
        # -----------------------------
        cur.execute("""
            SELECT
                TO_CHAR(date_attended, 'Mon'),
                COUNT(*)
            FROM attendance
            WHERE date_attended >= ADD_MONTHS(TRUNC(SYSDATE), -5)
            GROUP BY
                TO_CHAR(date_attended, 'Mon'),
                TO_CHAR(date_attended, 'MM')
            ORDER BY
                TO_CHAR(date_attended, 'MM')
        """)

        monthly_data = cur.fetchall()

        chart_labels = [row[0] for row in monthly_data]
        chart_values = [row[1] for row in monthly_data]

        return render_template(

            "index.html",

            total_students=total_students,

            total_attendance=total_attendance,

            today_attendance=today_attendance,

            attendance_percentage=attendance_percentage,

            recent=recent,

            chart_labels=chart_labels,

            chart_values=chart_values

        )

    except Exception as e:

        flash(

            f"Dashboard Error: {str(e)}",

            "danger"

        )

        return render_template(

            "index.html",

            total_students=0,

            total_attendance=0,

            today_attendance=0,

            attendance_percentage=0,

            recent=[],

            chart_labels=[],

            chart_values=[]

        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()
#------------------------------
# Login
#------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if "admin" in session:
        return redirect("/")

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        conn = None
        cur = None

        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute(
                "SELECT password FROM admins WHERE username = :1",
                (username,)
            )

            row = cur.fetchone()

            if row and check_password_hash(row[0], password):
                session["admin"] = username
                flash("Login successful!", "success")
                return redirect("/")

            flash("Invalid username or password!", "danger")

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    return render_template("login.html")

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out successfully!", "success")

    return redirect("/login")

# -----------------------------
# Signup
# -----------------------------


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "admin" not in session:
        flash("Access denied!", "danger")
        return redirect("/login")

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        # Check empty fields
        if not username or not password or not confirm:
            flash("All fields are required!", "danger")
            return redirect("/signup")

        # Check password match
        if password != confirm:
            flash("Passwords do not match!", "danger")
            return redirect("/signup")

        conn = None
        cur = None

        try:

            conn = get_db()
            cur = conn.cursor()

            # Check if username already exists
            cur.execute(
                """
                SELECT COUNT(*)
                FROM admins
                WHERE username = :1
                """,
                (username,)
            )

            count = cur.fetchone()[0]

            if count > 0:
                flash("Username already exists!", "warning")
                return redirect("/signup")

            # Hash password
            hashed_password = generate_password_hash(password)

            # Insert new admin
            cur.execute(
                """
                INSERT INTO admins (username, password)
                VALUES (:1, :2)
                """,
                (username, hashed_password)
            )

            conn.commit()

            flash("Account created successfully! Please login.", "success")

            return redirect("/login")

        except Exception as e:

            if conn:
                conn.rollback()

            flash(f"Error: {str(e)}", "danger")

            return redirect("/signup")

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    return render_template("signup.html")

@app.route("/scan")

def scan():

    if "admin" not in session:
        return redirect("/login")

    return render_template("scan.html")

# -----------------------------
# Add Student
# -----------------------------

@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if "admin" not in session:
        return redirect("/login")
    if request.method == "POST":

        name = request.form["name"].strip()
        usn = request.form["usn"].strip().upper()

        if not name or not usn:
            flash("Name and USN cannot be empty!", "danger")
            return redirect("/add_student")

        conn = None
        cur = None

        try:

            conn = get_db()
            cur = conn.cursor()

            # Check duplicate USN
            cur.execute(
                "SELECT COUNT(*) FROM students WHERE usn=:1",
                (usn,)
            )

            count = cur.fetchone()[0]

            if count > 0:
                flash("USN already exists!", "warning")
                return redirect("/add_student")

            # Insert student
            cur.execute("""
                INSERT INTO students
                (student_id, name, usn, qr_code)
                VALUES
                (student_seq.NEXTVAL, :1, :2, NULL)
            """, (name, usn))

            conn.commit()

            # Create QR folder if not exists
            
            qr_folder = os.path.join(app.static_folder, "qrcodes")
            os.makedirs(qr_folder, exist_ok=True)

            file_path = os.path.join(qr_folder, f"{usn}.png")

            qr_data = f"STUDENT:{usn}"

            qr = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=20,
                border=4
            )

            qr.add_data(qr_data)
            qr.make(fit=True)

            img = qr.make_image(
                fill_color="black",
                back_color="white"
            )

            img.save(file_path)

            db_path = f"qrcodes/{usn}.png"

            cur.execute(
                """
                UPDATE students
                SET qr_code=:1
                WHERE usn=:2
                """,
                (db_path, usn)
            )
            conn.commit()

            flash("Student added successfully!", "success")

            return redirect("/")

        except Exception as e:

            if conn:
                conn.rollback()

            flash(f"Error: {str(e)}", "danger")
            return redirect("/add_student")

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    return render_template("add_student.html")

@app.route("/mark_attendance/<path:usn>")
def mark_attendance(usn):
    

    if "admin" not in session:
        return redirect("/login")

    usn = unquote(usn)

    if not usn.startswith("STUDENT:"):
        flash("Invalid QR Code", "danger")
        return redirect("/scan")

    usn = usn.replace("STUDENT:", "", 1)
    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        # Find student
        cur.execute("""
            SELECT student_id, name
            FROM students
            WHERE usn = :1
        """, (usn,))

        student = cur.fetchone()

        if student is None:
            flash("Student not found!", "danger")
            return redirect("/scan")

        student_id = student[0]
        student_name = student[1]

        # Prevent duplicate attendance
        cur.execute("""
            SELECT COUNT(*)
            FROM attendance
            WHERE student_id = :1
            AND TRUNC(date_attended) = TRUNC(SYSDATE)
        """, (student_id,))

        already = cur.fetchone()[0]

        if already > 0:
            flash(
                f"{student_name} has already marked attendance today.",
                "warning"
            )
            return redirect("/")

        # Mark attendance
        cur.execute("""
            INSERT INTO attendance
            (student_id, date_attended, status)
            VALUES
            (:1, SYSDATE, 'Present')
        """, (student_id,))

        conn.commit()

        flash(
            f"Attendance marked successfully for {student_name}.",
            "success"
        )

    except Exception as e:

        if conn:
            conn.rollback()

        flash(str(e), "danger")

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

    return redirect("/")

@app.route("/api/mark_attendance/<path:usn>")
def api_mark_attendance(usn):

    if "admin" not in session:
        return jsonify({
            "success": False,
            "message": "Unauthorized"
        })

    usn = unquote(usn)

    if not usn.startswith("STUDENT:"):
        return jsonify({
            "success": False,
            "message": "Invalid QR Code"
        })

    usn = usn.replace("STUDENT:", "", 1)

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        # Find student
        cur.execute("""
            SELECT student_id, name
            FROM students
            WHERE usn = :1
        """, (usn,))

        student = cur.fetchone()

        if student is None:

            return jsonify({
                "success": False,
                "message": "Student not found"
            })

        student_id = student[0]
        student_name = student[1]

        # Check duplicate attendance
        cur.execute("""
            SELECT COUNT(*)
            FROM attendance
            WHERE student_id = :1
            AND TRUNC(date_attended)=TRUNC(SYSDATE)
        """, (student_id,))

        already = cur.fetchone()[0]

        if already > 0:

            return jsonify({
                "success": False,
                "message": f"{student_name} already marked today"
            })

        # Mark attendance
        cur.execute("""
            INSERT INTO attendance
            (
                student_id,
                date_attended,
                status
            )
            VALUES
            (
                :1,
                SYSDATE,
                'Present'
            )
        """, (student_id,))

        conn.commit()

        return jsonify({

            "success": True,

            "message":
            f"{student_name} attendance marked"

        })

    except Exception as e:

        if conn:
            conn.rollback()

        return jsonify({

            "success": False,

            "message": str(e)

        })

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

@app.route("/students")
def students():

    if "admin" not in session:
        return redirect("/login")

    search = request.args.get("search", "").strip()

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        if search:

            cur.execute("""

                SELECT
                    student_id,
                    name,
                    usn,
                    qr_code

                FROM students

                WHERE

                    UPPER(name) LIKE UPPER(:1)

                    OR

                    UPPER(usn) LIKE UPPER(:1)

                ORDER BY name

            """, (f"%{search}%",))

        else:

            cur.execute("""

                SELECT
                    student_id,
                    name,
                    usn,
                    qr_code

                FROM students

                ORDER BY name

            """)

        students = cur.fetchall()

        return render_template(

            "students.html",

            students=students,

            search=search

        )
    except Exception as e:

        flash(f"Database Error: {str(e)}", "danger")
        return redirect("/")

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()
            
@app.route("/delete_student/<int:id>", methods=["POST"])
def delete_student(id):

    if "admin" not in session:
        return redirect("/login")

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        # Get QR code path
        cur.execute(
            """
            SELECT qr_code
            FROM students
            WHERE student_id = :1
            """,
            (id,)
        )

        row = cur.fetchone()

        # Delete QR image file
        if row and row[0]:

            file_path = os.path.join(
                app.static_folder,
                row[0]
            )

            if os.path.exists(file_path):
                os.remove(file_path)

        # Delete attendance records first
        cur.execute(
            """
            DELETE FROM attendance
            WHERE student_id = :1
            """,
            (id,)
        )

        # Delete student record
        cur.execute(
            """
            DELETE FROM students
            WHERE student_id = :1
            """,
            (id,)
        )

        conn.commit()

        flash(
            "Student deleted successfully!",
            "success"
        )

    except Exception as e:

        if conn:
            conn.rollback()

        flash(
            f"Error deleting student: {str(e)}",
            "danger"
        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

    return redirect("/students")
#------------------------------
# Edit Student
#------------------------------
@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
def edit_student(id):

    if "admin" not in session:
        return redirect("/login")

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        # -----------------------------
        # GET Request
        # -----------------------------
        if request.method == "GET":

            cur.execute("""
                SELECT
                    student_id,
                    name,
                    usn,
                    qr_code
                FROM students
                WHERE student_id = :1
            """, (id,))

            student = cur.fetchone()

            if not student:
                flash("Student not found.", "danger")
                return redirect("/students")

            return render_template(
                "edit_student.html",
                student=student
            )

        # -----------------------------
        # POST Request
        # -----------------------------

        new_name = request.form["name"].strip()
        new_usn = request.form["usn"].strip().upper()

        # Get existing student
        cur.execute("""
            SELECT
                name,
                usn,
                qr_code
            FROM students
            WHERE student_id = :1
        """, (id,))

        old_student = cur.fetchone()

        if not old_student:

            flash("Student not found.", "danger")
            return redirect("/students")

        old_usn = old_student[1]
        old_qr = old_student[2]

        # Check duplicate USN
        cur.execute("""
            SELECT COUNT(*)
            FROM students
            WHERE usn = :1
            AND student_id <> :2
        """, (new_usn, id))

        duplicate = cur.fetchone()[0]

        if duplicate > 0:

            flash("USN already exists.", "warning")

            return redirect(f"/edit_student/{id}")

        # If USN changed, regenerate QR

        if old_usn != new_usn:

            # Delete old QR

            if old_qr:

                old_path = os.path.join(
                    app.static_folder,
                    old_qr
                )

                if os.path.exists(old_path):
                    os.remove(old_path)

            # Create QR folder

            qr_folder = os.path.join(
                app.static_folder,
                "qrcodes"
            )

            os.makedirs(
                qr_folder,
                exist_ok=True
            )

            # Generate new QR

            file_path = os.path.join(
                qr_folder,
                f"{new_usn}.png"
            )

            qr_data = f"STUDENT:{new_usn}"

            qr = qrcode.make(qr_data)

            qr.save(file_path)

            qr_db_path = f"qrcodes/{new_usn}.png"

        else:

            qr_db_path = old_qr

        # Update student

        cur.execute("""
            UPDATE students
            SET
                name = :1,
                usn = :2,
                qr_code = :3
            WHERE student_id = :4
        """, (

            new_name,
            new_usn,
            qr_db_path,
            id

        ))

        conn.commit()

        flash(
            "Student updated successfully!",
            "success"
        )

        return redirect("/students")

    except Exception as e:

        if conn:
            conn.rollback()

        flash(
            f"Error: {str(e)}",
            "danger"
        )

        return redirect("/students")

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()
# -----------------------------
# View Attendance
# -----------------------------
@app.route("/attendance")
def view_attendance():

    # Check login
    if "admin" not in session:
        return redirect("/login")

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                s.name,
                s.usn,
                a.date_attended,
                a.status
            FROM students s
            JOIN attendance a
                ON s.student_id = a.student_id
            ORDER BY a.date_attended DESC
        """)

        records = cur.fetchall()

        return render_template(
            "view_attendance.html",
            records=records
        )

    except Exception as e:

        flash(
            f"Database Error: {str(e)}",
            "danger"
        )

        return redirect("/")

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

@app.route("/export/pdf")
def export_pdf():

    if "admin" not in session:
        return redirect("/login")

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                s.name,
                s.usn,
                a.date_attended,
                a.status
            FROM students s
            JOIN attendance a
                ON s.student_id = a.student_id
            ORDER BY a.date_attended DESC
        """)

        records = cur.fetchall()

        buffer = BytesIO()

        doc = SimpleDocTemplate(buffer)

        styles = getSampleStyleSheet()

        elements = []

        # Title
        elements.append(
            Paragraph(
                "<b>Student Attendance Report</b>",
                styles["Title"]
            )
        )

        elements.append(
            Paragraph(
                "Generated by Student Attendance Management System",
                styles["Normal"]
            )
        )

        elements.append(Spacer(1, 0.3 * inch))

        # Table Data

        data = [

            ["Name", "USN", "Date", "Status"]

        ]

        for row in records:

            data.append([

                row[0],

                row[1],

                row[2].strftime("%d-%m-%Y %H:%M"),

                row[3]

            ])

        table = Table(data)

        table.setStyle(

            TableStyle([

                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),

                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

                ("GRID", (0, 0), (-1, -1), 1, colors.grey),

                ("ALIGN", (0, 0), (-1, -1), "CENTER"),

                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),

                ("BOTTOMPADDING", (0, 0), (-1, 0), 8)

            ])

        )

        elements.append(table)

        doc.build(elements)

        buffer.seek(0)

        return send_file(

            buffer,

            as_attachment=True,

            download_name="Attendance_Report.pdf",

            mimetype="application/pdf"

        )

    except Exception as e:

        flash(str(e), "danger")

        return redirect("/attendance")

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

@app.route("/export/excel")
def export_excel():

    if "admin" not in session:
        return redirect("/login")

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                s.name,
                s.usn,
                a.date_attended,
                a.status
            FROM students s
            JOIN attendance a
            ON s.student_id = a.student_id
            ORDER BY a.date_attended DESC
        """)

        records = cur.fetchall()

        wb = Workbook()
        ws = wb.active
        ws.title = "Attendance"

        # Header
        ws.append([
            "Student Name",
            "USN",
            "Date",
            "Status"
        ])

        # Bold header
        from openpyxl.styles import Font

        for cell in ws[1]:
            cell.font = Font(bold=True)

        # Data
        for row in records:
            ws.append(row)

        # Auto width
        for column in ws.columns:

            max_length = 0

            column_letter = column[0].column_letter

            for cell in column:

                try:

                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))

                except:
                    pass

            ws.column_dimensions[column_letter].width = max_length + 3

        output = BytesIO()

        wb.save(output)

        output.seek(0)

        return send_file(

            output,

            download_name="Attendance_Report.xlsx",

            as_attachment=True,

            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()
            
@app.route("/student/<int:student_id>")
def student_profile(student_id):

    if "admin" not in session:
        return redirect("/login")

    conn = None
    cur = None

    try:

        conn = get_db()
        cur = conn.cursor()

        # Student details
        cur.execute("""
            SELECT
                student_id,
                name,
                usn,
                qr_code
            FROM students
            WHERE student_id = :1
        """, (student_id,))

        student = cur.fetchone()

        if not student:
            flash("Student not found!", "danger")
            return redirect("/students")

        # Present count
        cur.execute("""
            SELECT COUNT(*)
            FROM attendance
            WHERE student_id = :1
            AND status = 'Present'
        """, (student_id,))

        present = cur.fetchone()[0]

        # Total attendance sessions
        cur.execute("""
            SELECT COUNT(DISTINCT TRUNC(date_attended))
            FROM attendance
        """)

        total_classes = cur.fetchone()[0]

        absent = max(total_classes - present, 0)

        percentage = 0

        if total_classes > 0:
            percentage = round(
                (present / total_classes) * 100,
                2
            )

        return render_template(

            "student_profile.html",

            student=student,

            present=present,

            absent=absent,

            total=total_classes,

            percentage=percentage

        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()
# -----------------------------
# Run Application
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)