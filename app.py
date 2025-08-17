from flask import *
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.from_pyfile('config.py') #, silent=True)

db = SQLAlchemy(app)

class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    campaigns = db.relationship('Campaigns', back_populates='owner')

class Campaigns(db.Model):
    __tablename__ = 'campaigns'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)

    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    owner = db.relationship('Users', back_populates='campaigns')

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    value = db.Column(db.String(250), nullable=False)

    @staticmethod
    def get(key, default=None):
        s = Setting.query.filter_by(key=key).first()
        return s.value if s else default

    @staticmethod
    def set(key, value):
        s = Setting.query.filter_by(key=key).first()
        if not s:
            s = Setting(key=key, value=value)
            db.session.add(s)
        else:
            s.value = value
        db.session.commit()


@app.before_request
def check_authentication():
    if request.endpoint not in ('login', "static") and (not session or not Users.query.filter_by(username=session["username"]).first()):
        return redirect(url_for('login'))
    
    # token = request.headers.get("Authorization")
    # if token != f"Bearer {API_KEY}":
    #     return jsonify({"error": "Unauthorized"}), 401

@app.route("/")
def index():
    return render_template("base.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/campaigns")
def campaigns():
    return render_template("campaigns.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = Users.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["username"] = user.username
            return redirect(url_for('index'))
    
    return render_template("login.html")

