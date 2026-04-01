from flask import flash, redirect, render_template, request, url_for

from mimic.extensions import db
from mimic.models import Assets, campaignAssets
from mimic.utils.auth import current_user


def register(app):
    @app.route("/senders", methods=["GET", "POST"])
    def senders():
        user = current_user()
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
        user = current_user()
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
