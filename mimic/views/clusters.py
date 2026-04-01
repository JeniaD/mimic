from flask import flash, redirect, render_template, request, url_for

from mimic.extensions import db
from mimic.models import Clusters, Targets, campaignClusters


def register(app):
    @app.route("/clusters", methods=["GET", "POST"])
    def clusters_list():
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip() or None
            if not name:
                flash("Cluster name is required.", "error")
                return redirect(url_for("clusters_list"))
            if Clusters.query.filter_by(name=name).first():
                flash("A cluster with that name already exists.", "error")
                return redirect(url_for("clusters_list"))
            c = Clusters(name=name, description=description)
            db.session.add(c)
            db.session.commit()
            flash("Cluster created.", "success")
            return redirect(url_for("cluster_detail", cluster_id=c.id))

        all_clusters = Clusters.query.order_by(Clusters.name).all()
        rows = [(c, Targets.query.filter_by(cluster_id=c.id).count()) for c in all_clusters]
        return render_template("clusters.html", clusters=rows)

    @app.route("/clusters/<int:cluster_id>", methods=["GET", "POST"])
    def cluster_detail(cluster_id):
        cluster = Clusters.query.get_or_404(cluster_id)

        if request.method == "POST":
            action = (request.form.get("action") or "").strip()
            if action == "update_cluster":
                description = (request.form.get("description") or "").strip() or None
                cluster.description = description
                db.session.commit()
                flash("Cluster updated.", "success")
                return redirect(url_for("cluster_detail", cluster_id=cluster_id))
            if action == "delete_cluster":
                db.session.execute(
                    campaignClusters.delete().where(campaignClusters.c.cluster_id == cluster_id)
                )
                db.session.delete(cluster)
                db.session.commit()
                flash("Cluster deleted.", "success")
                return redirect(url_for("clusters_list"))
            if action == "add_target":
                email = (request.form.get("email") or "").strip()
                name = (request.form.get("name") or "").strip() or None
                personal_text = (request.form.get("personal_text") or "").strip() or None
                if not email:
                    flash("Email is required.", "error")
                    return redirect(url_for("cluster_detail", cluster_id=cluster_id))
                if Targets.query.filter_by(cluster_id=cluster_id, email=email).first():
                    flash("That email is already in this cluster.", "error")
                    return redirect(url_for("cluster_detail", cluster_id=cluster_id))
                t = Targets(
                    cluster_id=cluster_id,
                    email=email,
                    name=name,
                    personal_text=personal_text,
                )
                db.session.add(t)
                db.session.commit()
                flash("Person added.", "success")
                return redirect(url_for("cluster_detail", cluster_id=cluster_id))
            if action == "delete_target":
                tid = request.form.get("target_id", type=int)
                t = Targets.query.filter_by(id=tid, cluster_id=cluster_id).first()
                if t:
                    db.session.delete(t)
                    db.session.commit()
                    flash("Person removed.", "success")
                return redirect(url_for("cluster_detail", cluster_id=cluster_id))

        targets = (
            Targets.query.filter_by(cluster_id=cluster_id).order_by(Targets.email).all()
        )
        return render_template(
            "cluster_detail.html",
            cluster=cluster,
            targets=targets,
        )
