# MIMIC

Web app for authorized red-team social engineering simulations (e.g. phishing awareness exercises): manage target groups, mail templates, SMTP senders, and campaigns with per-recipient personalization and open/click tracking.

**Use only with explicit written scope and approval.** Unauthorized use may violate law and organizational policy.

## Stack

| Layer | Technology |
|--------|-------------|
| Runtime | Python 3 |
| Web | [Flask](https://flask.palletsprojects.com/) |
| ORM / DB | [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/), SQLite (`database.sqlite` by default) |
| Templates | Jinja2 (Flask + per-email personalization) |
| UI | HTML, [Pure.css](https://purecss.io/), custom CSS |

Data model includes users, clusters (targets), mail templates, sender identities (SMTP), campaigns (draft/locked), campaign runs, tracking tokens, and interaction events.

## Project layout

| Path | Role |
|------|------|
| `app.py` | Thin entry: `app = create_app()` for `flask --app app run` |
| `mimic/__init__.py` | `create_app()` — config, `db`, route registration, optional bootstrap |
| `mimic/extensions.py` | Shared `SQLAlchemy()` instance |
| `mimic/models.py` | ORM models and association tables |
| `mimic/bootstrap.py` | Default DB + optional user from config |
| `mimic/utils/` | Auth helper, campaign helpers, email render/send |
| `mimic/views/` | One module per area (`register(app)` adds routes) |
| `templates/`, `static/` | Jinja templates and CSS |
| `config.py` | `SECRET_KEY`, DB URI, `CLICK_REDIRECT_URL`, etc. |

## Features (high level)

- **Clusters** — Recipients with email plus template fields (`name`, `text`) for Jinja placeholders.
- **Mail templates** — Reusable bodies; optional fill into campaign draft on save.
- **Senders** — Per-identity SMTP (e.g. port 587 + STARTTLS or 465 + SSL).
- **Campaigns** — Select clusters, one template, one sender; subject/body as Jinja; **launch** locks the campaign, snapshots content, creates a run, sends mail, appends tracking link + open pixel.
- **Tracking** — HTTP endpoints log opens and clicks; stats show distinct recipients with opens/clicks.
- **Settings** — Optional global mail-related key/value storage.

## Quick start

```bash
cd mimic
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Configure `config.py` (at minimum `SECRET_KEY` and, for production, database path and secrets). Optionally set `DEFAULT_PASSWORD` for the initial user or rely on `secret` for first bootstrap (see `mimic/bootstrap.py`).

Initialize the database and create the admin user interactively:

```bash
python init.py
```

Run the app (from the repo root):

```bash
flask --app app run
```

Alternatively: `python -c "from mimic import create_app; create_app().run(debug=True)"` or `flask --app 'mimic:create_app' run`.

Open the URL shown (e.g. `http://127.0.0.1:5000`), sign in, and follow **Help** in the UI for the full workflow.

## Showcase / demo notes

- Replace default **SECRET_KEY** and credentials before any public demo.
- Tracking links in mail use the **URL you use when launching**; for recipients outside localhost, use a reachable hostname or tunnel so opens/clicks resolve to this app.
- Click-through redirects use `CLICK_REDIRECT_URL` in `config.py`.
