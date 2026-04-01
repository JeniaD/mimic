from sqlalchemy import func

from mimic.extensions import db
from mimic.models import (
    CampaignInteractions,
    CampaignRuns,
    Targets,
    campaignAssets,
    campaignClusters,
    campaignMailTemplates,
)


def unique_targets_for_campaign(campaign):
    cluster_ids = [c.id for c in campaign.clusters]
    if not cluster_ids:
        return []
    seen = set()
    out = []
    for t in (
        Targets.query.filter(Targets.cluster_id.in_(cluster_ids))
        .order_by(Targets.id)
        .all()
    ):
        key = (t.email or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def distinct_event_count(campaign_id, event_type):
    run_ids = [r.id for r in CampaignRuns.query.filter_by(campaign_id=campaign_id).all()]
    if not run_ids:
        return 0
    n = (
        db.session.query(func.count(func.distinct(CampaignInteractions.target_id)))
        .filter(
            CampaignInteractions.campaign_run_id.in_(run_ids),
            CampaignInteractions.event_type == event_type,
            CampaignInteractions.target_id.isnot(None),
        )
        .scalar()
    )
    return int(n or 0)


def draft_target_count(campaign):
    return len(unique_targets_for_campaign(campaign))


def sync_campaign_template(campaign_id, template_id):
    db.session.execute(
        campaignMailTemplates.delete().where(campaignMailTemplates.c.campaign_id == campaign_id)
    )
    if template_id:
        db.session.execute(
            campaignMailTemplates.insert().values(
                campaign_id=campaign_id, template_id=template_id
            )
        )


def sync_campaign_asset(campaign_id, asset_id):
    db.session.execute(
        campaignAssets.delete().where(campaignAssets.c.campaign_id == campaign_id)
    )
    if asset_id:
        db.session.execute(
            campaignAssets.insert().values(campaign_id=campaign_id, asset_id=asset_id)
        )


def sync_campaign_clusters(campaign_id, cluster_ids):
    db.session.execute(
        campaignClusters.delete().where(campaignClusters.c.campaign_id == campaign_id)
    )
    for cid in cluster_ids:
        db.session.execute(
            campaignClusters.insert().values(campaign_id=campaign_id, cluster_id=cid)
        )


def delete_campaign_associations(campaign_id):
    db.session.execute(
        campaignMailTemplates.delete().where(campaignMailTemplates.c.campaign_id == campaign_id)
    )
    db.session.execute(
        campaignAssets.delete().where(campaignAssets.c.campaign_id == campaign_id)
    )
    db.session.execute(
        campaignClusters.delete().where(campaignClusters.c.campaign_id == campaign_id)
    )
