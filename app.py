import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import bcrypt
from flask import Flask, flash, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / "classroom.db"

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = "spirit-university-classroom-2026-change-this"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

APP_NAME = "Spirit University"

ROOMS = [
    ("Room A101", "Smart Classroom", 40, "room1.jpg"),
    ("Room B202", "Lecture Hall", 60, "room2.jpg"),
    ("Computer Lab C301", "Computer Lab", 36, "room3.jpg"),
    ("Science Lab D104", "Science Laboratory", 32, "room4.jpg"),
    ("Auditorium E001", "Auditorium", 180, "room5.jpg"),
]

DEMO_USERS = [
    ("student@spirit.edu", "DINESH001", "2024BTCY001", "Student", "Student@123"),
    ("hello@spirit.edu", "FAC1001", "FAC1001", "Faculty", "Hello@726"),
    ("hi@spirit.edu", "ADM1001", "ADM1001", "Admin", "Hi@726"),
]


def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def password_ok(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except (ValueError, TypeError):
        return False


def init_db():
    con = get_db()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            student_id TEXT UNIQUE NOT NULL,
            prn TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Student','Faculty','Admin')),
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rooms (
            name TEXT PRIMARY KEY,
            room_type TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            image TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            room TEXT NOT NULL,
            purpose TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            enrollment_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # Backward-compatible migration for older databases.
    booking_columns = {row["name"] for row in con.execute("PRAGMA table_info(bookings)").fetchall()}
    if "enrollment_count" not in booking_columns:
        con.execute("ALTER TABLE bookings ADD COLUMN enrollment_count INTEGER NOT NULL DEFAULT 1")

    for room in ROOMS:
        con.execute(
            "INSERT OR IGNORE INTO rooms(name, room_type, capacity, image) VALUES (?, ?, ?, ?)",
            room,
        )

    for email, student_id, prn, role, password in DEMO_USERS:
        existing = con.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
        if existing:
            con.execute(
                "UPDATE users SET password_hash=?, role=?, student_id=?, prn=? WHERE id=?",
                (password_hash(password), role, student_id, prn, existing["id"]),
            )
        else:
            con.execute(
                """INSERT INTO users(email, student_id, prn, role, password_hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (email, student_id, prn, role, password_hash(password), datetime.now(timezone.utc).isoformat()),
            )
    con.commit()
    con.close()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    con = get_db()
    user = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    con.close()
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please sign in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or user["role"] not in roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def globals_for_templates():
    return {"app_name": APP_NAME, "current_user": current_user()}



PRE_REGISTERED_STUDENTS = [('Jai', '2024BTCY005'), ('Anil', '2024BTCY007'), ('Bharath', '2024BTEC009'), ('lithin', '2024BTCS001'), ('hari', '2024BTDS175')]
DEFAULT_STUDENT_PASSWORD = 'Spirit@123'

def seed_pre_registered_students():
    con = get_db()
    for name, prn in PRE_REGISTERED_STUDENTS:
        email = prn.lower() + "@spirit.edu"
        existing = con.execute(
            "SELECT id FROM users WHERE lower(prn)=lower(?) LIMIT 1", (prn,)
        ).fetchone()
        if existing:
            con.execute(
                "UPDATE users SET email=?, student_id=?, role='Student', password_hash=? WHERE id=?",
                (email, prn, password_hash(DEFAULT_STUDENT_PASSWORD), existing["id"]),
            )
        else:
            con.execute(
                """INSERT INTO users(email, student_id, prn, role, password_hash, created_at)
                   VALUES (?, ?, ?, 'Student', ?, ?)""",
                (email, prn, prn, password_hash(DEFAULT_STUDENT_PASSWORD),
                 datetime.now(timezone.utc).isoformat()),
            )
    con.commit()
    con.close()

@app.route("/")
def index():
    return render_template("index.html")nt_user() else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()
        remember = request.form.get("remember") == "on"

        con = get_db()
        user = con.execute(
            """SELECT * FROM users
               WHERE lower(email)=lower(?) OR lower(student_id)=lower(?) OR lower(prn)=lower(?)
               LIMIT 1""",
            (identifier, identifier, identifier),
        ).fetchone()

        # The five pre-registered students may also sign in using their names.
        if not user:
            name_to_prn = {name.lower(): prn for name, prn in PRE_REGISTERED_STUDENTS}
            prn_for_name = name_to_prn.get(identifier.lower())
            if prn_for_name:
                user = con.execute(
                    "SELECT * FROM users WHERE lower(prn)=lower(?) LIMIT 1",
                    (prn_for_name,),
                ).fetchone()
        con.close()

        # Keep the response generic so the page does not reveal whether the
        # identifier or password was the incorrect part.
        if not user or not password_ok(password, user["password_hash"]):
            flash("Invalid ID or Password.", "danger")
            return render_template("login.html")

        if role and role != user["role"]:
            flash("Invalid ID or Password.", "danger")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session.permanent = remember
        if remember:
            app.permanent_session_lifetime = 60 * 60 * 24 * 30

        flash(f"Welcome back, {user['role']}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        student_id = request.form.get("student_id", "").strip()
        prn = request.form.get("prn", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([email, student_id, prn, password, confirm_password]):
            flash("Please complete every registration field.", "danger")
            return render_template("register.html")

        if "@" not in email:
            flash("Please enter a valid university email.", "danger")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        con = get_db()
        existing = con.execute(
            """SELECT id FROM users
               WHERE lower(email)=lower(?) OR lower(student_id)=lower(?) OR lower(prn)=lower(?)
               LIMIT 1""",
            (email, student_id, prn),
        ).fetchone()

        if existing:
            con.close()
            flash("An account with that Email, Student ID, or PRN already exists.", "danger")
            return render_template("register.html")

        con.execute(
            """INSERT INTO users(email, student_id, prn, role, password_hash, created_at)
               VALUES (?, ?, ?, 'Student', ?, ?)""",
            (
                email,
                student_id,
                prn,
                password_hash(password),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        con.commit()
        con.close()

        flash("Account created successfully. You can now sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        # Prototype behavior: do not disclose whether an account exists.
        flash("If the account exists, password-reset instructions will be sent to the registered university email.", "success")
    return render_template("forgot_password.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user["role"] == "Faculty":
        return redirect(url_for("faculty_dashboard"))
    if user["role"] == "Admin":
        return redirect(url_for("admin_dashboard"))

    con = get_db()
    rooms = con.execute("SELECT * FROM rooms ORDER BY name").fetchall()
    bookings = con.execute(
        "SELECT * FROM bookings WHERE user_id=? ORDER BY booking_date, start_time",
        (user["id"],),
    ).fetchall()
    con.close()
    return render_template("dashboard.html", rooms=rooms, bookings=bookings)


@app.route("/faculty")
@login_required
@role_required("Faculty")
def faculty_dashboard():
    con = get_db()
    rooms = con.execute("SELECT * FROM rooms ORDER BY name").fetchall()
    bookings = con.execute(
        """SELECT b.*, u.email, u.student_id, u.prn, u.role,
                  r.capacity AS room_capacity,
                  (SELECT COALESCE(SUM(b2.enrollment_count), 0)
                     FROM bookings b2
                    WHERE b2.room=b.room
                      AND b2.booking_date=b.booking_date
                      AND b2.start_time < b.end_time
                      AND b2.end_time > b.start_time) AS current_enrollment
           FROM bookings b
           JOIN users u ON u.id=b.user_id
           JOIN rooms r ON r.name=b.room
           ORDER BY b.booking_date, b.start_time"""
    ).fetchall()
    con.close()
    return render_template("faculty.html", rooms=rooms, bookings=bookings)


@app.route("/admin")
@login_required
@role_required("Admin")
def admin_dashboard():
    con = get_db()
    users = con.execute("SELECT email, student_id, prn, role FROM users ORDER BY role, email").fetchall()
    rooms = con.execute("SELECT * FROM rooms ORDER BY name").fetchall()
    bookings = con.execute(
        """SELECT b.*, u.email, u.student_id, u.prn, u.role,
                  r.capacity AS room_capacity,
                  (SELECT COALESCE(SUM(b2.enrollment_count), 0)
                     FROM bookings b2
                    WHERE b2.room=b.room
                      AND b2.booking_date=b.booking_date
                      AND b2.start_time < b.end_time
                      AND b2.end_time > b.start_time) AS current_enrollment
           FROM bookings b
           JOIN users u ON u.id=b.user_id
           JOIN rooms r ON r.name=b.room
           ORDER BY b.booking_date, b.start_time"""
    ).fetchall()
    con.close()
    return render_template("admin.html", users=users, rooms=rooms, bookings=bookings)


@app.post("/book")
@login_required
@role_required("Student", "Faculty")
def book():
    user = current_user()
    room = request.form.get("room", "").strip()
    purpose = request.form.get("purpose", "").strip()
    booking_date = request.form.get("booking_date", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()

    try:
        enrollment_count = int(request.form.get("enrollment_count", "1"))
    except (TypeError, ValueError):
        enrollment_count = 0

    if not all([room, purpose, booking_date, start_time, end_time]):
        flash("Please complete every booking field.", "danger")
        return redirect(url_for("dashboard"))

    if enrollment_count < 1:
        flash("Number of students must be at least 1.", "danger")
        return redirect(url_for("dashboard"))

    if enrollment_count > 5:
        flash("You can book a maximum of 5 seats per reservation.", "danger")
        return redirect(url_for("dashboard"))

    try:
        start = datetime.strptime(f"{booking_date} {start_time}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{booking_date} {end_time}", "%Y-%m-%d %H:%M")
        if end <= start:
            raise ValueError
    except ValueError:
        flash("Choose a valid date and an end time after the start time.", "danger")
        return redirect(url_for("dashboard"))

    con = get_db()

    try:
        # BEGIN IMMEDIATE obtains SQLite's write lock before checking capacity.
        # This makes concurrent booking requests serialize safely: one request
        # completes the capacity check + insert before another can do the same.
        con.execute("BEGIN IMMEDIATE")

        room_row = con.execute(
            "SELECT name, capacity FROM rooms WHERE name=?", (room,)
        ).fetchone()

        if not room_row:
            con.rollback()
            flash("Invalid classroom selected.", "danger")
            return redirect(url_for("dashboard"))

        max_capacity = int(room_row["capacity"])

        if enrollment_count > max_capacity:
            con.rollback()
            flash(
                f"This classroom has a maximum capacity of {max_capacity} students.",
                "danger",
            )
            return redirect(url_for("dashboard"))

        # Sum all overlapping reservations. Because the transaction is locked,
        # two simultaneous requests cannot both claim the same remaining seats.
        current_enrollment_row = con.execute(
            """SELECT COALESCE(SUM(enrollment_count), 0) AS current_enrollment
               FROM bookings
               WHERE room=? AND booking_date=?
                 AND start_time < ? AND end_time > ?""",
            (room, booking_date, end_time, start_time),
        ).fetchone()

        current_enrollment = int(current_enrollment_row["current_enrollment"] or 0)
        remaining_capacity = max_capacity - current_enrollment

        if enrollment_count > remaining_capacity:
            con.rollback()
            flash(
                f"Booking unavailable: only {remaining_capacity} seat(s) remain "
                f"for this classroom and time.",
                "danger",
            )
            return redirect(url_for("dashboard"))

        con.execute(
            """INSERT INTO bookings(
                   user_id, room, purpose, booking_date,
                   start_time, end_time, enrollment_count, created_at
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user["id"],
                room,
                purpose,
                booking_date,
                start_time,
                end_time,
                enrollment_count,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        con.commit()
        flash(
            f"Classroom booked successfully for {enrollment_count} student(s). "
            f"{max_capacity - current_enrollment - enrollment_count} seat(s) remain.",
            "success",
        )
    except sqlite3.IntegrityError:
        con.rollback()
        flash("The booking could not be completed. Please try again.", "danger")
    except sqlite3.OperationalError:
        con.rollback()
        flash("The booking system is busy. Please try again in a moment.", "warning")
    finally:
        con.close()

    return redirect(url_for("dashboard"))


@app.post("/cancel/<int:booking_id>")
@login_required
def cancel(booking_id):
    user = current_user()
    con = get_db()
    con.execute("DELETE FROM bookings WHERE id=? AND user_id=?", (booking_id, user["id"]))
    con.commit()
    con.close()
    flash("Booking cancelled.", "success")
    return redirect(url_for("dashboard"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    seed_pre_registered_students()
    app.run(host="127.0.0.1", port=5000, debug=True)
