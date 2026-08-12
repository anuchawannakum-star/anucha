"""
routes_kpi.py — Blueprint สำหรับบันทึก/สรุปคะแนน KPI
ต่อยอด endpoint ที่ base.html เรียกใช้:  kpi.record , main.dashboard , main.team_overview
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import (User, KpiCategory, KpiRecord,
                    get_user_kpis, month_total, year_average, grade_of, total_weight)

kpi = Blueprint("kpi", __name__, url_prefix="/kpi")
main = Blueprint("main", __name__)

MONTHS = [(7, "กรกฎาคม"), (8, "สิงหาคม"), (9, "กันยายน"),
          (10, "ตุลาคม"), (11, "พฤศจิกายน"), (12, "ธันวาคม")]
YEAR = 2569


# ---------- หน้าบันทึกคะแนนรายเดือน ----------
@kpi.route("/record/<int:year>/<int:month>", methods=["GET", "POST"])
@login_required
def record(year, month):
    # admin เลือกดูของคนอื่นได้ผ่าน ?user_id= ; user ทั่วไปดูของตัวเอง
    target_id = request.args.get("user_id", type=int)
    target = User.query.get(target_id) if (target_id and current_user.is_admin) else current_user

    kpis = get_user_kpis(target, year)

    if request.method == "POST":
        for cat in kpis:
            field = f"kpi_{cat.id}"
            value = request.form.get(field, "").strip()
            rec = KpiRecord.query.filter_by(
                user_id=target.id, category_id=cat.id, year=year, month=month).first()
            if rec:
                rec.actual_value = value
            else:
                db.session.add(KpiRecord(user_id=target.id, category_id=cat.id,
                                         year=year, month=month, actual_value=value))
        db.session.commit()
        flash("บันทึกคะแนนเดือน " + dict(MONTHS)[month] + " เรียบร้อยแล้ว", "success")
        return redirect(url_for("kpi.record", year=year, month=month,
                                user_id=target.id if current_user.is_admin else None))

    # เตรียมข้อมูลสำหรับ template
    rows = []
    for cat in kpis:
        rec = KpiRecord.query.filter_by(
            user_id=target.id, category_id=cat.id, year=year, month=month).first()
        val = rec.actual_value if rec else ""
        rows.append({
            "cat": cat, "value": val,
            "level": cat.calc_level(val), "score": round(cat.calc_score(val), 2),
        })

    return render_template("kpi/record.html",
                           target=target, rows=rows,
                           year=year, month=month,
                           month_name=dict(MONTHS)[month],
                           months=MONTHS,
                           month_total=month_total(target, month, year),
                           total_weight=total_weight(target, year))


# ---------- API: คำนวณ preview แบบ real-time (AJAX) ----------
@kpi.route("/preview/<int:cat_id>")
@login_required
def preview(cat_id):
    cat = KpiCategory.query.get_or_404(cat_id)
    val = request.args.get("value", "")
    return jsonify(level=cat.calc_level(val), score=round(cat.calc_score(val), 2))


# ---------- Dashboard สรุปของตัวเอง ----------
@main.route("/")
@main.route("/dashboard")
@login_required
def dashboard():
    months = [m for m, _ in MONTHS]
    monthly = [month_total(current_user, m, YEAR) for m in months]
    avg = year_average(current_user, YEAR)

    # คะแนนเฉลี่ยรายหัวข้อ (ระดับ 1–5)
    topic_levels = []
    for cat in get_user_kpis(current_user, YEAR):
        lv = []
        for m in months:
            rec = KpiRecord.query.filter_by(
                user_id=current_user.id, category_id=cat.id, year=YEAR, month=m).first()
            if rec and rec.actual_value:
                lv.append(cat.calc_level(rec.actual_value))
        topic_levels.append({"name": cat.name,
                             "avg": round(sum(lv) / len(lv), 2) if lv else 0})

    return render_template("kpi/dashboard.html",
                           month_labels=[n for _, n in MONTHS],
                           monthly=monthly, avg=avg, grade=grade_of(avg),
                           topic_levels=topic_levels, year=YEAR)


# ---------- ภาพรวมทั้งทีม ----------
@main.route("/team")
@login_required
def team_overview():
    users = User.query.filter_by(role="user").all()
    data = []
    for u in users:
        avg = year_average(u, YEAR)
        data.append({"user": u, "avg": avg, "grade": grade_of(avg),
                     "monthly": [month_total(u, m, YEAR) for m, _ in MONTHS]})
    data.sort(key=lambda x: x["avg"], reverse=True)
    return render_template("kpi/team.html",
                           team=data, month_labels=[n for _, n in MONTHS], year=YEAR)
