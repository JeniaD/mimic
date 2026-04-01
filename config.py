# MIMIC app configuration.
#
# Engagement callbacks (open/click tracking, etc.) are handled by this service.
# A separate listener process (e.g. another Flask app on another port) may be
# added later for raw connections and hosted simulation pages (e.g. landing pages).

secret = "password"
SQLALCHEMY_DATABASE_URI = "sqlite:///database.sqlite"
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = "supersecretkey"
DEFAULT_USER = "mimic"

# Where click-track links redirect after logging (authorized simulation landing page).
CLICK_REDIRECT_URL = "https://example.com"
