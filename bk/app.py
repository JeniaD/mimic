from flask import *
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin

app = Flask(__name__)
# app.secret = "password"
# app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.sqlite"
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# app.config["SECRET_KEY"] = "supersecretkey"

app.config.from_pyfile('config.py') #, silent=True)

db = SQLAlchemy(app)

loginManager = LoginManager()
loginManager.init_app(app)

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)

@loginManager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

@app.route("/")
def main():
    return render_template("base.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(somewhere)

with app.app_context():
    db.create_all()
