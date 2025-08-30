from flask import *
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.from_pyfile('config.py') #, silent=True)

db = SQLAlchemy(app)

campaignMailTemplates = db.Table('campaignMailTemplates',
    db.Column('campaign_id', db.Integer, db.ForeignKey('campaigns.id')),
    db.Column('template_id', db.Integer, db.ForeignKey('mail_templates.id'))
)
campaignClusters = db.Table('campaignClusters',
    db.Column('campaign_id', db.Integer, db.ForeignKey('campaigns.id')),
    db.Column('cluster_id', db.Integer, db.ForeignKey('clusters.id'))
)
campaignAssets = db.Table('campaignAssets',
    db.Column('campaign_id', db.Integer, db.ForeignKey('campaigns.id')),
    db.Column('asset_id', db.Integer, db.ForeignKey('assets.id'))
)

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

    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    owner = db.relationship('Users', back_populates='campaigns')

    mailTemplates = db.relationship('MailTemplates', secondary=campaignMailTemplates, backref="campaigns")
    assets = db.relationship('Assets', secondary=campaignAssets, backref="campaigns")
    clusters = db.relationship('Clusters', secondary=campaignClusters, backref="campaigns")
    # mailTemplates = db.relationship('MailTemplates', back_populates='campaign')
    # assets = db.relationship('Assets', back_populates='campaign')
    # clusters = db.relationship('Clusters', back_populates='campaign')

class MailTemplates(db.Model):
    __tablename__ = 'mail_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    content = db.Column(db.Text)

class Assets(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    server = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)
    port = db.Column(db.Integer)

class Clusters(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)

    targets = db.relationship("Targets", backref="cluster", lazy=True)

class Targets(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attributes = db.Column(db.PickleType)

    cluster_id = db.Column(db.Integer, db.ForeignKey('clusters.id'))
    # cluster = db.relationship("Clusters", back_populates="targets")

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

