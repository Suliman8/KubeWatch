"""
KubeWatch - Log Collector
Collects and aggregates logs from all containers in the cluster.
"""

from kubernetes import client
from datetime import datetime, timezone


def get_pod_logs(apis, pod_name, namespace="default", lines=100, container=None):
    """Get logs from a specific pod."""
    v1 = apis["core"]
    try:
        kwargs = {
            "name": pod_name,
            "namespace": namespace,
            "tail_lines": lines,
        }
        if container:
            kwargs["container"] = container

        logs = v1.read_namespaced_pod_log(**kwargs)
        log_lines = logs.split("\n") if logs else []

        return {
            "pod": pod_name,
            "namespace": namespace,
            "container": container,
            "lines": log_lines,
            "count": len(log_lines),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "pod": pod_name,
            "namespace": namespace,
            "error": str(e),
            "lines": [],
            "count": 0,
        }


def get_all_pod_logs(apis, namespace=None, lines_per_pod=50):
    """Get logs from ALL pods in the namespace."""
    v1 = apis["core"]

    if namespace:
        pod_list = v1.list_namespaced_pod(namespace)
    else:
        pod_list = v1.list_pod_for_all_namespaces()

    all_logs = []

    for pod in pod_list.items:
        if pod.status.phase != "Running":
            continue

        pod_name = pod.metadata.name
        pod_ns = pod.metadata.namespace

        # Get logs from each container in the pod
        if pod.spec.containers:
            for container in pod.spec.containers:
                log_data = get_pod_logs(
                    apis,
                    pod_name,
                    namespace=pod_ns,
                    lines=lines_per_pod,
                    container=container.name,
                )
                log_data["container"] = container.name
                all_logs.append(log_data)

    return all_logs


def search_logs(apis, keyword, namespace=None, lines_per_pod=200):
    """Search all pod logs for a specific keyword."""
    all_logs = get_all_pod_logs(apis, namespace, lines_per_pod)
    matches = []

    keyword_lower = keyword.lower()

    for log_data in all_logs:
        for i, line in enumerate(log_data["lines"]):
            if keyword_lower in line.lower():
                matches.append({
                    "pod": log_data["pod"],
                    "namespace": log_data.get("namespace", "default"),
                    "container": log_data.get("container", ""),
                    "line_number": i + 1,
                    "text": line,
                })

    return matches


def get_error_logs(apis, namespace=None, lines_per_pod=200):
    """Get all log lines containing errors or warnings."""
    error_keywords = ["error", "exception", "fatal", "panic", "fail", "crash", "timeout", "refused"]
    all_logs = get_all_pod_logs(apis, namespace, lines_per_pod)
    errors = []

    for log_data in all_logs:
        for line in log_data["lines"]:
            line_lower = line.lower()
            if any(kw in line_lower for kw in error_keywords):
                errors.append({
                    "pod": log_data["pod"],
                    "namespace": log_data.get("namespace", "default"),
                    "container": log_data.get("container", ""),
                    "text": line,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    return errors
