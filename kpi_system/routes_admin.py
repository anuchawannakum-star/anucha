"""
routes_admin.py — Blueprint จัดการหัวข้อ KPI + ผู้ใช้ + รายงาน (เฉพาะ admin)
รองรับ endpoint ที่ base.html เรียก: admin.kpi_categories, admin.users,
admin.all_records, admin.export_my_kpi
"""
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from extensions import db
from models import (User, KpiCategory, KpiRecord, get_user_kpis, total_weight,
                    year_average, grade_of, month_total)

admin = Blueprint("admin", __name__, url_prefix="/admin")
YEAR = 2569
MONTHS = [(7, "ก.ค."), (8, "ส.ค."), (9, "ก.ย."),
          (10, "ต.ค."), (11, "พ.ย."), (12, "ธ.ค.")]


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


# ---------- หน้าจัดการหัวข้อ KPI ----------
@admin.route("/kpi")
@admin_required
def kpi_categories():
    team = (KpiCategory.query
            .filter_by(is_team=True, year=YEAR)
            .order_by(KpiCategory.order_no).all())
    team_weight = round(sum(c.weight for c in team), 2)

    users = User.query.filter_by(role="user").all()
    personal = []
    for u in users:
        cats = (KpiCategory.query
                .filter_by(is_team=False, owner_id=u.id, year=YEAR)
                .order_by(KpiCategory.order_no).all())
        personal.append({"user": u, "cats": cats, "total_weight": total_weight(u, YEAR)})

    return render_template("kpi/admin_categories.html",
                           team=team, team_weight=team_weight,
                           personal=personal, users=users, year=YEAR)


# ---------- เพิ่ม / แก้ไข หัวข้อ KPI ----------
@admin.route("/kpi/save", methods=["POST"])
@admin_required
def save_kpi():
    cat_id = request.form.get("id", type=int)
    scope = request.form.get("scope")
    owner_id = request.form.get("owner_id", type=int)

    data = dict(
        name=request.form.get("name", "").strip(),
        unit=request.form.get("unit", "หน่วย").strip(),
        weight=request.form.get("weight", type=float) or 0,
        order_no=request.form.get("order_no", type=int) or 0,
        direction=request.form.get("direction", "higher"),
        thresholds=request.form.get("thresholds", "").strip(),
        year=YEAR,
    )

    if not data["name"] or not data["thresholds"]:
        flash("กรุณากรอกชื่อหัวข้อและเกณฑ์ให้ครบ", "danger")
        return redirect(url_for("admin.kpi_categories"))
    if len(data["thresholds"].split(",")) != 5:
        flash("เกณฑ์ (thresholds) ต้องมี 5 ค่า คั่นด้วยจุลภาค เช่น 1,2,3,4,5", "danger")
        return redirect(url_for("admin.kpi_categories"))

    if cat_id:
        cat = KpiCategory.query.get_or_404(cat_id)
        for k, v in data.items():
            setattr(cat, k, v)
        flash("แก้ไขหัวข้อ KPI เรียบร้อย", "success")
    else:
        cat = KpiCategory(**data)
        if scope == "team":
            cat.is_team = True
            cat.owner_id = None
        else:
            cat.is_team = False
            cat.owner_id = owner_id
        db.session.add(cat)
        flash("เพิ่มหัวข้อ KPI เรียบร้อย", "success")

    db.session.commit()
    return redirect(url_for("admin.kpi_categories"))


# ---------- ลบหัวข้อ KPI ----------
@admin.route("/kpi/delete/<int:cat_id>", methods=["POST"])
@admin_required
def delete_kpi(cat_id):
    cat = KpiCategory.query.get_or_404(cat_id)
    KpiRecord.query.filter_by(category_id=cat_id).delete()
    db.session.delete(cat)
    db.session.commit()
    flash("ลบหัวข้อ KPI เรียบร้อย", "success")
    return redirect(url_for("admin.kpi_categories"))


# ---------- จัดการผู้ใช้ ----------
@admin.route("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.role.desc(), User.username).all()
    return render_template("admin_users.html", users=all_users)


# ---------- บันทึกคะแนนทั้งหมด ----------
@admin.route("/records")
@admin_required
def all_records():
    users_list = User.query.filter_by(role="user").all()
    rows = []
    for u in users_list:
        avg = year_average(u, YEAR)
        rows.append({
            "user": u,
            "monthly": [month_total(u, m, YEAR) for m, _ in MONTHS],
            "avg": avg,
            "grade": grade_of(avg),
        })
    return render_template("admin_records.html", rows=rows,
                           month_labels=[n for _, n in MONTHS], year=YEAR)


# ---------- Export KPI ของตัวเอง (CSV) ----------
@admin.route("/export/my")
@login_required
def export_my_kpi():
    import csv, io
    from flask import Response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["หัวข้อ KPI", "น้ำหนัก(%)"] + [n for _, n in MONTHS])
    for cat in get_user_kpis(current_user, YEAR):
        row = [cat.name, cat.weight]
        for m, _ in MONTHS:
            rec = KpiRecord.query.filter_by(
                user_id=current_user.id, category_id=cat.id, year=YEAR, month=m).first()
            row.append(rec.actual_value if rec else "")
        writer.writerow(row)
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=kpi_{current_user.username}.csv"})
