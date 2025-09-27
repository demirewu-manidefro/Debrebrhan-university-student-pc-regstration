# models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from db import db

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'manager' or 'sub_manager'
    can_register = db.Column(db.Boolean, default=False)
    can_verify_exit = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_manager(self):
        return self.role == "manager"

    def is_sub_manager(self):
        return self.role == "sub_manager"


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    # personal
    name = db.Column(db.String(100), nullable=False)
    father_name = db.Column(db.String(100), nullable=False)
    grandfather_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.String(20), nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)

    # device / material
    device_model = db.Column(db.String(150))
    serial_number = db.Column(db.String(150), unique=True)

    # picture
    picture_path = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
