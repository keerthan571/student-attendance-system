import cv2
from pyzbar.pyzbar import decode
from datetime import date

@app.route("/mark_attendance_multi")
def mark_attendance_multi():
    conn = get_db()
    cur = conn.cursor()

    # Keep track of students already marked in this session
    marked_usn = set()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Cannot open webcam"

    print("📷 Scanning QR codes. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Decode QR codes
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
                        print(f"ℹ️ Attendance already marked for {usn}")

            # Draw rectangle around QR
            x, y, w, h = barcode.rect.left, barcode.rect.top, barcode.rect.width, barcode.rect.height
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, usn, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # Display
        cv2.imshow("Scan QR - Press 'q' to Quit", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    conn.close()
    return f"Attendance session finished. {len(marked_usn)} students marked."
