from flask import Flask, render_template, request, redirect
import oracledb, qrcode, os

app = Flask(__name__)

# Ensure static folder exists for QR codes
if not os.path.exists("static"):
    os.makedirs("static")

# DB connection
def get_db():
    dsn = oracledb.makedsn("localhost", 1521, service_name="XEPDB1")  # Use your PDB
    conn = oracledb.connect(
        user="attendance_user",
        password="attendance_pass",
        dsn=dsn
    )
    return conn

# Home page
@app.route("/")
def index():
    return render_template("index.html")

# Add student
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

        # Insert student using sequence
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
        return redirect("/")

    return render_template("add_student.html")

# View attendance
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

if __name__ == "__main__":
    app.run(debug=True)
