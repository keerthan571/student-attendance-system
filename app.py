from flask import Flask, render_template, request, redirect, url_for
import oracledb, qrcode, os

app = Flask(__name__)

# Ensure static folder exists for QR codes
if not os.path.exists("static"):
    os.makedirs("static")

# -------------------------
# Database Connection
# -------------------------
def get_db():
    # ⚠️ Change service_name if your Oracle is 11g XE → use "XE"
    dsn = oracledb.makedsn("localhost", 1521, service_name="XEPDB1")
    conn = oracledb.connect(
        user="attendance_user",
        password="attendance_pass",
        dsn=dsn
    )
    return conn

# -------------------------
# Home Page
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -------------------------
# Add Student
# -------------------------
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        name = request.form["name"].strip()
        usn = request.form["usn"].strip()

        conn = get_db()
        cur = conn.cursor()

        # Check if USN already exists
        cur.execute("SELECT COUNT(*) FROM students WHERE usn=:1", (usn,))
        count = cur.fetchone()[0]

        if count > 0:
            conn.close()
            return "❌ Error: USN already exists!"

        # Insert student (requires student_seq created in Oracle)
        cur.execute(
            """
            INSERT INTO students (student_id, name, usn, qr_code) 
            VALUES (student_seq.NEXTVAL, :1, :2, NULL)
            """,
            (name, usn)
        )
        conn.commit()

        # Generate QR Code
        qr_data = f"{usn}"
        qr_img = qrcode.make(qr_data)
        qr_filename = f"{usn}.png"
        qr_path = os.path.join("static", qr_filename)
        qr_img.save(qr_path)

        # Update student with QR code filename (not full path)
        cur.execute("UPDATE students SET qr_code=:1 WHERE usn=:2", (qr_filename, usn))
        conn.commit()

        conn.close()
        return redirect(url_for("students"))

    return render_template("add_student.html")

# -------------------------
# View All Students + Delete
# -------------------------
@app.route("/students")
def students():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT student_id, name, usn, qr_code FROM students ORDER BY student_id")
    students = cur.fetchall()
    conn.close()
    return render_template("students.html", students=students)

@app.route("/delete_student/<int:student_id>")
def delete_student(student_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE student_id=:1", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("students"))

# -------------------------
# View Attendance
# -------------------------
@app.route("/attendance")
def view_attendance():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.name, s.usn, a.date_attended, a.status
        FROM students s
        LEFT JOIN attendance1 a ON s.student_id = a.student_id
    """)
    records = cur.fetchall()
    conn.close()
    return render_template("view_attendance.html", records=records)
# Mark Attendance
@app.route("/mark_attendance_multi")
def mark_attendance_multi():
    import cv2
    from pyzbar.pyzbar import decode

    conn = get_db()
    cur = conn.cursor()

    marked_usn = set()  # Track already marked in session

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Cannot open webcam"

    print("📷 Scanning QR codes. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        for barcode in decode(frame):
            usn = barcode.data.decode('utf-8')

            if usn not in marked_usn:
                # Get student_id
                cur.execute("SELECT student_id FROM students WHERE usn=:1", [usn])
                student = cur.fetchone()
                if student:
                    student_id = student[0]

                    # Check if already marked today
                    cur.execute("""
                        SELECT COUNT(*) FROM attendance1
                        WHERE student_id=:1 AND TRUNC(date_attended)=TRUNC(SYSDATE)
                    """, [student_id])
                    already_marked = cur.fetchone()[0]

                    if already_marked == 0:
                        cur.execute("INSERT INTO attendance1 (student_id) VALUES (:1)", [student_id])
                        conn.commit()
                        print(f"✅ Attendance marked for {usn}")
                        marked_usn.add(usn)
                    else:
                        print(f"ℹ️ Already marked for {usn}")

            # Draw rectangle around QR
            x, y, w, h = barcode.rect.left, barcode.rect.top, barcode.rect.width, barcode.rect.height
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, usn, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        cv2.imshow("Scan QR - Press 'q' to Quit", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    conn.close()
    return f"Attendance session finished. {len(marked_usn)} students marked."

# -------------------------
# Run Flask App
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
