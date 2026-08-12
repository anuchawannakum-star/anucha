"""
models.py — โครงสร้างข้อมูลระบบบันทึกคะแนน KPI ประจำปี
ต่อยอดจากระบบเดิมของ KIRO (Flask + SQLAlchemy + Flask-Login)

โครงสร้าง KPI:
  - KPI ส่วนกลาง (ข้อ 1–5)  : ใช้เหมือนกันทั้งทีม  (is_team=True)
  - KPI รายบุคคล (ข้อ 6+)   : เพิ่มเองได้ต่อคน     (is_team=False, owner_id=user.id)

หลักการให้คะแนน: กรอก "ค่าจริง" → ระบบแปลงเป็น "ระดับ 1–5" ตามเกณฑ์ → คำนวณคะแนนถ่วงน้ำหนัก
  คะแนนหัวข้อ      = (ระดับ / 5) * น้ำหนัก
  คะแนนรวมเดือน    = ผลรวมทุกหัวข้อ (เต็ม 100)
  คะแนนประจำปี     = เฉลี่ยคะแนนรวมของทุกเดือนที่บันทึก (ก.ค.–ธ.ค.)
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# db ถูกสร้างใน extensions.py / app factory ของ KIRO — import มาใช้ร่วมกัน
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120))
    role = db.Column(db.String(20), default="user")  # 'admin' | 'user'

    # ความสัมพันธ์
    personal_kpis = db.relationship("KpiCategory", backref="owner", lazy=True,
                                    foreign_keys="KpiCategory.owner_id")
    records = db.relationship("KpiRecord", backref="user", lazy=True)

    @property
    def is_admin(self):
        return self.role == "admin"

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class KpiCategory(db.Model):
    """หัวข้อ KPI — ส่วนกลาง (ทั้งทีม) หรือ รายบุคคล (owner_id)"""
    __tablename__ = "kpi_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    unit = db.Column(db.String(40), default="หน่วย")      # หน่วยของค่าจริง เช่น %, เคส, กิจกรรม
    weight = db.Column(db.Float, nullable=False)           # น้ำหนัก % (0–100)
    order_no = db.Column(db.Integer, default=0)            # ลำดับข้อ (1–5 = ส่วนกลาง)

    is_team = db.Column(db.Boolean, default=True)          # True=ส่วนกลาง, False=รายบุคคล
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # ใช้เมื่อ is_team=False

    # ทิศทางคะแนน: 'higher' = ค่ามากยิ่งดี | 'lower' = ค่าน้อยยิ่งดี
    direction = db.Column(db.String(10), default="higher")

    # เกณฑ์แปลงค่า→ระดับ 1..5 : เก็บเป็น string "v1,v2,v3,v4,v5"
    #   higher: ค่า >= th[i] ⇒ ระดับ i+1 (ไล่จากสูงสุดลงมา)
    #   lower : ค่า <= th[i] ⇒ ระดับ i+1
    thresholds = db.Column(db.String(120), nullable=False)

    year = db.Column(db.Integer, default=2569)

    def th_list(self):
        return [float(x) for x in self.thresholds.split(",")]

    def calc_level(self, value):
        """แปลงค่าจริง → ระดับ 1–5 (0 = ยังไม่กรอก)"""
        if value is None or value == "":
            return 0
        try:
            v = float(value)
        except (TypeError, ValueError):
            return 0
        th = self.th_list()
        if self.direction == "lower":
            for i in range(4, -1, -1):
                if v <= th[i]:
                    return i + 1
            return 1
        else:  # higher
            for i in range(4, -1, -1):
                if v >= th[i]:
                    return i + 1
            return 1

    def calc_score(self, value):
        """คะแนนถ่วงน้ำหนักของหัวข้อนี้ = (ระดับ/5) * น้ำหนัก"""
        lvl = self.calc_level(value)
        return (lvl / 5.0) * self.weight if lvl else 0.0


class KpiRecord(db.Model):
    """บันทึกค่าจริงของ 1 หัวข้อ ของผู้ใช้ 1 คน ในเดือน 1 เดือน"""
    __tablename__ = "kpi_records"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("kpi_categories.id"), nullable=False)
    year = db.Column(db.Integer, default=2569)
    month = db.Column(db.Integer, nullable=False)          # 7–12
    actual_value = db.Column(db.String(40))                # ค่าจริงที่กรอก
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = db.relationship("KpiCategory")

    __table_args__ = (
        db.UniqueConstraint("user_id", "category_id", "year", "month",
                            name="uq_user_cat_period"),
    )


# ---------- ฟังก์ชันช่วยคำนวณ (ใช้ใน routes / templates) ----------

def get_user_kpis(user, year=2569):
    """คืนหัวข้อ KPI ทั้งหมดของผู้ใช้: ส่วนกลาง (1–5) + รายบุคคลของคนนั้น"""
    team = (KpiCategory.query
            .filter_by(is_team=True, year=year)
            .order_by(KpiCategory.order_no).all())
    personal = (KpiCategory.query
                .filter_by(is_team=False, owner_id=user.id, year=year)
                .order_by(KpiCategory.order_no).all())
    return team + personal


def month_total(user, month, year=2569):
    """คะแนนรวมของผู้ใช้ในเดือนหนึ่ง (เต็ม 100)"""
    total = 0.0
    for cat in get_user_kpis(user, year):
        rec = KpiRecord.query.filter_by(
            user_id=user.id, category_id=cat.id, year=year, month=month).first()
        val = rec.actual_value if rec else None
        total += cat.calc_score(val)
    return round(total, 2)


def year_average(user, year=2569, months=(7, 8, 9, 10, 11, 12)):
    """คะแนนเฉลี่ยประจำปี = เฉลี่ยเฉพาะเดือนที่มีการบันทึก"""
    totals = []
    for m in months:
        has = KpiRecord.query.filter_by(user_id=user.id, year=year, month=m).first()
        if has:
            totals.append(month_total(user, m, year))
    return round(sum(totals) / len(totals), 2) if totals else 0.0


def grade_of(score):
    """แปลงคะแนน → เกรด"""
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def total_weight(user, year=2569):
    """น้ำหนักรวมของผู้ใช้ (ควรเป็น 100)"""
    return round(sum(c.weight for c in get_user_kpis(user, year)), 2)
