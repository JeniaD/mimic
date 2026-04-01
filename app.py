from flask import *
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint, func
import secrets
import smtplib
import html as html_module
from email.mime.text import MIMEText
from jinja2 import Environment, BaseLoader

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
    description = db.Column(db.Text, nullable=True)

    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    owner = db.relationship('Users', back_populates='campaigns')

    mailTemplates = db.relationship('MailTemplates', secondary=campaignMailTemplates, backref="campaigns")
    assets = db.relationship('Assets', secondary=campaignAssets, backref="campaigns")
    clusters = db.relationship('Clusters', secondary=campaignClusters, backref="campaigns")

    status = db.Column(db.String(50), nullable=False, default="draft")  # draft|launched|completed|archived
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    launched_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)

    # Editable while draft; copied to snapshots at launch.
    subject_draft = db.Column(db.Text, nullable=True)
    body_draft = db.Column(db.Text, nullable=True)

    # Frozen at launch (content without per-recipient tracking tokens; tokens added per send).
    subject_snapshot = db.Column(db.Text, nullable=True)
    body_snapshot = db.Column(db.Text, nullable=True)

    target_count_snapshot = db.Column(db.Integer, nullable=True)

    runs = db.relationship("CampaignRuns", back_populates="campaign", cascade="all, delete-orphan")

class MailTemplates(db.Model):
    __tablename__ = 'mail_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    content = db.Column(db.Text)

class Assets(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    server = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)
    port = db.Column(db.Integer)

