"""
seed_data.py — เตรียมข้อมูลตั้งต้น
  - KPI ส่วนกลาง (ข้อ 1–5) ใช้เหมือนกันทั้งทีม
  - ผู้ใช้ทีม 4 คน (รวม Anucha) + admin
  - KPI รายบุคคลตัวอย่างของ Anucha (ข้อ 6–8 จากไฟล์ PMS)

เรียกจาก app.py อัตโนมัติเมื่อ DB ว่าง หรือรันตรง:  python seed_data.py
"""
from extensions import db
from models import User, KpiCategory

YEAR = 2569

# ---------- KPI ส่วนกลาง (ข้อ 1–5) — น้ำหนักรวม 50% ----------
TEAM_KPIS = [
    dict(order_no=1, name="กิจกรรม CSR ครอบคลุมด้านสุขภาวะ", unit="กิจกรรม",
         weight=5,  direction="higher", thresholds="1,2,3,6,9"),
    dict(order_no=2, name="ความพึงพอใจของพนักงานที่ร่วมกิจกรรม CSR", unit="คะแนน",
         weight=15, direction="higher", thresholds="3,3.5,4,4.5,5"),
    dict(order_no=3, name="จำนวนข้อร้องเรียนที่เกี่ยวข้อง", unit="เคส",
         weight=5,  direction="lower",  thresholds="5,4,3,1,0"),   # ตามไฟล์: น้อย=ดี
    dict(order_no=4, name="อัตราการเข้าร่วมกิจกรรมของพนักงาน", unit="%",
         weight=15, direction="higher", thresholds="80,90,100,110,120"),
    dict(order_no=5, name="จำนวนกิจกรรม", unit="กิจกรรม",
         weight=10, direction="higher", thresholds="4,5,6,7,8"),
]

# ---------- ทีม 4 คน + admin ----------
USERS = [
    dict(username="anucha", full_name="อนุชา วรรณคำ (Anucha)", department="CSR/HR", role="user"),
    dict(username="member2", full_name="สมาชิก 2", department="CSR/HR", role="user"),
    dict(username="member3", full_name="สมาชิก 3", department="CSR/HR", role="user"),
    dict(username="member4", full_name="สมาชิก 4", department="CSR/HR", role="user"),
    dict(username="admin",   full_name="ผู้ดูแลระบบ", department=None, role="admin"),
]

# ---------- KPI รายบุคคลของ Anucha (ข้อ 6–8) — น้ำหนักรวม 50% ----------
ANUCHA_PERSONAL = [
    dict(order_no=6, name="ออกหน่วยสื่อ (ตามระยะเวลาที่กำหนด)", unit="วัน",
         weight=10, direction="lower",  thresholds="25,20,14,7,3"),
    dict(order_no=7, name="สอบสวนพนักงาน / ดำเนินการถูกต้อง", unit="%",
         weight=20, direction="higher", thresholds="90,95,97,99,100"),
    dict(order_no=8, name="โครงการ Retention สำเร็จตามแผนภายในปี 2569", unit="โครงการ",
         weight=20, direction="higher", thresholds="4,5,6,7,8"),
]


def _seed():
    """ทำงานภายใต้ app context ที่เปิดอยู่แล้ว"""
    db.create_all()

    users = {}
    for u in USERS:
        user = User.query.filter_by(username=u["username"]).first()
        if not user:
            user = User(**u)
            user.set_password("1234")  # เดโม — เปลี่ยนก่อนใช้จริง
            db.session.add(user)
        users[u["username"]] = user
    db.session.commit()

    for k in TEAM_KPIS:
        if not KpiCategory.query.filter_by(order_no=k["order_no"], is_team=True, year=YEAR).first():
            db.session.add(KpiCategory(is_team=True, year=YEAR, **k))

    anucha = users["anucha"]
    for k in ANUCHA_PERSONAL:
        if not KpiCategory.query.filter_by(order_no=k["order_no"], owner_id=anucha.id, year=YEAR).first():
            db.session.add(KpiCategory(is_team=False, owner_id=anucha.id, year=YEAR, **k))

    db.session.commit()
    print("✅ Seed สำเร็จ: KPI ส่วนกลาง 5 ข้อ, ผู้ใช้", len(USERS), "คน, KPI รายบุคคล Anucha 3 ข้อ")
    print("   รหัสผ่านเริ่มต้นทุกคน: 1234 (เปลี่ยนก่อนใช้งานจริง)")


def run_within_app(app):
    with app.app_context():
        _seed()


def run():
    from app import create_app
    run_within_app(create_app())


if __name__ == "__main__":
    run()
