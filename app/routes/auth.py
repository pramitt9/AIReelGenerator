from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User

auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/register", methods=["POST"])
def register():

    data = request.get_json(silent=True) or request.form

    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(
        username=username,
        email=email
    )

    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Registration successful",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }), 201


@auth.route("/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or request.form

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    login_user(user)

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }), 200


@auth.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()

    return jsonify({
        "message": "Logout successful"
    }), 200


@auth.route("/me", methods=["GET"])
@login_required
def get_current_user():

    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email
    }), 200