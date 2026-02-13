"""
KubeWatch - Alert Engine
Detects problems: high CPU, memory leaks, crash loops, pod failures.
Calculates health scores per service.
"""

import json
import requests
from datetime import datetime, timezone
from colorama import Fore, Style, init

init(autoreset=True)

# Alert severity levels
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"


class AlertEngine:
    def __init__(self, config=None):
        self.alerts = []
        self.alert_history = []
        self.config = config or {}
        self.cpu_warn = self.config.get("cpu_warn", 70)
        self.cpu_crit = self.config.get("cpu_crit", 90)
        self.mem_warn = self.config.get("mem_warn", 75)
        self.mem_crit = self.config.get("mem_crit", 90)
        self.restart_warn = self.config.get("restart_warn", 3)
        self.restart_crit = self.config.get("restart_crit", 5)
        self.slack_webhook = self.config.get("slack_webhook", "")

    def evaluate(self, snapshot, pod_metrics=None):
        """Evaluate the cluster state and generate alerts."""
        self.alerts = []

        self._check_pod_status(snapshot)
        self._check_deployments(snapshot)
        self._check_restart_counts(snapshot)
        self._check_events(snapshot)

        if pod_metrics:
            self._check_resource_usage(pod_metrics, snapshot)

        # Store in history
        for alert in self.alerts:
            alert["timestamp"] = datetime.now(timezone.utc).isoformat()
            self.alert_history.append(alert)

        # Keep last 200 alerts in history
        if len(self.alert_history) > 200:
            self.alert_history = self.alert_history[-200:]

        return self.alerts

    def _check_pod_status(self, snapshot):
        """Check for failed or pending pods."""
        for pod in snapshot.get("pods", []):
            if pod["status"] == "Failed":
                self.alerts.append({
                    "severity": SEVERITY_CRITICAL,
                    "type": "pod_failed",
                    "pod": pod["name"],
                    "namespace": pod["namespace"],
                    "message": f"Pod {pod['name']} has FAILED",
                })
            elif pod["status"] == "Pending":
                self.alerts.append({
                    "severity": SEVERITY_WARNING,
                    "type": "pod_pending",
                    "pod": pod["name"],
                    "namespace": pod["namespace"],
                    "message": f"Pod {pod['name']} is stuck in Pending state",
                })

            # Check container states
            for container in pod.get("containers", []):
                if "waiting" in container.get("state", ""):
                    reason = container["state"]
                    if "CrashLoopBackOff" in reason:
                        self.alerts.append({
                            "severity": SEVERITY_CRITICAL,
                            "type": "crash_loop",
                            "pod": pod["name"],
                            "namespace": pod["namespace"],
                            "container": container["name"],
                            "message": f"Container {container['name']} in {pod['name']} is in CrashLoopBackOff",
                        })
                    elif "ImagePullBackOff" in reason or "ErrImagePull" in reason:
                        self.alerts.append({
                            "severity": SEVERITY_CRITICAL,
                            "type": "image_pull_error",
                            "pod": pod["name"],
                            "namespace": pod["namespace"],
                            "container": container["name"],
                            "message": f"Container {container['name']} in {pod['name']} cannot pull image",
                        })

    def _check_deployments(self, snapshot):
        """Check for unhealthy deployments."""
        for dep in snapshot.get("deployments", []):
            desired = dep["replicas_desired"]
            ready = dep["replicas_ready"]

            if desired > 0 and ready == 0:
                self.alerts.append({
                    "severity": SEVERITY_CRITICAL,
                    "type": "deployment_down",
                    "deployment": dep["name"],
                    "namespace": dep["namespace"],
                    "message": f"Deployment {dep['name']} has 0/{desired} replicas ready - SERVICE DOWN",
                })
            elif desired > 0 and ready < desired:
                self.alerts.append({
                    "severity": SEVERITY_WARNING,
                    "type": "deployment_degraded",
                    "deployment": dep["name"],
                    "namespace": dep["namespace"],
                    "message": f"Deployment {dep['name']} has {ready}/{desired} replicas ready - DEGRADED",
                })

    def _check_restart_counts(self, snapshot):
        """Check for pods with high restart counts."""
        for pod in snapshot.get("pods", []):
            restarts = pod["restart_count"]
            if restarts >= self.restart_crit:
                self.alerts.append({
                    "severity": SEVERITY_CRITICAL,
                    "type": "high_restarts",
                    "pod": pod["name"],
                    "namespace": pod["namespace"],
                    "message": f"Pod {pod['name']} has restarted {restarts} times (critical threshold: {self.restart_crit})",
                })
            elif restarts >= self.restart_warn:
                self.alerts.append({
                    "severity": SEVERITY_WARNING,
                    "type": "high_restarts",
                    "pod": pod["name"],
                    "namespace": pod["namespace"],
                    "message": f"Pod {pod['name']} has restarted {restarts} times (warning threshold: {self.restart_warn})",
                })

    def _check_events(self, snapshot):
        """Check for warning events."""
        for event in snapshot.get("events", []):
            if event["type"] == "Warning":
                self.alerts.append({
                    "severity": SEVERITY_WARNING,
                    "type": "k8s_warning_event",
                    "object": event["object"],
                    "namespace": event.get("namespace", ""),
                    "message": f"K8s Warning: {event['reason']} - {event['message'][:100]}",
                })

    def _check_resource_usage(self, pod_metrics, snapshot):
        """Check CPU/Memory usage against thresholds."""
        for pm in pod_metrics:
            if "error" in pm:
                continue

            # Find the pod spec to get limits
            pod_spec = None
            for pod in snapshot.get("pods", []):
                if pod["name"] == pm["name"]:
                    pod_spec = pod
                    break

            if pod_spec and pod_spec.get("cpu_limit") and pod_spec["cpu_limit"] != "0":
                cpu_limit_m = self._parse_cpu_to_milli(pod_spec["cpu_limit"])
                if cpu_limit_m > 0:
                    cpu_percent = (pm["cpu_usage_millicores"] / cpu_limit_m) * 100
                    if cpu_percent >= self.cpu_crit:
                        self.alerts.append({
                            "severity": SEVERITY_CRITICAL,
                            "type": "high_cpu",
                            "pod": pm["name"],
                            "namespace": pm["namespace"],
                            "message": f"Pod {pm['name']} CPU at {cpu_percent:.0f}% of limit",
                        })
                    elif cpu_percent >= self.cpu_warn:
                        self.alerts.append({
                            "severity": SEVERITY_WARNING,
                            "type": "high_cpu",
                            "pod": pm["name"],
                            "namespace": pm["namespace"],
                            "message": f"Pod {pm['name']} CPU at {cpu_percent:.0f}% of limit",
                        })

    def _parse_cpu_to_milli(self, cpu_str):
        """Parse CPU string to millicores."""
        if cpu_str.endswith("m"):
            return int(cpu_str[:-1])
        return int(float(cpu_str) * 1000)

    def get_health_scores(self, snapshot, pod_metrics=None):
        """Calculate health score (0-100) per deployment/service."""
        scores = {}

        for dep in snapshot.get("deployments", []):
            name = dep["name"]
            score = 100

            # Check replica health (-30 for no replicas, -15 for partial)
            desired = dep["replicas_desired"]
            ready = dep["replicas_ready"]
            if desired > 0:
                if ready == 0:
                    score -= 50
                elif ready < desired:
                    score -= 25

            # Check pod restarts (-5 per restart, max -30)
            dep_pods = [p for p in snapshot.get("pods", []) if dep["name"] in p["name"]]
            total_restarts = sum(p["restart_count"] for p in dep_pods)
            score -= min(total_restarts * 5, 30)

            # Check for failed/pending pods (-10 each)
            failed = sum(1 for p in dep_pods if p["status"] in ("Failed", "Pending"))
            score -= failed * 10

            # Check for crash loops (-20 each)
            for pod in dep_pods:
                for c in pod.get("containers", []):
                    if "CrashLoopBackOff" in c.get("state", ""):
                        score -= 20

            scores[name] = {
                "name": name,
                "namespace": dep["namespace"],
                "score": max(0, min(100, score)),
                "status": _score_to_status(max(0, min(100, score))),
                "replicas": f"{ready}/{desired}",
                "restarts": total_restarts,
            }

        return scores

    def print_alerts(self):
        """Print alerts to terminal with colors."""
        if not self.alerts:
            print(f"  {Fore.GREEN}No alerts - cluster is healthy{Style.RESET_ALL}")
            return

        for alert in self.alerts:
            severity = alert["severity"]
            if severity == SEVERITY_CRITICAL:
                icon = f"{Fore.RED}[CRITICAL]{Style.RESET_ALL}"
            elif severity == SEVERITY_WARNING:
                icon = f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL}"
            else:
                icon = f"{Fore.CYAN}[INFO]{Style.RESET_ALL}"

            print(f"  {icon} {alert['message']}")

    def send_slack(self, alert):
        """Send alert to Slack webhook."""
        if not self.slack_webhook:
            return

        severity_emoji = {
            SEVERITY_CRITICAL: ":red_circle:",
            SEVERITY_WARNING: ":warning:",
            SEVERITY_INFO: ":information_source:",
        }

        emoji = severity_emoji.get(alert["severity"], ":bell:")
        try:
            requests.post(self.slack_webhook, json={
                "text": f"{emoji} *KubeWatch Alert*\n*{alert['severity'].upper()}*: {alert['message']}"
            }, timeout=5)
        except Exception:
            pass


def _score_to_status(score):
    """Convert health score to status label."""
    if score >= 90:
        return "healthy"
    elif score >= 70:
        return "degraded"
    elif score >= 50:
        return "unhealthy"
    else:
        return "critical"
