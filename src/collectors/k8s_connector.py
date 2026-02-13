"""
KubeWatch - Kubernetes API Connector
Auto-discovers and collects info about all pods, services, nodes, deployments.
"""

from kubernetes import client, config
from datetime import datetime, timezone


def connect():
    """Connect to Kubernetes cluster. Tries in-cluster first, then kubeconfig."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    return {
        "core": client.CoreV1Api(),
        "apps": client.AppsV1Api(),
        "metrics": None,
    }


def get_cluster_info(apis):
    """Get cluster overview info."""
    v1 = apis["core"]
    version_info = client.VersionApi().get_code()

    return {
        "version": f"{version_info.major}.{version_info.minor}",
        "platform": version_info.platform,
    }


def get_nodes(apis):
    """Get all nodes with their status and resource info."""
    v1 = apis["core"]
    nodes = []

    for node in v1.list_node().items:
        conditions = {c.type: c.status for c in node.status.conditions}
        capacity = node.status.capacity
        allocatable = node.status.allocatable

        nodes.append({
            "name": node.metadata.name,
            "status": "Ready" if conditions.get("Ready") == "True" else "NotReady",
            "roles": _get_node_roles(node),
            "cpu_capacity": capacity.get("cpu", "0"),
            "memory_capacity": capacity.get("memory", "0"),
            "cpu_allocatable": allocatable.get("cpu", "0"),
            "memory_allocatable": allocatable.get("memory", "0"),
            "os": node.status.node_info.os_image,
            "kernel": node.status.node_info.kernel_version,
            "container_runtime": node.status.node_info.container_runtime_version,
            "kubelet_version": node.status.node_info.kubelet_version,
            "created": node.metadata.creation_timestamp.isoformat() if node.metadata.creation_timestamp else "",
        })

    return nodes


def get_pods(apis, namespace=None):
    """Get all pods with their status, containers, and resource info."""
    v1 = apis["core"]

    if namespace:
        pod_list = v1.list_namespaced_pod(namespace)
    else:
        pod_list = v1.list_pod_for_all_namespaces()

    pods = []
    for pod in pod_list.items:
        containers = []
        restart_count = 0

        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                restart_count += cs.restart_count
                state = "unknown"
                if cs.state.running:
                    state = "running"
                elif cs.state.waiting:
                    state = f"waiting ({cs.state.waiting.reason})"
                elif cs.state.terminated:
                    state = f"terminated ({cs.state.terminated.reason})"

                containers.append({
                    "name": cs.name,
                    "image": cs.image,
                    "ready": cs.ready,
                    "restart_count": cs.restart_count,
                    "state": state,
                })

        # Get resource requests/limits from spec
        cpu_request = "0"
        mem_request = "0"
        cpu_limit = "0"
        mem_limit = "0"

        if pod.spec.containers:
            for c in pod.spec.containers:
                if c.resources:
                    if c.resources.requests:
                        cpu_request = c.resources.requests.get("cpu", "0")
                        mem_request = c.resources.requests.get("memory", "0")
                    if c.resources.limits:
                        cpu_limit = c.resources.limits.get("cpu", "0")
                        mem_limit = c.resources.limits.get("memory", "0")

        pods.append({
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
            "ip": pod.status.pod_ip or "",
            "restart_count": restart_count,
            "containers": containers,
            "labels": pod.metadata.labels or {},
            "cpu_request": cpu_request,
            "mem_request": mem_request,
            "cpu_limit": cpu_limit,
            "mem_limit": mem_limit,
            "created": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else "",
            "age": _calculate_age(pod.metadata.creation_timestamp),
        })

    return pods


def get_services(apis, namespace=None):
    """Get all services."""
    v1 = apis["core"]

    if namespace:
        svc_list = v1.list_namespaced_service(namespace)
    else:
        svc_list = v1.list_service_for_all_namespaces()

    services = []
    for svc in svc_list.items:
        ports = []
        if svc.spec.ports:
            for p in svc.spec.ports:
                ports.append({
                    "port": p.port,
                    "target_port": str(p.target_port),
                    "protocol": p.protocol,
                })

        services.append({
            "name": svc.metadata.name,
            "namespace": svc.metadata.namespace,
            "type": svc.spec.type,
            "cluster_ip": svc.spec.cluster_ip,
            "ports": ports,
            "selector": svc.spec.selector or {},
            "created": svc.metadata.creation_timestamp.isoformat() if svc.metadata.creation_timestamp else "",
        })

    return services


def get_deployments(apis, namespace=None):
    """Get all deployments with replica status."""
    apps_v1 = apis["apps"]

    if namespace:
        dep_list = apps_v1.list_namespaced_deployment(namespace)
    else:
        dep_list = apps_v1.list_deployment_for_all_namespaces()

    deployments = []
    for dep in dep_list.items:
        deployments.append({
            "name": dep.metadata.name,
            "namespace": dep.metadata.namespace,
            "replicas_desired": dep.spec.replicas or 0,
            "replicas_ready": dep.status.ready_replicas or 0,
            "replicas_available": dep.status.available_replicas or 0,
            "replicas_updated": dep.status.updated_replicas or 0,
            "labels": dep.metadata.labels or {},
            "created": dep.metadata.creation_timestamp.isoformat() if dep.metadata.creation_timestamp else "",
        })

    return deployments


def get_events(apis, namespace=None, limit=50):
    """Get recent cluster events (warnings, errors)."""
    v1 = apis["core"]

    if namespace:
        event_list = v1.list_namespaced_event(namespace)
    else:
        event_list = v1.list_event_for_all_namespaces()

    events = []
    for event in sorted(event_list.items, key=lambda e: e.last_timestamp or e.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:limit]:
        events.append({
            "type": event.type,
            "reason": event.reason,
            "message": event.message,
            "object": f"{event.involved_object.kind}/{event.involved_object.name}",
            "namespace": event.metadata.namespace,
            "count": event.count or 1,
            "timestamp": (event.last_timestamp or event.metadata.creation_timestamp or "").isoformat() if hasattr(event.last_timestamp or event.metadata.creation_timestamp, 'isoformat') else "",
        })

    return events


def get_pod_logs(apis, pod_name, namespace="default", lines=100):
    """Get logs from a specific pod."""
    v1 = apis["core"]
    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=lines,
        )
        return logs.split("\n") if logs else []
    except Exception as e:
        return [f"Error fetching logs: {str(e)}"]


def get_full_snapshot(apis, namespace=None):
    """Get a complete cluster snapshot - everything at once."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cluster": get_cluster_info(apis),
        "nodes": get_nodes(apis),
        "pods": get_pods(apis, namespace),
        "services": get_services(apis, namespace),
        "deployments": get_deployments(apis, namespace),
        "events": get_events(apis, namespace),
        "summary": None,
    }


