"""routes_auth.py — Blueprint เข้าสู่ระบบ / ออกจากระบบ / โปรไฟล์"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User

auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(pw):
            login_user(user)
            return redirect(url_for("main.dashboard"))
        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "danger")
    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("ออกจากระบบเรียบร้อย", "success")
    return redirect(url_for("auth.login"))


@auth.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        new_pw = request.form.get("password", "").strip()
        if new_pw:
            current_user.set_password(new_pw)
            db.session.commit()
            flash("เปลี่ยนรหัสผ่านเรียบร้อย", "success")
        return redirect(url_for("auth.profile"))
    return render_template("profile.html")
