import cv2
from pyzbar import pyzbar
import oracledb
import datetime


# DB Connection
def get_db():
    dsn = oracledb.makedsn("localhost", 1521, service_name="XE")
    conn = oracledb.connect(user="attendance_user", password="attendance_pass", dsn=dsn)
    return conn


# Mark attendance
def mark_attendance(usn, faculty_id=1):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT student_id FROM students WHERE usn=:1", (usn,))
    student = cur.fetchone()
    
    if student:
        student_id = student[0]
        today = datetime.date.today()
        
        cur.execute(
            "INSERT INTO attendance (attendance_id, student_id, faculty_id, attendance_date, status) "
            "VALUES (attendance_seq.NEXTVAL, :1, :2, :3, 'Present')",
            (student_id, faculty_id, today)
        )
        
        conn.commit()
        print(f"✅ Marked Present: {usn}")
    
    else:
        print(f"❌ Student with USN {usn} not found!")
    
    conn.close()


# Start scanning
def scan_qr():
    cap = cv2.VideoCapture(0)
    print("📷 Show QR code. Press 'q' to quit.")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        decoded_objs = pyzbar.decode(frame)
        for obj in decoded_objs:
            usn = obj.data.decode("utf-8")
            mark_attendance(usn)

        cv2.imshow("QR Scanner", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    scan_qr()
