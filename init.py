from flask import *
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from app import app, db, Users, Settings
from config import DEFAULT_USER

with app.app_context():
    print("Creating database tables...")
    db.create_all()

    if not Users.query.filter_by(username=DEFAULT_USER).first():
        password = input("Set admin password: ")
        admin = Users(username=DEFAULT_USER, password=generate_password_hash(password))
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user {DEFAULT_USER} created.")
    
    # domain = input("Please enter domain name: ")
    # Settings.set("domain", domain)

def create_db(app):
    with app.app_context():
        db.create_all()