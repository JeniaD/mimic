import secrets
from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for

from mimic.extensions import db
from mimic.models import (
    Assets,
    CampaignInteractions,
    CampaignRuns,
    Campaigns,
    Clusters,
    MailTemplates,
    Targets,
    TrackingTokens,
    campaignAssets,
    campaignClusters,
    campaignMailTemplates,
)
from mimic.utils.auth import current_user
from mimic.utils import campaign as campaign_util
from mimic.utils import email as email_util


def register(app):
    @app.route("/campaigns", methods=["GET", "POST"])
    def campaigns():
        user = current_user()
        if not user:
            return redirect(url_for("login"))

        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip() or None
            if not name:
                flash("Campaign name is required.", "error")
                return redirect(url_for("campaigns"))
            if Campaigns.query.filter_by(name=name).first():
                flash("A campaign with that name already exists.", "error")
                return redirect(url_for("campaigns"))
            c = Campaigns(name=name, description=description, owner_id=user.id)
            db.session.add(c)
            db.session.commit()
            flash("Campaign created.", "success")
            return redirect(url_for("campaign_detail", campaign_id=c.id))

        rows = []
        for c in (
            Campaigns.query.filter_by(owner_id=user.id)
            .order_by(Campaigns.created_at.desc())
            .all()
        ):
            targets_n = (
                c.target_count_snapshot
                if c.locked_at is not None
                else campaign_util.draft_target_count(c)
            )
            rows.append(
                {
                    "campaign": c,
                    "targets": targets_n,
                    "opens": campaign_util.distinct_event_count(c.id, "open"),
                    "clicks": campaign_util.distinct_event_count(c.id, "click"),
                }
            )
        return render_template("campaigns.html", rows=rows)

    @app.route("/campaigns/<int:campaign_id>", methods=["GET", "POST"])
    def campaign_detail(campaign_id):
        user = current_user()
        if not user:
            return redirect(url_for("login"))

        campaign = Campaigns.query.get_or_404(campaign_id)
        if campaign.owner_id != user.id:
            flash("Not found.", "error")
            return redirect(url_for("campaigns"))

        all_clusters = Clusters.query.order_by(Clusters.name).all()
        all_templates = MailTemplates.query.order_by(MailTemplates.name).all()
        all_assets = Assets.query.order_by(Assets.email).all()

        selected_cluster_ids = {c.id for c in campaign.clusters}
        selected_template_id = (
            campaign.mailTemplates[0].id if campaign.mailTemplates else None
        )
        selected_asset_id = campaign.assets[0].id if campaign.assets else None

        editable = campaign.locked_at is None and campaign.status == "draft"

        if request.method == "POST":
            action = (request.form.get("action") or "").strip()
            if not editable and action not in ("copy",):
                flash("This campaign is locked after launch.", "error")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))

            if action == "save" and editable:
                description = (request.form.get("description") or "").strip() or None
                subject_draft = (request.form.get("subject_draft") or "").strip()
                body_draft = (request.form.get("body_draft") or "").strip()

                cluster_ids = request.form.getlist("cluster_ids", type=int)
                template_id = request.form.get("template_id", type=int)
                asset_id = request.form.get("asset_id", type=int)

                use_template = request.form.get("load_template_content") == "on"
                if use_template and template_id:
                    mt = MailTemplates.query.get(template_id)
                    if mt and not body_draft:
                        body_draft = mt.content or ""

                campaign.description = description
                campaign.subject_draft = subject_draft or None
                campaign.body_draft = body_draft or None

                campaign_util.sync_campaign_clusters(campaign.id, cluster_ids)
                campaign_util.sync_campaign_template(campaign.id, template_id)
                campaign_util.sync_campaign_asset(campaign.id, asset_id)
                db.session.commit()
                flash("Campaign saved.", "success")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))

            if action == "launch" and editable:
                subject_draft = (request.form.get("subject_draft") or "").strip()
                body_draft = (request.form.get("body_draft") or "").strip()
                description = (request.form.get("description") or "").strip() or None
                cluster_ids = request.form.getlist("cluster_ids", type=int)
                template_id = request.form.get("template_id", type=int)
                asset_id = request.form.get("asset_id", type=int)

                campaign.description = description
                campaign.subject_draft = subject_draft or None
                campaign.body_draft = body_draft or None
                campaign_util.sync_campaign_clusters(campaign.id, cluster_ids)
                campaign_util.sync_campaign_template(campaign.id, template_id)
                campaign_util.sync_campaign_asset(campaign.id, asset_id)
                db.session.flush()
                db.session.refresh(campaign)

                if not cluster_ids:
                    flash("Select at least one cluster.", "error")
                    return redirect(url_for("campaign_detail", campaign_id=campaign_id))
                if not template_id:
                    flash("Select a mail template.", "error")
                    return redirect(url_for("campaign_detail", campaign_id=campaign_id))
                if not asset_id:
                    flash("Select a sender (asset).", "error")
                    return redirect(url_for("campaign_detail", campaign_id=campaign_id))
                if not subject_draft or not body_draft:
                    flash("Subject and body are required to launch.", "error")
                    return redirect(url_for("campaign_detail", campaign_id=campaign_id))

                targets = campaign_util.unique_targets_for_campaign(campaign)
                if not targets:
                    flash("Selected clusters have no people.", "error")
                    return redirect(url_for("campaign_detail", campaign_id=campaign_id))

                asset = Assets.query.get(asset_id)
                if not asset:
                    flash("Sender not found.", "error")
                    return redirect(url_for("campaign_detail", campaign_id=campaign_id))

                now = datetime.now(timezone.utc)
                public_base = (request.url_root or "/").rstrip("/") + "/"

                campaign.subject_snapshot = subject_draft
                campaign.body_snapshot = body_draft
                campaign.target_count_snapshot = len(targets)
                campaign.locked_at = now
                campaign.launched_at = now
                campaign.ended_at = now
                campaign.status = "completed"

                run = CampaignRuns(
                    campaign_id=campaign.id,
                    status="succeeded",
                    started_at=now,
                    ended_at=now,
                    config_snapshot={"public_base_url": public_base},
                )
                db.session.add(run)
                db.session.flush()

                send_errors = []
                for t in targets:
                    open_token = secrets.token_urlsafe(24)
                    click_token = secrets.token_urlsafe(24)
                    db.session.add(
                        TrackingTokens(
                            token=open_token,
                            campaign_run_id=run.id,
                            target_id=t.id,
                            purpose="open_pixel",
                        )
                    )
                    db.session.add(
                        TrackingTokens(
                            token=click_token,
                            campaign_run_id=run.id,
                            target_id=t.id,
                            purpose="click",
                        )
                    )
                    open_url = f"{public_base}track/o/{open_token}"
                    click_url = f"{public_base}track/c/{click_token}"
                    subj = email_util.render_personalization(
                        campaign.subject_snapshot or "", t
                    )
                    body_inner = email_util.build_html_body(
                        email_util.render_personalization(
                            campaign.body_snapshot or "", t
                        )
                    )
                    final_html = email_util.append_tracking_footer(
                        body_inner, open_url, click_url
                    )
                    db.session.add(
                        CampaignInteractions(
                            campaign_run_id=run.id,
                            target_id=t.id,
                            event_type="sent",
                            occurred_at=now,
                            campaign_metadata=None,
                        )
                    )
                    try:
                        email_util.send_smtp_html(asset, t.email, subj, final_html)
                    except Exception as ex:
                        send_errors.append(f"{t.email}: {ex}")

                db.session.commit()
                if send_errors:
                    flash(
                        f"Launched. Some emails failed to send ({len(send_errors)}). "
                        f"First error: {send_errors[0]}",
                        "error",
                    )
                else:
                    flash(
                        "Campaign launched; emails sent (if SMTP accepted them).",
                        "success",
                    )
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))

            if action == "delete" and editable:
                campaign_util.delete_campaign_associations(campaign.id)
                db.session.delete(campaign)
                db.session.commit()
                flash("Campaign deleted.", "success")
                return redirect(url_for("campaigns"))

            if action == "copy":
                base_name = f"{campaign.name} (copy)"
                new_name = base_name
                n = 2
                while Campaigns.query.filter_by(name=new_name).first():
                    new_name = f"{campaign.name} (copy {n})"
                    n += 1

                new_c = Campaigns(
                    name=new_name,
                    description=campaign.description,
                    owner_id=user.id,
                    status="draft",
                    subject_draft=campaign.subject_snapshot or campaign.subject_draft,
                    body_draft=campaign.body_snapshot or campaign.body_draft,
                )
                db.session.add(new_c)
                db.session.flush()

                for cl in campaign.clusters:
                    db.session.execute(
                        campaignClusters.insert().values(
                            campaign_id=new_c.id, cluster_id=cl.id
                        )
                    )
                if campaign.mailTemplates:
                    db.session.execute(
                        campaignMailTemplates.insert().values(
                            campaign_id=new_c.id,
                            template_id=campaign.mailTemplates[0].id,
                        )
                    )
                if campaign.assets:
                    db.session.execute(
                        campaignAssets.insert().values(
                            campaign_id=new_c.id, asset_id=campaign.assets[0].id
                        )
                    )
                db.session.commit()
                flash("Campaign duplicated as draft.", "success")
                return redirect(url_for("campaign_detail", campaign_id=new_c.id))

            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        return render_template(
            "campaign_detail.html",
            campaign=campaign,
            editable=editable,
            all_clusters=all_clusters,
            all_templates=all_templates,
            all_assets=all_assets,
            selected_cluster_ids=selected_cluster_ids,
            selected_template_id=selected_template_id,
            selected_asset_id=selected_asset_id,
        )
