from datetime import datetime, timezone

from flask import Response, current_app, redirect

from mimic.constants import PIXEL_GIF
from mimic.extensions import db
from mimic.models import CampaignInteractions, TrackingTokens


def register(app):
    @app.route("/track/o/<token>")
    def track_open(token):
        tt = TrackingTokens.query.filter_by(token=token, purpose="open_pixel").first()
        if not tt:
            return Response(PIXEL_GIF, mimetype="image/gif")

        now = datetime.now(timezone.utc)
        db.session.add(
            CampaignInteractions(
                campaign_run_id=tt.campaign_run_id,
                target_id=tt.target_id,
                event_type="open",
                occurred_at=now,
                campaign_metadata=None,
            )
        )
        db.session.commit()
        return Response(PIXEL_GIF, mimetype="image/gif")

    @app.route("/track/c/<token>")
    def track_click(token):
        tt = TrackingTokens.query.filter_by(token=token, purpose="click").first()
        redirect_url = current_app.config.get("CLICK_REDIRECT_URL", "https://example.com")
        if not tt:
            return redirect(redirect_url, code=302)

        now = datetime.now(timezone.utc)
        db.session.add(
            CampaignInteractions(
                campaign_run_id=tt.campaign_run_id,
                target_id=tt.target_id,
                event_type="click",
                occurred_at=now,
                campaign_metadata=None,
            )
        )
        db.session.commit()
        return redirect(redirect_url, code=302)