class Clusters(db.Model):
    __tablename__ = "clusters"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    targets = db.relationship(
        "Targets",
        back_populates="cluster",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Targets(db.Model):
    __tablename__ = "targets"
    __table_args__ = (
        UniqueConstraint("cluster_id", "email", name="uq_target_cluster_email"),
    )

    id = db.Column(db.Integer, primary_key=True)
    cluster_id = db.Column(db.Integer, db.ForeignKey("clusters.id"), nullable=False, index=True)
    # Explicit fields for people in a cluster (queryable, form-friendly).
    email = db.Column(db.String(250), nullable=False)
    # Personalization for campaign subject/body (Jinja: {{ name }}, {{ text }}).
    name = db.Column(db.String(250), nullable=True)
    personal_text = db.Column(db.Text, nullable=True)

    cluster = db.relationship("Clusters", back_populates="targets")


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
    campaign_metadata = db.Column(db.JSON, nullable=True)

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

PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def _current_user():
    username = session.get("username")
    if not username:
        return None
    return Users.query.filter_by(username=username).first()


def _unique_targets_for_campaign(campaign):
    cluster_ids = [c.id for c in campaign.clusters]
    if not cluster_ids:
        return []
    seen = set()
    out = []
    for t in (
        Targets.query.filter(Targets.cluster_id.in_(cluster_ids))
        .order_by(Targets.id)
        .all()
    ):
        key = (t.email or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _distinct_event_count(campaign_id, event_type):
    run_ids = [
        r.id
        for r in CampaignRuns.query.filter_by(campaign_id=campaign_id).all()
    ]
    if not run_ids:
        return 0
    n = (
        db.session.query(func.count(func.distinct(CampaignInteractions.target_id)))
        .filter(
            CampaignInteractions.campaign_run_id.in_(run_ids),
            CampaignInteractions.event_type == event_type,
            CampaignInteractions.target_id.isnot(None),
        )
        .scalar()
    )
    return int(n or 0)


def _draft_target_count(campaign):
    return len(_unique_targets_for_campaign(campaign))


def _sync_campaign_template(campaign_id, template_id):
    db.session.execute(
        campaignMailTemplates.delete().where(campaignMailTemplates.c.campaign_id == campaign_id)
    )
    if template_id:
        db.session.execute(
            campaignMailTemplates.insert().values(
                campaign_id=campaign_id, template_id=template_id
            )
        )


def _sync_campaign_asset(campaign_id, asset_id):
    db.session.execute(
        campaignAssets.delete().where(campaignAssets.c.campaign_id == campaign_id)
    )
    if asset_id:
        db.session.execute(
            campaignAssets.insert().values(campaign_id=campaign_id, asset_id=asset_id)
        )


def _sync_campaign_clusters(campaign_id, cluster_ids):
    db.session.execute(
        campaignClusters.delete().where(campaignClusters.c.campaign_id == campaign_id)
    )
    for cid in cluster_ids:
        db.session.execute(
            campaignClusters.insert().values(campaign_id=campaign_id, cluster_id=cid)
        )


def _delete_campaign_associations(campaign_id):
    db.session.execute(
        campaignMailTemplates.delete().where(campaignMailTemplates.c.campaign_id == campaign_id)
    )
    db.session.execute(
        campaignAssets.delete().where(campaignAssets.c.campaign_id == campaign_id)
    )
    db.session.execute(
        campaignClusters.delete().where(campaignClusters.c.campaign_id == campaign_id)
    )


def _render_personalization(template_str: str, target: "Targets") -> str:
    """Fill campaign/template HTML with per-target fields (name, text)."""
    if not template_str:
        return ""
    env = Environment(loader=BaseLoader(), autoescape=True)
    return env.from_string(str(template_str)).render(
        name=(target.name or "").strip(),
        text=(target.personal_text or "").strip(),
    )


def _build_html_body(raw):
    if not raw:
        return ""
    s = str(raw)
    if "<" in s and ">" in s:
        return s
    lines = s.splitlines() or [s]
    esc = "<br/>".join(html_module.escape(line) for line in lines)
    return f"<p>{esc}</p>"


def _append_tracking_footer(html_inner, open_url, click_url):
    footer = (
        f'<p><a href="{click_url}">Click here</a></p>'
        f'<img src="{open_url}" width="1" height="1" alt="" />'
    )
    return html_inner + footer


def _send_smtp_html(asset, to_addr, subject, html_body):
    port = int(asset.port or 587)
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = asset.email
    msg["To"] = to_addr
    if port == 465:
        with smtplib.SMTP_SSL(asset.server, port, timeout=30) as smtp:
            smtp.login(asset.email, asset.password)
            smtp.sendmail(asset.email, [to_addr], msg.as_string())
        return
    with smtplib.SMTP(asset.server, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(asset.email, asset.password)
        smtp.sendmail(asset.email, [to_addr], msg.as_string())


@app.before_request
def check_authentication():
    endpoint = request.endpoint or ""
    if endpoint in ("login", "static", "track_open", "track_click"):
        return

    username = session.get("username")
    if not username or not Users.query.filter_by(username=username).first():
        return redirect(url_for('login'))
    
    # token = request.headers.get("Authorization")
    # if token != f"Bearer {API_KEY}":
    #     return jsonify({"error": "Unauthorized"}), 401

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        mapping = {
            "mail_server": "mail_server",
            "mail_port": "mail_port",
            "mail_username": "mail_username",
            "mail_password": "mail_password",
            "send_delay_seconds": "send_delay_seconds",
        }

        changed = 0
        cleared = 0
        for form_key, setting_name in mapping.items():
            raw = (request.form.get(form_key) or "").strip()
            if raw == "":
                if request.form.get(f"clear_{form_key}") == "on":
                    Settings.set(setting_name, "")
                    cleared += 1
                continue
            Settings.set(setting_name, raw)
            changed += 1

        if changed or cleared:
            flash(f"Settings saved. Updated: {changed}. Cleared: {cleared}.", "success")
        else:
            flash("No changes to save.", "info")
        return redirect(url_for("settings"))

    current = {
        "mail_server": Settings.get("mail_server", ""),
        "mail_port": Settings.get("mail_port", ""),
        "mail_username": Settings.get("mail_username", ""),
        "mail_password": Settings.get("mail_password", ""),
        "send_delay_seconds": Settings.get("send_delay_seconds", ""),
    }
    return render_template("settings.html", current=current)

@app.route("/campaigns", methods=["GET", "POST"])
def campaigns():
    user = _current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        if not name:
            flash("Campaign name is required.", "error")
            return redirect(url_for("campaigns"))
        if Campaigns.query.filter_by(name=name).first():
            flash("A campaign with that name already exists.", "error")
            return redirect(url_for("campaigns"))
        c = Campaigns(name=name, description=description, owner_id=user.id)
        db.session.add(c)
        db.session.commit()
        flash("Campaign created.", "success")
        return redirect(url_for("campaign_detail", campaign_id=c.id))

    rows = []
    for c in (
        Campaigns.query.filter_by(owner_id=user.id)
        .order_by(Campaigns.created_at.desc())
        .all()
    ):
        targets_n = (
            c.target_count_snapshot
            if c.locked_at is not None
            else _draft_target_count(c)
        )
        rows.append(
            {
                "campaign": c,
                "targets": targets_n,
                "opens": _distinct_event_count(c.id, "open"),
                "clicks": _distinct_event_count(c.id, "click"),
            }
        )
    return render_template("campaigns.html", rows=rows)


@app.route("/campaigns/<int:campaign_id>", methods=["GET", "POST"])
def campaign_detail(campaign_id):
    user = _current_user()
    if not user:
        return redirect(url_for("login"))

    campaign = Campaigns.query.get_or_404(campaign_id)
    if campaign.owner_id != user.id:
        flash("Not found.", "error")
        return redirect(url_for("campaigns"))

    all_clusters = Clusters.query.order_by(Clusters.name).all()
    all_templates = MailTemplates.query.order_by(MailTemplates.name).all()
    all_assets = Assets.query.order_by(Assets.email).all()

    selected_cluster_ids = {c.id for c in campaign.clusters}
    selected_template_id = campaign.mailTemplates[0].id if campaign.mailTemplates else None
    selected_asset_id = campaign.assets[0].id if campaign.assets else None

    editable = campaign.locked_at is None and campaign.status == "draft"

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if not editable and action not in ("copy",):
            flash("This campaign is locked after launch.", "error")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        if action == "save" and editable:
            description = (request.form.get("description") or "").strip() or None
            subject_draft = (request.form.get("subject_draft") or "").strip()
            body_draft = (request.form.get("body_draft") or "").strip()

            cluster_ids = request.form.getlist("cluster_ids", type=int)
            template_id = request.form.get("template_id", type=int)
            asset_id = request.form.get("asset_id", type=int)

            use_template = request.form.get("load_template_content") == "on"
            if use_template and template_id:
                mt = MailTemplates.query.get(template_id)
                if mt and not body_draft:
                    body_draft = mt.content or ""

            campaign.description = description
            campaign.subject_draft = subject_draft or None
            campaign.body_draft = body_draft or None

            _sync_campaign_clusters(campaign.id, cluster_ids)
            _sync_campaign_template(campaign.id, template_id)
            _sync_campaign_asset(campaign.id, asset_id)
            db.session.commit()
            flash("Campaign saved.", "success")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        if action == "launch" and editable:
            subject_draft = (request.form.get("subject_draft") or "").strip()
            body_draft = (request.form.get("body_draft") or "").strip()
            description = (request.form.get("description") or "").strip() or None
            cluster_ids = request.form.getlist("cluster_ids", type=int)
            template_id = request.form.get("template_id", type=int)
            asset_id = request.form.get("asset_id", type=int)

            campaign.description = description
            campaign.subject_draft = subject_draft or None
            campaign.body_draft = body_draft or None
            _sync_campaign_clusters(campaign.id, cluster_ids)
            _sync_campaign_template(campaign.id, template_id)
            _sync_campaign_asset(campaign.id, asset_id)
            db.session.flush()
            db.session.refresh(campaign)

            if not cluster_ids:
                flash("Select at least one cluster.", "error")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))
            if not template_id:
                flash("Select a mail template.", "error")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))
            if not asset_id:
                flash("Select a sender (asset).", "error")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))
            if not subject_draft or not body_draft:
                flash("Subject and body are required to launch.", "error")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))

            targets = _unique_targets_for_campaign(campaign)
            if not targets:
                flash("Selected clusters have no people.", "error")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))

            asset = Assets.query.get(asset_id)
            if not asset:
                flash("Sender not found.", "error")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))

            now = datetime.now(timezone.utc)
            public_base = (request.url_root or "/").rstrip("/") + "/"

            campaign.subject_snapshot = subject_draft
            campaign.body_snapshot = body_draft
            campaign.target_count_snapshot = len(targets)
            campaign.locked_at = now
            campaign.launched_at = now
            campaign.ended_at = now
            campaign.status = "completed"

            run = CampaignRuns(
                campaign_id=campaign.id,
                status="succeeded",
                started_at=now,
                ended_at=now,
                config_snapshot={"public_base_url": public_base},
            )
            db.session.add(run)
            db.session.flush()

            send_errors = []
            for t in targets:
                open_token = secrets.token_urlsafe(24)
                click_token = secrets.token_urlsafe(24)
                db.session.add(
                    TrackingTokens(
                        token=open_token,
                        campaign_run_id=run.id,
                        target_id=t.id,
                        purpose="open_pixel",
                    )
                )
                db.session.add(
                    TrackingTokens(
                        token=click_token,
                        campaign_run_id=run.id,
                        target_id=t.id,
                        purpose="click",
                    )
                )
                open_url = f"{public_base}track/o/{open_token}"
                click_url = f"{public_base}track/c/{click_token}"
                subj = _render_personalization(campaign.subject_snapshot or "", t)
                body_inner = _build_html_body(_render_personalization(campaign.body_snapshot or "", t))
                final_html = _append_tracking_footer(body_inner, open_url, click_url)
                db.session.add(
                    CampaignInteractions(
                        campaign_run_id=run.id,
                        target_id=t.id,
                        event_type="sent",
                        occurred_at=now,
                        campaign_metadata=None,
                    )
                )
                try:
                    _send_smtp_html(
                        asset,
                        t.email,
                        subj,
                        final_html,
                    )
                except Exception as ex:
                    send_errors.append(f"{t.email}: {ex}")

            db.session.commit()
            if send_errors:
                flash(
                    f"Launched. Some emails failed to send ({len(send_errors)}). First error: {send_errors[0]}",
                    "error",
                )
            else:
                flash("Campaign launched; emails sent (if SMTP accepted them).", "success")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        if action == "delete" and editable:
            _delete_campaign_associations(campaign.id)
            db.session.delete(campaign)
            db.session.commit()
            flash("Campaign deleted.", "success")
            return redirect(url_for("campaigns"))

        if action == "copy":
            base_name = f"{campaign.name} (copy)"
            new_name = base_name
            n = 2
            while Campaigns.query.filter_by(name=new_name).first():
                new_name = f"{campaign.name} (copy {n})"
                n += 1

            new_c = Campaigns(
                name=new_name,
                description=campaign.description,
                owner_id=user.id,
                status="draft",
                subject_draft=campaign.subject_snapshot or campaign.subject_draft,
                body_draft=campaign.body_snapshot or campaign.body_draft,
            )
            db.session.add(new_c)
            db.session.flush()

            for cl in campaign.clusters:
                db.session.execute(
                    campaignClusters.insert().values(
                        campaign_id=new_c.id, cluster_id=cl.id
                    )
                )
            if campaign.mailTemplates:
                db.session.execute(
                    campaignMailTemplates.insert().values(
                        campaign_id=new_c.id,
                        template_id=campaign.mailTemplates[0].id,
                    )
                )
            if campaign.assets:
                db.session.execute(
                    campaignAssets.insert().values(
                        campaign_id=new_c.id, asset_id=campaign.assets[0].id
                    )
                )
            db.session.commit()
            flash("Campaign duplicated as draft.", "success")
            return redirect(url_for("campaign_detail", campaign_id=new_c.id))

        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    return render_template(
        "campaign_detail.html",
        campaign=campaign,
        editable=editable,
        all_clusters=all_clusters,
        all_templates=all_templates,
        all_assets=all_assets,
        selected_cluster_ids=selected_cluster_ids,
        selected_template_id=selected_template_id,
        selected_asset_id=selected_asset_id,
    )


