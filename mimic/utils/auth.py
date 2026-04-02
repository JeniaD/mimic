from flask import session

from mimic.extensions import db
from mimic.models import Users


def current_user():
    username = session.get("username")
    if not username:
        return None
    return Users.query.filter_by(username=username).first()
