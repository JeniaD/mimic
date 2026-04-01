from flask import flash, redirect, render_template, request, url_for

from mimic.models import Settings


def register(app):
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