@app.route("/mail-templates", methods=["GET", "POST"])
def mail_templates():
    user = _current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not name:
            flash("Template name is required.", "error")
            return redirect(url_for("mail_templates"))
        if MailTemplates.query.filter_by(name=name).first():
            flash("A template with that name already exists.", "error")
            return redirect(url_for("mail_templates"))
        t = MailTemplates(name=name, content=content or None)
        db.session.add(t)
        db.session.commit()
        flash("Template created.", "success")
        return redirect(url_for("mail_templates"))

    items = MailTemplates.query.order_by(MailTemplates.name).all()
    return render_template("mail_templates.html", templates=items)


@app.route("/mail-templates/<int:template_id>", methods=["GET", "POST"])
def mail_template_edit(template_id):
    user = _current_user()
    if not user:
        return redirect(url_for("login"))

    t = MailTemplates.query.get_or_404(template_id)

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "delete":
            db.session.execute(
                campaignMailTemplates.delete().where(
                    campaignMailTemplates.c.template_id == template_id
                )
            )
            db.session.delete(t)
            db.session.commit()
            flash("Template deleted.", "success")
            return redirect(url_for("mail_templates"))

        name = (request.form.get("name") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("mail_template_edit", template_id=template_id))
        other = MailTemplates.query.filter(MailTemplates.name == name, MailTemplates.id != t.id).first()
        if other:
            flash("That name is already taken.", "error")
            return redirect(url_for("mail_template_edit", template_id=template_id))
        t.name = name
        t.content = content or None
        db.session.commit()
        flash("Template updated.", "success")
        return redirect(url_for("mail_template_edit", template_id=template_id))

    return render_template("mail_template_edit.html", template=t)


