"""
KubeWatch - Metrics Collector
Collects CPU, memory, network metrics from Kubernetes metrics API and Prometheus.
"""

import requests
from kubernetes import client, config
from datetime import datetime, timezone


def get_node_metrics(apis):
    """Get CPU/Memory usage per node from metrics API."""
    try:
        api = client.CustomObjectsApi()
        metrics = api.list_cluster_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            plural="nodes",
        )

        nodes = []
        for node in metrics.get("items", []):
            cpu_nano = _parse_cpu(node["usage"]["cpu"])
            mem_bytes = _parse_memory(node["usage"]["memory"])

            nodes.append({
                "name": node["metadata"]["name"],
                "cpu_usage_millicores": cpu_nano // 1_000_000,
                "memory_usage_mb": mem_bytes // (1024 * 1024),
                "timestamp": node["timestamp"],
            })

        return nodes
    except Exception as e:
        return [{"error": str(e)}]


def get_pod_metrics(apis, namespace=None):
    """Get CPU/Memory usage per pod from metrics API."""
    try:
        api = client.CustomObjectsApi()

        if namespace:
            metrics = api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="pods",
                namespace=namespace,
            )
        else:
            metrics = api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="pods",
            )

        pods = []
        for pod in metrics.get("items", []):
            total_cpu = 0
            total_mem = 0

            for container in pod.get("containers", []):
                total_cpu += _parse_cpu(container["usage"]["cpu"])
                total_mem += _parse_memory(container["usage"]["memory"])

            pods.append({
                "name": pod["metadata"]["name"],
                "namespace": pod["metadata"]["namespace"],
                "cpu_usage_millicores": total_cpu // 1_000_000,
                "memory_usage_mb": total_mem // (1024 * 1024),
                "memory_usage_bytes": total_mem,
                "containers": [{
                    "name": c["name"],
                    "cpu_millicores": _parse_cpu(c["usage"]["cpu"]) // 1_000_000,
                    "memory_mb": _parse_memory(c["usage"]["memory"]) // (1024 * 1024),
                } for c in pod.get("containers", [])],
                "timestamp": pod["timestamp"],
            })

        return pods
    except Exception as e:
        return [{"error": str(e)}]


def query_prometheus(prometheus_url, query):
    """Run a PromQL query against Prometheus."""
    try:
        response = requests.get(
            f"{prometheus_url}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        data = response.json()
        if data["status"] == "success":
            return data["data"]["result"]
        return []
    except Exception:
        return []


def get_prometheus_metrics(prometheus_url):
    """Get key metrics from Prometheus for the cluster."""
    metrics = {}

    # Container CPU usage by pod
    cpu_results = query_prometheus(
        prometheus_url,
        'sum(rate(container_cpu_usage_seconds_total{image!=""}[5m])) by (pod, namespace)'
    )
    metrics["cpu_by_pod"] = {
        r["metric"].get("pod", ""): round(float(r["value"][1]) * 1000, 2)
        for r in cpu_results
        if r["metric"].get("pod")
    }

    # Container memory usage by pod
    mem_results = query_prometheus(
        prometheus_url,
        'sum(container_memory_working_set_bytes{image!=""}) by (pod, namespace)'
    )
    metrics["memory_by_pod"] = {
        r["metric"].get("pod", ""): round(float(r["value"][1]) / (1024 * 1024), 2)
        for r in mem_results
        if r["metric"].get("pod")
    }

    # Network receive bytes by pod
    net_rx = query_prometheus(
        prometheus_url,
        'sum(rate(container_network_receive_bytes_total[5m])) by (pod)'
    )
    metrics["network_rx_by_pod"] = {
        r["metric"].get("pod", ""): round(float(r["value"][1]) / 1024, 2)
        for r in net_rx
        if r["metric"].get("pod")
    }

    # Network transmit bytes by pod
    net_tx = query_prometheus(
        prometheus_url,
        'sum(rate(container_network_transmit_bytes_total[5m])) by (pod)'
    )
    metrics["network_tx_by_pod"] = {
        r["metric"].get("pod", ""): round(float(r["value"][1]) / 1024, 2)
        for r in net_tx
        if r["metric"].get("pod")
    }

    # Total cluster CPU usage
    cluster_cpu = query_prometheus(
        prometheus_url,
        'sum(rate(container_cpu_usage_seconds_total{image!=""}[5m]))'
    )
    metrics["cluster_cpu_cores"] = round(float(cluster_cpu[0]["value"][1]), 3) if cluster_cpu else 0

    # Total cluster memory usage
    cluster_mem = query_prometheus(
        prometheus_url,
        'sum(container_memory_working_set_bytes{image!=""})'
    )
    metrics["cluster_memory_mb"] = round(float(cluster_mem[0]["value"][1]) / (1024 * 1024), 2) if cluster_mem else 0

    return metrics


# ---- Helper Functions ----

def _parse_cpu(cpu_string):
    """Parse CPU string to nanocores. E.g., '250m' -> 250000000, '1' -> 1000000000"""
    if cpu_string.endswith("n"):
        return int(cpu_string[:-1])
    elif cpu_string.endswith("u"):
        return int(cpu_string[:-1]) * 1000
    elif cpu_string.endswith("m"):
        return int(cpu_string[:-1]) * 1_000_000
    else:
        return int(float(cpu_string) * 1_000_000_000)


def _parse_memory(mem_string):
    """Parse memory string to bytes. E.g., '128Mi' -> 134217728"""
    units = {
        "Ki": 1024,
        "Mi": 1024 ** 2,
        "Gi": 1024 ** 3,
        "Ti": 1024 ** 4,
        "K": 1000,
        "M": 1000 ** 2,
        "G": 1000 ** 3,
    }
    for suffix, multiplier in units.items():
        if mem_string.endswith(suffix):
            return int(mem_string[:-len(suffix)]) * multiplier
    return int(mem_string)
