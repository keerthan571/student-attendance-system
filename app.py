from flask import Flask, render_template, request, redirect, url_for
import oracledb, qrcode, os

app = Flask(__name__)

# Ensure static folder exists for QR codes
if not os.path.exists("static"):
    os.makedirs("static")

# DB connection
def get_db():
    dsn = oracledb.makedsn("localhost", 1521, service_name="XEPDB1")  # Use your PDB or XE
    conn = oracledb.connect(
        user="attendance_user",
        password="attendance_pass",
        dsn=dsn
    )
    return conn

# -------------------------
# Home page
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -------------------------
# Add student
# -------------------------
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        name = request.form["name"]
        usn = request.form["usn"]

        conn = get_db()
        cur = conn.cursor()

        # Check if USN already exists
        cur.execute("SELECT COUNT(*) FROM students WHERE usn=:1", (usn,))
        count = cur.fetchone()[0]

        if count > 0:
            conn.close()
            return "Error: USN already exists!"

        # Insert student (assuming you created student_seq in Oracle DB)
        cur.execute(
            "INSERT INTO students (student_id, name, usn, qr_code) VALUES (student_seq.NEXTVAL, :1, :2, NULL)",
            (name, usn)
        )
        conn.commit()

        # Generate QR code
        qr_data = f"{usn}"
        qr_img = qrcode.make(qr_data)
        qr_path = f"static/{usn}.png"
        qr_img.save(qr_path)

        # Update student with QR code path
        cur.execute("UPDATE students SET qr_code=:1 WHERE usn=:2", (qr_path, usn))
        conn.commit()

        conn.close()
        return redirect("/students")

    return render_template("add_student.html")

# -------------------------
# View all students + delete option
# -------------------------
@app.route("/students")
def students():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT student_id, name, usn, qr_code FROM students")
    students = cur.fetchall()
    conn.close()
    return render_template("students.html", students=students)

# Delete student by ID
@app.route("/delete_student/<int:student_id>")
def delete_student(student_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE student_id = :1", [student_id])
    conn.commit()
    conn.close()
    return redirect(url_for("students"))

# -------------------------
# View attendance
# -------------------------
@app.route("/attendance")
def view_attendance():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.name, s.usn, a.date_attended, a.status
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id
    """)
    records = cur.fetchall()
    conn.close()
    return render_template("view_attendance.html", records=records)

# -------------------------
# Run the Flask app
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