@app.route("/senders", methods=["GET", "POST"])
def senders():
    user = _current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        server = (request.form.get("server") or "").strip()
        password = request.form.get("password") or ""
        port = request.form.get("port", type=int)
        if not email or not server or not password:
            flash("Email, server, and password are required.", "error")
            return redirect(url_for("senders"))
        if Assets.query.filter_by(email=email).first():
            flash("A sender with that email already exists.", "error")
            return redirect(url_for("senders"))
        a = Assets(email=email, server=server, password=password, port=port)
        db.session.add(a)
        db.session.commit()
        flash("Sender created.", "success")
        return redirect(url_for("senders"))

    items = Assets.query.order_by(Assets.email).all()
    return render_template("senders.html", senders=items)


@app.route("/senders/<int:asset_id>", methods=["GET", "POST"])
def sender_edit(asset_id):
    user = _current_user()
    if not user:
        return redirect(url_for("login"))

    a = Assets.query.get_or_404(asset_id)

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "delete":
            db.session.execute(
                campaignAssets.delete().where(campaignAssets.c.asset_id == asset_id)
            )
            db.session.delete(a)
            db.session.commit()
            flash("Sender deleted.", "success")
            return redirect(url_for("senders"))

        email = (request.form.get("email") or "").strip()
        server = (request.form.get("server") or "").strip()
        password = request.form.get("password") or ""
        port = request.form.get("port", type=int)
        if not email or not server:
            flash("Email and server are required.", "error")
            return redirect(url_for("sender_edit", asset_id=asset_id))
        other = Assets.query.filter(Assets.email == email, Assets.id != a.id).first()
        if other:
            flash("That email is already used by another sender.", "error")
            return redirect(url_for("sender_edit", asset_id=asset_id))
        a.email = email
        a.server = server
        if password:
            a.password = password
        a.port = port
        db.session.commit()
        flash("Sender updated.", "success")
        return redirect(url_for("sender_edit", asset_id=asset_id))

    return render_template("sender_edit.html", sender=a)


