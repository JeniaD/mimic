"""HTTP route registration. Each submodule exposes ``register(app)``."""

from . import (
    auth_views,
    campaigns,
    clusters,
    home,
    mail_templates,
    senders,
    settings,
    tracking,
)


def register_views(app):
    """Attach all URL handlers to the Flask app (preserves legacy endpoint names)."""
    for register in (
        auth_views.register,
        home.register,
        settings.register,
        campaigns.register,
        clusters.register,
        mail_templates.register,
        senders.register,
        tracking.register,
    ):
        register(app)
