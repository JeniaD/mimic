from werkzeug.security import generate_password_hash

from config import DEFAULT_USER
from mimic import create_app
from mimic.extensions import db
from mimic.models import Users

app = create_app(bootstrap_defaults=False)

with app.app_context():
    print("Creating database tables...")

    if not Users.query.filter_by(username=DEFAULT_USER).first():
        password = input("Set admin password: ")
        admin = Users(
            username=DEFAULT_USER,
            password=generate_password_hash(password, method="pbkdf2:sha256"),
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user {DEFAULT_USER} created.")
    else:
        existing = Users.query.filter_by(username=DEFAULT_USER).first()
        if (existing.password or "").startswith("scrypt:"):
            print(
                f"User {DEFAULT_USER} exists but uses a scrypt password hash, "
                "which may not work on this Python build."
            )
            password = input(
                "Reset admin password now? Enter new password (or blank to skip): "
            )
            if password:
                existing.password = generate_password_hash(password, method="pbkdf2:sha256")
                db.session.commit()
                print(f"Admin user {DEFAULT_USER} password reset (pbkdf2:sha256).")


def create_db(flask_app):
    with flask_app.app_context():
        db.create_all()