@app.route("/track/o/<token>")
def track_open(token):
    tt = TrackingTokens.query.filter_by(token=token, purpose="open_pixel").first()
    if not tt:
        return Response(PIXEL_GIF, mimetype="image/gif")

    now = datetime.now(timezone.utc)
    db.session.add(
        CampaignInteractions(
            campaign_run_id=tt.campaign_run_id,
            target_id=tt.target_id,
            event_type="open",
            occurred_at=now,
            campaign_metadata=None,
        )
    )
    db.session.commit()
    return Response(PIXEL_GIF, mimetype="image/gif")


@app.route("/track/c/<token>")
def track_click(token):
    tt = TrackingTokens.query.filter_by(token=token, purpose="click").first()
    redirect_url = app.config.get("CLICK_REDIRECT_URL", "https://example.com")
    if not tt:
        return redirect(redirect_url, code=302)

    now = datetime.now(timezone.utc)
    db.session.add(
        CampaignInteractions(
            campaign_run_id=tt.campaign_run_id,
            target_id=tt.target_id,
            event_type="click",
            occurred_at=now,
            campaign_metadata=None,
        )
    )
    db.session.commit()
    return redirect(redirect_url, code=302)


@app.route("/clusters", methods=["GET", "POST"])
def clusters_list():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        if not name:
            flash("Cluster name is required.", "error")
            return redirect(url_for("clusters_list"))
        if Clusters.query.filter_by(name=name).first():
            flash("A cluster with that name already exists.", "error")
            return redirect(url_for("clusters_list"))
        c = Clusters(name=name, description=description)
        db.session.add(c)
        db.session.commit()
        flash("Cluster created.", "success")
        return redirect(url_for("cluster_detail", cluster_id=c.id))

    all_clusters = Clusters.query.order_by(Clusters.name).all()
    rows = [(c, Targets.query.filter_by(cluster_id=c.id).count()) for c in all_clusters]
    return render_template("clusters.html", clusters=rows)


