"""
KubeWatch - Web Dashboard
Flask app serving the monitoring dashboard.
"""

import json
from flask import Flask, render_template, jsonify
from src.collectors.k8s_connector import connect, get_full_snapshot, enrich_snapshot
from src.collectors.log_collector import get_all_pod_logs, get_error_logs, get_pod_logs
from src.collectors.metrics_collector import get_pod_metrics, get_node_metrics
from src.alerting.alert_engine import AlertEngine

app = Flask(__name__,
    template_folder="templates",
    static_folder="static",
)

# Global state
apis = None
alert_engine = AlertEngine()


def get_apis():
    global apis
    if apis is None:
        apis = connect()
    return apis


@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("index.html")


@app.route("/api/snapshot")
def api_snapshot():
    """API: Get full cluster snapshot with alerts and health scores."""
    try:
        k8s = get_apis()
        snapshot = get_full_snapshot(k8s, namespace="default")
        snapshot = enrich_snapshot(snapshot)

        # Get metrics
        pod_metrics = get_pod_metrics(k8s, namespace="default")
        node_metrics = get_node_metrics(k8s)

        # Evaluate alerts
        alerts = alert_engine.evaluate(snapshot, pod_metrics)
        health_scores = alert_engine.get_health_scores(snapshot, pod_metrics)

        return jsonify({
            "status": "ok",
            "snapshot": snapshot,
            "metrics": {
                "pods": pod_metrics,
                "nodes": node_metrics,
            },
            "alerts": alerts,
            "health_scores": health_scores,
            "alert_history": alert_engine.alert_history[-50:],
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/pods")
def api_pods():
    """API: Get all pods."""
    try:
        k8s = get_apis()
        from src.collectors.k8s_connector import get_pods
        pods = get_pods(k8s, namespace="default")
        return jsonify({"status": "ok", "pods": pods})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/logs/<pod_name>")
def api_pod_logs(pod_name):
    """API: Get logs for a specific pod."""
    try:
        k8s = get_apis()
        logs = get_pod_logs(k8s, pod_name, namespace="default", lines=200)
        return jsonify({"status": "ok", "logs": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/errors")
def api_errors():
    """API: Get all error logs."""
    try:
        k8s = get_apis()
        errors = get_error_logs(k8s, namespace="default")
        return jsonify({"status": "ok", "errors": errors})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/alerts")
def api_alerts():
    """API: Get current alerts and history."""
    return jsonify({
        "status": "ok",
        "current": alert_engine.alerts,
        "history": alert_engine.alert_history[-50:],
    })


def run_dashboard(host="0.0.0.0", port=8080):
    """Start the dashboard server."""
    print(f"\n  Dashboard running at: http://localhost:{port}")
    print(f"  Press Ctrl+C to stop\n")
    app.run(host=host, port=port, debug=False)
