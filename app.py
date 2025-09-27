# app.py
import os
import uuid
import smtplib
from email.message import EmailMessage
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort, jsonify
)
from werkzeug.utils import secure_filename
from config import Config
from db import db
from models import User, Student

# Create app
app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize DB
db.init_app(app)

# ------------------------
# Utility helpers
# ------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = session.get("user_id")
        if not uid:
            return redirect(url_for("login"))
        user = User.query.get(uid)
        if not user or not user.is_manager():
            flash("Manager access only.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    allowed = {"png", "jpg", "jpeg"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed

def save_picture(file_storage):
    if file_storage and allowed_file(file_storage.filename):
        filename = secure_filename(file_storage.filename)
        # make filename unique
        ext = filename.rsplit(".", 1)[1]
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file_storage.save(filepath)
        # return relative path to store in db
        return os.path.join("static", "uploads", unique_name)
    return None

def delete_picture_file(picture_path):
    """Delete a stored picture file. picture_path is like 'static/uploads/xxx.jpg'"""
    if not picture_path:
        return
    full = os.path.join(os.path.dirname(__file__), picture_path)
    try:
        if os.path.exists(full):
            os.remove(full)
    except Exception as e:
        app.logger.error(f"Error removing file {full}: {e}")

def send_exit_email(to_email, student, manager_user):
    """Send basic SMTP email notification when exit is approved."""
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Exit Approved for {student.name} ({student.student_id})"
        msg["From"] = app.config["EMAIL_FROM"]
        msg["To"] = to_email

        body = (
            f"Hello {student.name},\n\n"
            f"Your exit has been approved by {manager_user.username}.\n\n"
            f"Student ID: {student.student_id}\n"
            f"Device Model: {student.device_model}\n"
            f"Serial Number: {student.serial_number}\n"
            f"Department: {student.department}\n"
            f"Year: {student.year}\n\n"
            f"Purpose recorded at verification time.\n\n"
            "Please keep this message for your records.\n\n"
            "— Campus Admin"
        )
        msg.set_content(body)

        # Use SMTP server from config
        server = smtplib.SMTP(app.config["SMTP_SERVER"], app.config["SMTP_PORT"])
        server.starttls()
        server.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        app.logger.error(f"Failed to send email to {to_email}: {e}")
        return False

# ------------------------
# Routes: Auth & Dash
# ------------------------
@app.route("/setup")
def setup():
    """
    One-time setup route to create DB tables and create a default manager user.
    After running once, you can remove or protect this route.
    """
    with app.app_context():
        db.create_all()
        # Create default manager if not exists
        if not User.query.filter_by(username="manager").first():
            m = User(username="manager", role="manager", can_register=True, can_verify_exit=True)
            m.set_password("manager123")  # change after first login
            db.session.add(m)
            db.session.commit()
            return "Setup done. Manager user created with username=manager and password=manager123. Change it immediately."
        return "Setup done. Manager already exists."

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    user = User.query.get(session["user_id"])
    return render_template("dashboard.html", user=user)

# ------------------------
# User management (Manager)
# ------------------------
@app.route("/users")
@manager_required
def users_list():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users_list.html", users=users)

@app.route("/users/create", methods=["GET", "POST"])
@manager_required
def create_sub_manager():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        can_register = bool(request.form.get("can_register"))
        can_verify = bool(request.form.get("can_verify_exit"))
        if User.query.filter_by(username=username).first():
            flash("Username already exists", "danger")
            return redirect(url_for("create_sub_manager"))
        user = User(username=username, role="sub_manager", can_register=can_register, can_verify_exit=can_verify)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Sub-Manager created.", "success")
        return redirect(url_for("users_list"))
    return render_template("create_user.html")

@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@manager_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        user.can_register = bool(request.form.get("can_register"))
        user.can_verify_exit = bool(request.form.get("can_verify_exit"))
        db.session.commit()
        flash("Permissions updated.", "success")
        return redirect(url_for("users_list"))
    return render_template("edit_user.html", u=user)

@app.route("/users/<int:user_id>/delete", methods=["POST"])
@manager_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_manager():
        flash("Cannot delete a manager account.", "danger")
        return redirect(url_for("users_list"))
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.", "success")
    return redirect(url_for("users_list"))

# ------------------------
# Student CRUD & Search
# ------------------------
@app.route("/students")
@login_required
def list_students():
    # Basic list or optionally filter
    q = request.args.get("q", "").strip()
    if q:
        # search by student id or name
        students = Student.query.filter(
            (Student.student_id.ilike(f"%{q}%")) | (Student.name.ilike(f"%{q}%"))
        ).all()
    else:
        students = Student.query.order_by(Student.created_at.desc()).limit(200).all()
    user = User.query.get(session["user_id"])
    return render_template("students_list.html", students=students, user=user)

@app.route("/students/new", methods=["GET", "POST"])
@login_required
def register_student():
    user = User.query.get(session["user_id"])
    # permission check
    if not (user.is_manager() or user.can_register):
        flash("You don't have permission to register students.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form["name"].strip()
        father_name = request.form["father_name"].strip()
        grandfather_name = request.form["grandfather_name"].strip()
        department = request.form["department"].strip()
        year = request.form["year"].strip()
        student_id_val = request.form["student_id"].strip()
        email = request.form["email"].strip()
        device_model = request.form.get("device_model", "").strip()
        serial_number = request.form.get("serial_number", "").strip()

        # uniqueness checks
        if Student.query.filter_by(student_id=student_id_val).first():
            flash("Student ID already exists.", "danger")
            return redirect(url_for("register_student"))
        if serial_number and Student.query.filter_by(serial_number=serial_number).first():
            flash("Serial number already registered.", "danger")
            return redirect(url_for("register_student"))

        picture = request.files.get("picture")
        picture_path = None
        if picture and picture.filename:
            picture_path = save_picture(picture)

        student = Student(
            name=name,
            father_name=father_name,
            grandfather_name=grandfather_name,
            department=department,
            year=year,
            student_id=student_id_val,
            email=email,
            device_model=device_model,
            serial_number=serial_number,
            picture_path=picture_path
        )
        db.session.add(student)
        db.session.commit()
        flash("Student registered successfully.", "success")
        return redirect(url_for("list_students"))
    return render_template("register_student.html")

@app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def edit_student(sid):
    student = Student.query.get_or_404(sid)
    user = User.query.get(session["user_id"])
    if not (user.is_manager() or user.can_register):
        flash("You don't have permission to edit students.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        # If serial will be changed, ensure uniqueness
        serial_number = request.form.get("serial_number", "").strip()
        if serial_number and serial_number != student.serial_number:
            if Student.query.filter_by(serial_number=serial_number).first():
                flash("Serial number already in use.", "danger")
                return redirect(url_for("edit_student", sid=sid))

        # If the picture or device changed, delete old picture (as requested)
        picture = request.files.get("picture")
        if picture and picture.filename:
            # delete old
            delete_picture_file(student.picture_path)
            student.picture_path = save_picture(picture)

        # Update fields
        student.name = request.form["name"].strip()
        student.father_name = request.form["father_name"].strip()
        student.grandfather_name = request.form["grandfather_name"].strip()
        student.department = request.form["department"].strip()
        student.year = request.form["year"].strip()
        student.student_id = request.form["student_id"].strip()
        student.email = request.form["email"].strip()
        student.device_model = request.form.get("device_model", "").strip()
        student.serial_number = serial_number

        db.session.commit()
        flash("Student updated.", "success")
        return redirect(url_for("list_students"))

    return render_template("edit_student.html", student=student)

@app.route("/students/<int:sid>/delete", methods=["POST"])
@login_required
def delete_student(sid):
    student = Student.query.get_or_404(sid)
    user = User.query.get(session["user_id"])
    if not user.is_manager():
        flash("Only Manager can delete students.", "danger")
        return redirect(url_for("list_students"))
    # delete picture file
    delete_picture_file(student.picture_path)
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted.", "success")
    return redirect(url_for("list_students"))

@app.route("/students/search", methods=["GET"])
@login_required
def search_student():
    # search by student_id param
    sid = request.args.get("student_id", "").strip()
    if not sid:
        flash("Provide student ID to search.", "warning")
        return redirect(url_for("list_students"))
    student = Student.query.filter_by(student_id=sid).first()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("list_students"))
    return render_template("student_profile.html", student=student)

# ------------------------
# Exit verification
# ------------------------
@app.route("/verify_exit", methods=["GET", "POST"])
@login_required
def verify_exit():
    user = User.query.get(session["user_id"])
    if request.method == "POST":
        # permission check
        if not (user.is_manager() or user.can_verify_exit):
            flash("You don't have permission to verify exit.", "danger")
            return redirect(url_for("dashboard"))

        student_id_val = request.form["student_id"].strip()
        reason = request.form.get("reason", "").strip()

        student = Student.query.filter_by(student_id=student_id_val).first()
        if not student:
            flash("Student not found.", "danger")
            return redirect(url_for("verify_exit"))

        # verify step — in UI manager will visually confirm picture and serial
        # Here we record the action and send email
        sent = send_exit_email(student.email, student, user)
        if sent:
            flash("Exit approved and email notification sent to student.", "success")
        else:
            flash("Exit approved but failed to send email. Check SMTP settings.", "warning")
        # Note: we do NOT create a leave-out table because you said not necessary;
        # if you want history later we can add it.
        return redirect(url_for("list_students"))

    return render_template("verify_exit.html")

# ------------------------
# Static files / simple API
# ------------------------
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # serve uploads securely
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ------------------------
# API endpoints (optional small JSON helpers)
# ------------------------
@app.route("/api/student/<student_id>", methods=["GET"])
@login_required
def api_get_student(student_id):
    s = Student.query.filter_by(student_id=student_id).first_or_404()
    return jsonify({
        "name": s.name,
        "father_name": s.father_name,
        "grandfather_name": s.grandfather_name,
        "department": s.department,
        "year": s.year,
        "student_id": s.student_id,
        "email": s.email,
        "device_model": s.device_model,
        "serial_number": s.serial_number,
        "picture_path": s.picture_path
    })

# ------------------------
# Run app
# ------------------------
if __name__ == "__main__":
    # for debugging only; in production use a WSGI server
    app.run(debug=True,host="127.0.0.1", port=5000)