@app.route("/clusters/<int:cluster_id>", methods=["GET", "POST"])
def cluster_detail(cluster_id):
    cluster = Clusters.query.get_or_404(cluster_id)

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "update_cluster":
            description = (request.form.get("description") or "").strip() or None
            cluster.description = description
            db.session.commit()
            flash("Cluster updated.", "success")
            return redirect(url_for("cluster_detail", cluster_id=cluster_id))
        if action == "delete_cluster":
            db.session.execute(
                campaignClusters.delete().where(campaignClusters.c.cluster_id == cluster_id)
            )
            db.session.delete(cluster)
            db.session.commit()
            flash("Cluster deleted.", "success")
            return redirect(url_for("clusters_list"))
        if action == "add_target":
            email = (request.form.get("email") or "").strip()
            name = (request.form.get("name") or "").strip() or None
            personal_text = (request.form.get("personal_text") or "").strip() or None
            if not email:
                flash("Email is required.", "error")
                return redirect(url_for("cluster_detail", cluster_id=cluster_id))
            if Targets.query.filter_by(cluster_id=cluster_id, email=email).first():
                flash("That email is already in this cluster.", "error")
                return redirect(url_for("cluster_detail", cluster_id=cluster_id))
            t = Targets(
                cluster_id=cluster_id,
                email=email,
                name=name,
                personal_text=personal_text,
            )
            db.session.add(t)
            db.session.commit()
            flash("Person added.", "success")
            return redirect(url_for("cluster_detail", cluster_id=cluster_id))
        if action == "delete_target":
            tid = request.form.get("target_id", type=int)
            t = Targets.query.filter_by(id=tid, cluster_id=cluster_id).first()
            if t:
                db.session.delete(t)
                db.session.commit()
                flash("Person removed.", "success")
            return redirect(url_for("cluster_detail", cluster_id=cluster_id))

    targets = (
        Targets.query.filter_by(cluster_id=cluster_id)
        .order_by(Targets.email)
        .all()
    )
    return render_template(
        "cluster_detail.html",
        cluster=cluster,
        targets=targets,
    )


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
    return render_template("help.html")

