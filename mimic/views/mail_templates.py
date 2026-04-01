from flask import flash, redirect, render_template, request, url_for

from mimic.extensions import db
from mimic.models import MailTemplates, campaignMailTemplates
from mimic.utils.auth import current_user


def register(app):
    @app.route("/mail-templates", methods=["GET", "POST"])
    def mail_templates():
        user = current_user()
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
        user = current_user()
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
            other = MailTemplates.query.filter(
                MailTemplates.name == name, MailTemplates.id != t.id
            ).first()
            if other:
                flash("That name is already taken.", "error")
                return redirect(url_for("mail_template_edit", template_id=template_id))
            t.name = name
            t.content = content or None
            db.session.commit()
            flash("Template updated.", "success")
            return redirect(url_for("mail_template_edit", template_id=template_id))

        return render_template("mail_template_edit.html", template=t)
