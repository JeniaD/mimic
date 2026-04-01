from werkzeug.security import generate_password_hash

from mimic.extensions import db
from mimic.models import Users


def ensure_db_and_default_user(app):
    """Create tables and optional default user from config."""
    db.create_all()

    default_username = app.config.get("DEFAULT_USER")
    default_password = app.config.get("DEFAULT_PASSWORD") or app.config.get("secret")
    if not default_username or not default_password:
        return

    existing = Users.query.filter_by(username=default_username).first()
    if existing:
        return

    user = Users(
        username=default_username,
        password=generate_password_hash(str(default_password), method="pbkdf2:sha256"),
    )
    db.session.add(user)
    db.session.commit()
