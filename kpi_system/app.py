"""
app.py — Application factory ประกอบระบบ KPI ทั้งหมด
รันในเครื่อง:  python app.py
รัน production (Render): gunicorn app:app
"""
import os
from flask import Flask, redirect, url_for
from extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "kpi-dev-secret-change-me")

    # ฐานข้อมูล: ใช้ DATABASE_URL จาก environment (Render Postgres) ถ้ามี, ไม่งั้น SQLite
    db_url = os.environ.get("DATABASE_URL", "sqlite:///kpi.db")
    # Render ให้ URL ขึ้นต้น postgres:// แต่ SQLAlchemy ต้องการ postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(uid):
        return User.query.get(int(uid))

    from routes_auth import auth
    from routes_kpi import kpi, main
    from routes_admin import admin
    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(kpi)
    app.register_blueprint(admin)

    @app.route("/")
    def index():
        return redirect(url_for("main.dashboard"))

    # สร้างตาราง + seed อัตโนมัติเมื่อเริ่มระบบ (ครั้งแรก / DB ว่าง)
    with app.app_context():
        db.create_all()
        if User.query.count() == 0:
            import seed_data
            seed_data._seed()

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
