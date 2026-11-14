
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from app.extensions import db
from app.models import User

auth = Blueprint("auth", __name__)


# -------------------------
# Registration
# -------------------------

@auth.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not username or not email or not password:
        flash("All fields are required.", "danger")
        return redirect(url_for("auth.register"))

    if len(password) < 8:
        flash("Password must contain at least 8 characters.", "danger")
        return redirect(url_for("auth.register"))

    if password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("auth.register"))

    if User.query.filter_by(email=email).first():
        flash("An account with this email already exists.", "danger")
        return redirect(url_for("auth.register"))

    user = User(username=username, email=email)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    login_user(user)

    flash("Account created successfully!", "success")
    return redirect(url_for("main.home"))


# -------------------------
# Login
# -------------------------

@auth.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user, remember=True)

    return redirect(url_for("main.home"))


# -------------------------
# Logout
# -------------------------

@auth.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()
    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))


# -------------------------
# Current user API
# -------------------------

@auth.route("/me", methods=["GET"])
@login_required
def me():

    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email
    })
