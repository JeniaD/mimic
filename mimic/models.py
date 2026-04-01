from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint

from mimic.extensions import db

campaignMailTemplates = db.Table(
    "campaignMailTemplates",
    db.Column("campaign_id", db.Integer, db.ForeignKey("campaigns.id")),
    db.Column("template_id", db.Integer, db.ForeignKey("mail_templates.id")),
)
campaignClusters = db.Table(
    "campaignClusters",
    db.Column("campaign_id", db.Integer, db.ForeignKey("campaigns.id")),
    db.Column("cluster_id", db.Integer, db.ForeignKey("clusters.id")),
)
campaignAssets = db.Table(
    "campaignAssets",
    db.Column("campaign_id", db.Integer, db.ForeignKey("campaigns.id")),
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id")),
)


class Users(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    campaigns = db.relationship("Campaigns", back_populates="owner")


class Campaigns(db.Model):
    __tablename__ = "campaigns"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    owner = db.relationship("Users", back_populates="campaigns")

    mailTemplates = db.relationship(
        "MailTemplates", secondary=campaignMailTemplates, backref="campaigns"
    )
    assets = db.relationship("Assets", secondary=campaignAssets, backref="campaigns")
    clusters = db.relationship("Clusters", secondary=campaignClusters, backref="campaigns")

    status = db.Column(db.String(50), nullable=False, default="draft")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    launched_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)

    subject_draft = db.Column(db.Text, nullable=True)
    body_draft = db.Column(db.Text, nullable=True)

    subject_snapshot = db.Column(db.Text, nullable=True)
    body_snapshot = db.Column(db.Text, nullable=True)

    target_count_snapshot = db.Column(db.Integer, nullable=True)

    runs = db.relationship(
        "CampaignRuns", back_populates="campaign", cascade="all, delete-orphan"
    )


class MailTemplates(db.Model):
    __tablename__ = "mail_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    content = db.Column(db.Text)


class Assets(db.Model):
    __tablename__ = "assets"
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
    email = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=True)
    personal_text = db.Column(db.Text, nullable=True)

    cluster = db.relationship("Clusters", back_populates="targets")


class CampaignRuns(db.Model):
    __tablename__ = "campaign_runs"
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False, index=True)

    status = db.Column(db.String(50), nullable=False, default="running")
    started_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    ended_at = db.Column(db.DateTime, nullable=True)

    config_snapshot = db.Column(db.JSON, nullable=True)

    campaign = db.relationship("Campaigns", back_populates="runs")
    interactions = db.relationship(
        "CampaignInteractions",
        back_populates="campaign_run",
        cascade="all, delete-orphan",
    )
    tracking_tokens = db.relationship(
        "TrackingTokens",
        back_populates="campaign_run",
        cascade="all, delete-orphan",
    )


class CampaignInteractions(db.Model):
    __tablename__ = "campaign_interactions"
    id = db.Column(db.Integer, primary_key=True)
    campaign_run_id = db.Column(
        db.Integer, db.ForeignKey("campaign_runs.id"), nullable=False, index=True
    )
    target_id = db.Column(db.Integer, db.ForeignKey("targets.id"), nullable=True, index=True)

    event_type = db.Column(db.String(50), nullable=False)
    occurred_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    campaign_metadata = db.Column(db.JSON, nullable=True)

    campaign_run = db.relationship("CampaignRuns", back_populates="interactions")
    target = db.relationship("Targets")


class TrackingTokens(db.Model):
    __tablename__ = "tracking_tokens"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    campaign_run_id = db.Column(
        db.Integer, db.ForeignKey("campaign_runs.id"), nullable=False, index=True
    )
    target_id = db.Column(db.Integer, db.ForeignKey("targets.id"), nullable=True, index=True)
    purpose = db.Column(db.String(50), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

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
