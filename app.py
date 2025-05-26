# main.py - Phiên bản đã sửa hoàn chỉnh: giữ notes và files sau restart

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
import sqlite3
import os
import datetime
import face_recognition
import csv

app = Flask(__name__)
app.secret_key = 'supersecretkey'

UPLOAD_FOLDER = 'uploads'
RECEIVED_FOLDER = 'received_images'
KNOWN_FACES_DIR = 'known_faces'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RECEIVED_FOLDER, exist_ok=True)

# Database setup
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    mssv TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    fullname TEXT NOT NULL
                )''')
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (mssv, password, fullname) VALUES ('admin', 'admin', 'Administrator')")
        c.execute("INSERT INTO users (mssv, password, fullname) VALUES ('23521670', '123456', 'Nguyễn Thị Lệ Trúc')")
        conn.commit()
    conn.close()

init_db()

# Load known faces
known_face_encodings = []
known_face_names = []
for filename in os.listdir(KNOWN_FACES_DIR):
    if filename.lower().endswith(('.jpg', '.png')):
        img = face_recognition.load_image_file(os.path.join(KNOWN_FACES_DIR, filename))
        encoding = face_recognition.face_encodings(img)
        if encoding:
            known_face_encodings.append(encoding[0])
            known_face_names.append(os.path.splitext(filename)[0])
print(f"[INFO] Loaded {len(known_face_encodings)} faces from '{KNOWN_FACES_DIR}' folder.")

# Load existing notes if available
notes = []
if os.path.exists('notes.txt'):
    with open('notes.txt', 'r', encoding='utf-8') as f:
        notes = [line.strip() for line in f if line.strip()]

@app.route('/upload', methods=['POST'])
def upload_image():
    if request.data:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{now}.jpg"
        filepath = os.path.join(RECEIVED_FOLDER, filename)

        with open(filepath, 'wb') as f:
            f.write(request.data)

        image = face_recognition.load_image_file(filepath)
        face_locations = face_recognition.face_locations(image)
        face_encodings = face_recognition.face_encodings(image, face_locations)

        recognized_names = []

        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
            name = "Unknown"
            if True in matches:
                first_match_index = matches.index(True)
                name = known_face_names[first_match_index]
            recognized_names.append(name)

        with open('attendance.csv', mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            for name in recognized_names:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([now, name, "Đã điểm danh"])

        return jsonify({"recognized": recognized_names}), 200
    return "No image received", 400

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT password, fullname FROM users WHERE mssv = ?', (username,))
        user = c.fetchone()
        conn.close()
        if user and user[0] == password:
            session['user'] = username
            session['role'] = 'admin' if username == 'admin' else 'student'
            session['name'] = user[1]
            if session['role'] == 'admin':
                return redirect(url_for('admin_page'))
            else:
                return redirect(url_for('student_page'))
        else:
            flash('Sai tài khoản hoặc mật khẩu!')
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_page():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'note' in request.form and request.form['note'].strip() != '':
            note = request.form['note']
            notes.append(note)
            with open('notes.txt', 'a', encoding='utf-8') as f:
                f.write(note + '\n')
            flash('Đã gửi thông báo thành công!')
        elif 'file' in request.files:
            file = request.files['file']
            if file and file.filename != '':
                filename = file.filename
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                flash('Đã upload file thành công!')

    attendance_records = []
    if os.path.exists('attendance.csv'):
        with open('attendance.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            attendance_records = list(reader)

    images = os.listdir(RECEIVED_FOLDER)
    images.sort(reverse=True)

    files = os.listdir(UPLOAD_FOLDER)
    files.sort(reverse=True)

    return render_template('admin.html', notes=notes, files=files, name=session.get('name'), attendance=attendance_records, images=images)

@app.route('/student')
def student_page():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    files = os.listdir(UPLOAD_FOLDER)
    files.sort(reverse=True)

    return render_template('student.html', notes=notes, files=files, name=session.get('name'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/received_images/<filename>')
def received_file(filename):
    return send_from_directory(RECEIVED_FOLDER, filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)