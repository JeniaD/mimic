from flask import *
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timezone

app = Flask(__name__)
app.config.from_pyfile('config.py') #, silent=True)

db = SQLAlchemy(app)


def _ensure_db_and_default_user():
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

    status = db.Column(db.String(50), nullable=False, default="draft")  # draft|running|completed|archived
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    launched_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)

    # Freeze the final outgoing content (template + user pretext/payload) at launch time.
    subject_snapshot = db.Column(db.Text, nullable=True)
    body_snapshot = db.Column(db.Text, nullable=True)

    # Convenience snapshot for UI; not authoritative.
    target_count_snapshot = db.Column(db.Integer, nullable=True)

    runs = db.relationship("CampaignRuns", back_populates="campaign", cascade="all, delete-orphan")

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


class CampaignRuns(db.Model):
    __tablename__ = "campaign_runs"
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False, index=True)

    status = db.Column(db.String(50), nullable=False, default="running")  # running|succeeded|failed|stopped
    started_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    ended_at = db.Column(db.DateTime, nullable=True)

    # Snapshot run-time config (delay, sender selection, etc.). On SQLite this becomes TEXT.
    config_snapshot = db.Column(db.JSON, nullable=True)

    campaign = db.relationship("Campaigns", back_populates="runs")
    interactions = db.relationship("CampaignInteractions", back_populates="campaign_run", cascade="all, delete-orphan")
    tracking_tokens = db.relationship("TrackingTokens", back_populates="campaign_run", cascade="all, delete-orphan")


class CampaignInteractions(db.Model):
    __tablename__ = "campaign_interactions"
    id = db.Column(db.Integer, primary_key=True)
    campaign_run_id = db.Column(db.Integer, db.ForeignKey("campaign_runs.id"), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey("targets.id"), nullable=True, index=True)

    event_type = db.Column(db.String(50), nullable=False)  # sent|open|click|submit|bounce|report
    occurred_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    metadata = db.Column(db.JSON, nullable=True)

    campaign_run = db.relationship("CampaignRuns", back_populates="interactions")
    target = db.relationship("Targets")


class TrackingTokens(db.Model):
    __tablename__ = "tracking_tokens"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    campaign_run_id = db.Column(db.Integer, db.ForeignKey("campaign_runs.id"), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey("targets.id"), nullable=True, index=True)
    purpose = db.Column(db.String(50), nullable=True)  # open_pixel|click|other
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    campaign_run = db.relationship("CampaignRuns", back_populates="tracking_tokens")
    target = db.relationship("Targets")

class Settings(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    value = db.Column(db.String(250), nullable=False)

    @staticmethod
    def get(name, default=None):
        s = Settings.query.filter_by(name=name).first()
        return s.value if s else default

    @staticmethod
    def set(name, value):
        s = Settings.query.filter_by(name=name).first()
        if not s:
            s = Settings(name=name, value=str(value))
            db.session.add(s)
        else:
            s.value = str(value)
        db.session.commit()


with app.app_context():
    _ensure_db_and_default_user()

@app.before_request
def check_authentication():
    endpoint = request.endpoint or ""
    if endpoint in ("login", "static"):
        return

    username = session.get("username")
    if not username or not Users.query.filter_by(username=username).first():
        return redirect(url_for('login'))
    
    # token = request.headers.get("Authorization")
    # if token != f"Bearer {API_KEY}":
    #     return jsonify({"error": "Unauthorized"}), 401

@app.route("/")
def index():
    return render_template("base.html")

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        # Update only the fields that were submitted.
        mapping = {
            "mserver": "mail_server",
            "mport": "mail_port",
            "musername": "mail_username",
            "mpassword": "mail_password",
            "sdelay": "send_delay_seconds",
        }
        for form_key, setting_name in mapping.items():
            if form_key in request.form:
                raw = request.form.get(form_key, "").strip()
                if raw != "":
                    Settings.set(setting_name, raw)

        return redirect(url_for("settings"))

    current = {
        "mail_server": Settings.get("mail_server", ""),
        "mail_port": Settings.get("mail_port", ""),
        "mail_username": Settings.get("mail_username", ""),
        "mail_password": Settings.get("mail_password", ""),
        "send_delay_seconds": Settings.get("send_delay_seconds", ""),
    }
    return render_template("settings.html", current=current)

@app.route("/campaigns")
def campaigns():
    return render_template("campaigns.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html"), 400

        user = Users.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["username"] = user.username
            return redirect(url_for('index'))
        flash("Invalid username or password.", "error")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/help")
def help():
    return render_template("base.html")

