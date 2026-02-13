"""
KubeWatch - Configuration
"""

import os

# Kubernetes
KUBECONFIG = os.environ.get("KUBECONFIG", os.path.expanduser("~/.kube/config"))
NAMESPACE = os.environ.get("KUBEWATCH_NAMESPACE", "default")
WATCH_ALL_NAMESPACES = os.environ.get("KUBEWATCH_ALL_NS", "false").lower() == "true"

# Collection interval (seconds)
COLLECT_INTERVAL = int(os.environ.get("KUBEWATCH_INTERVAL", "15"))

# Prometheus
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

# Dashboard
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))

# Alerting thresholds
CPU_WARN_PERCENT = 70
CPU_CRIT_PERCENT = 90
MEMORY_WARN_PERCENT = 75
MEMORY_CRIT_PERCENT = 90
RESTART_WARN_COUNT = 3
RESTART_CRIT_COUNT = 5

# Slack webhook (optional)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# Project info
PROJECT_NAME = "KubeWatch"
VERSION = "1.0.0"
AUTHOR = "SULIMAN KHAN"
