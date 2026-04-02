import os

from flask import Flask

from mimic.bootstrap import ensure_db_and_default_user
from mimic.extensions import db
from mimic.views import register_views


def create_app(config_path=None, bootstrap_defaults=True):
    """Application factory.

    :param bootstrap_defaults: If True (default), create tables and optional
        default user from ``config`` (same as legacy ``app.py``). Set False for
        ``init.py`` so an admin password can be set interactively first.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
    )

    cfg = config_path or os.path.join(root, "config.py")
    app.config.from_pyfile(cfg)

    db.init_app(app)
    register_views(app)

    with app.app_context():
        if bootstrap_defaults:
            ensure_db_and_default_user(app)
        else:
            db.create_all()

    return app
