from flask import *

app = Flask(__name__)
app.secret = "password"

@app.route("/")
def main():
    return render_template("base.html")

