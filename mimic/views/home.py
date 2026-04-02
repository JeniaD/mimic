from flask import render_template


def register(app):
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/help")
    def help():
        return render_template("help.html")
