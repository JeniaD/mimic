from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from mimic.models import Users


def register(app):
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
                return redirect(url_for("index"))
            flash("Invalid username or password.", "error")

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.before_request
    def check_authentication():
        endpoint = request.endpoint or ""
        if endpoint in ("login", "static", "track_open", "track_click"):
            return

        username = session.get("username")
        if not username or not Users.query.filter_by(username=username).first():
            return redirect(url_for("login"))