def enrich_snapshot(snapshot):
    """Add summary stats to a snapshot."""
    pods = snapshot["pods"]
    nodes = snapshot["nodes"]
    deployments = snapshot["deployments"]

    total_pods = len(pods)
    running_pods = sum(1 for p in pods if p["status"] == "Running")
    failed_pods = sum(1 for p in pods if p["status"] == "Failed")
    pending_pods = sum(1 for p in pods if p["status"] == "Pending")
    total_restarts = sum(p["restart_count"] for p in pods)
    warning_events = sum(1 for e in snapshot["events"] if e["type"] == "Warning")

    snapshot["summary"] = {
        "total_pods": total_pods,
        "running_pods": running_pods,
        "failed_pods": failed_pods,
        "pending_pods": pending_pods,
        "total_nodes": len(nodes),
        "ready_nodes": sum(1 for n in nodes if n["status"] == "Ready"),
        "total_deployments": len(deployments),
        "healthy_deployments": sum(1 for d in deployments if d["replicas_ready"] == d["replicas_desired"]),
        "total_services": len(snapshot["services"]),
        "total_restarts": total_restarts,
        "warning_events": warning_events,
    }

    return snapshot


# ---- Helper Functions ----

def _get_node_roles(node):
    """Extract node roles from labels."""
    roles = []
    for label, value in (node.metadata.labels or {}).items():
        if label.startswith("node-role.kubernetes.io/"):
            roles.append(label.split("/")[1])
    return ", ".join(roles) if roles else "worker"


def _calculate_age(timestamp):
    """Calculate human-readable age from timestamp."""
    if not timestamp:
        return "unknown"

    now = datetime.now(timezone.utc)
    diff = now - timestamp

    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
