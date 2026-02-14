/**
 * KubeWatch Dashboard - Frontend Logic
 * Fetches cluster data from Flask API, renders UI, auto-refreshes.
 */

const API_BASE = "";
const REFRESH_INTERVAL = 15000; // 15 seconds

// Chart instances
let cpuChart = null;
let memChart = null;

// Store latest data for detail views
let latestData = null;

// Chart data history (keep last 20 data points)
const MAX_HISTORY = 20;
let cpuHistory = {};
let memHistory = {};
let timeLabels = [];

// ---- INIT ----
document.addEventListener("DOMContentLoaded", () => {
    if (typeof Chart !== "undefined") {
        initCharts();
    } else {
        console.warn("Chart.js not loaded - charts disabled");
    }
    fetchData();
    setInterval(fetchData, REFRESH_INTERVAL);
});

// ---- FETCH DATA ----
async function fetchData() {
    try {
        const res = await fetch(`${API_BASE}/api/snapshot`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.status === "ok") {
            latestData = data;
            setConnected(true);
            renderStats(data);
            renderHealthScores(data.health_scores);
            renderAlerts(data.alerts);
            renderPods(data.snapshot.pods);
            renderEvents(data.snapshot.events);
            if (cpuChart && memChart) {
                updateCharts(data.metrics.pods);
            }
        } else {
            setConnected(false, data.message);
        }
    } catch (err) {
        console.error("Fetch error:", err);
        setConnected(false, err.message);
    }
}

// ---- CONNECTION STATUS ----
function setConnected(ok, msg) {
    const dot = document.getElementById("connectionDot");
    const status = document.getElementById("connectionStatus");

    if (ok) {
        dot.className = "status-dot connected";
        status.textContent = "Connected";
    } else {
        dot.className = "status-dot error";
        status.textContent = msg ? `Error: ${msg}` : "Disconnected";
    }
}

// ---- STATS BAR ----
function renderStats(data) {
    const snap = data.snapshot;
    const pods = snap.pods || [];

    document.getElementById("totalPods").textContent = pods.length;
    document.getElementById("runningPods").textContent =
        pods.filter(p => p.status === "Running").length;
    document.getElementById("totalNodes").textContent =
        (snap.nodes || []).length;
    document.getElementById("totalDeploys").textContent =
        (snap.deployments || []).length;
    document.getElementById("totalRestarts").textContent =
        pods.reduce((sum, p) => sum + (p.restart_count || 0), 0);
    document.getElementById("totalAlerts").textContent =
        (data.alerts || []).length;
}

// ---- HEALTH SCORES ----
function renderHealthScores(scores) {
    const container = document.getElementById("healthScores");

    if (!scores || Object.keys(scores).length === 0) {
        container.innerHTML = '<p class="no-data">No deployments found</p>';
        return;
    }

    let html = '<div class="health-grid">';
    for (const [name, info] of Object.entries(scores)) {
        const statusClass = `health-${info.status}`;
        html += `
            <div class="health-item ${statusClass}">
                <div class="health-item-header">
                    <span class="health-name">${esc(name)}</span>
                    <span class="health-score">${info.score}</span>
                </div>
                <div class="health-bar">
                    <div class="health-bar-fill" style="width: ${info.score}%"></div>
                </div>
                <div class="health-meta">
                    <span>Replicas: ${info.replicas}</span>
                    <span>Restarts: ${info.restarts}</span>
                </div>
            </div>
        `;
    }
    html += "</div>";
    container.innerHTML = html;
}

// ---- ALERTS ----
function renderAlerts(alerts) {
    const container = document.getElementById("alertList");
    const badge = document.getElementById("alertBadge");

    badge.textContent = alerts.length;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<p class="no-data">No active alerts - cluster is healthy</p>';
        return;
    }

    // Sort: critical first, then warning, then info
    const order = { critical: 0, warning: 1, info: 2 };
    alerts.sort((a, b) => (order[a.severity] || 3) - (order[b.severity] || 3));

    let html = "";
    for (const alert of alerts) {
        const icon = alert.severity === "critical" ? "&#9888;" :
                     alert.severity === "warning" ? "&#9679;" : "&#8505;";
        html += `
            <div class="alert-item ${alert.severity}">
                <span class="alert-icon">${icon}</span>
                <span class="alert-msg">${esc(alert.message)}</span>
                ${alert.timestamp ? `<span class="alert-time">${formatTime(alert.timestamp)}</span>` : ""}
            </div>
        `;
    }
    container.innerHTML = html;
}

// ---- PODS ----
function renderPods(pods) {
    const container = document.getElementById("podList");

    if (!pods || pods.length === 0) {
        container.innerHTML = '<p class="no-data">No pods found</p>';
        return;
    }

    let html = "";
    for (const pod of pods) {
        const statusLower = (pod.status || "unknown").toLowerCase();
        const restartHtml = pod.restart_count > 0
            ? `<span class="pod-restarts">Restarts: ${pod.restart_count}</span>`
            : "";

        // Calculate ready count from containers
        const containers = pod.containers || [];
        const readyCount = containers.filter(c => c.ready).length;
        const totalCount = containers.length;
        const readyStr = `${readyCount}/${totalCount}`;

        html += `
            <div class="pod-item">
                <span class="pod-status-dot ${statusLower}"></span>
                <span class="pod-name">${esc(pod.name)}</span>
                <div class="pod-info">
                    <span>${pod.status}</span>
                    ${restartHtml}
                    <span>${readyStr}</span>
                </div>
            </div>
        `;
    }
    container.innerHTML = html;
}

// ---- EVENTS ----
function renderEvents(events) {
    const container = document.getElementById("eventList");

    if (!events || events.length === 0) {
        container.innerHTML = '<p class="no-data">No recent events</p>';
        return;
    }

    // Show most recent first, limit to 30
    const recent = events.slice(-30).reverse();

    let html = "";
    for (const evt of recent) {
        const timeStr = evt.age || (evt.timestamp ? formatTime(evt.timestamp) : "");
        html += `
            <div class="event-item ${evt.type}">
                <span class="event-type ${evt.type}">${evt.type}</span>
                <span class="event-msg">
                    <span class="event-object">${esc(evt.object)}</span>
                    ${esc(evt.reason)} - ${esc(evt.message || "").substring(0, 120)}
                </span>
                <span class="event-time">${esc(timeStr)}</span>
            </div>
        `;
    }
    container.innerHTML = html;
}

// ---- CHARTS ----
function initCharts() {
    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 600 },
        plugins: {
            legend: {
                position: "bottom",
                labels: {
                    color: "#8b949e",
                    boxWidth: 12,
                    padding: 12,
                    font: { size: 11 },
                },
            },
        },
        scales: {
            x: {
                grid: { color: "rgba(48,54,61,0.5)" },
                ticks: { color: "#6e7681", font: { size: 10 }, maxTicksLimit: 8 },
            },
            y: {
                grid: { color: "rgba(48,54,61,0.5)" },
                ticks: { color: "#6e7681", font: { size: 10 } },
                beginAtZero: true,
            },
        },
    };

    cpuChart = new Chart(document.getElementById("cpuChart"), {
        type: "line",
        data: { labels: [], datasets: [] },
        options: { ...chartDefaults },
    });

    memChart = new Chart(document.getElementById("memChart"), {
        type: "line",
        data: { labels: [], datasets: [] },
        options: { ...chartDefaults },
    });
}

function updateCharts(podMetrics) {
    if (!podMetrics || podMetrics.length === 0 || podMetrics[0].error) return;

    const now = new Date().toLocaleTimeString("en-US", {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });

    timeLabels.push(now);
    if (timeLabels.length > MAX_HISTORY) {
        timeLabels = timeLabels.slice(-MAX_HISTORY);
    }

    // Colors for chart lines
    const colors = [
        "#58a6ff", "#3fb950", "#bc8cff", "#39d2c0",
        "#d29922", "#f85149", "#f778ba", "#79c0ff",
        "#a5d6ff", "#ffa657",
    ];

    // Update history
    for (const pm of podMetrics) {
        if (pm.error) continue;
        const name = pm.name;

        if (!cpuHistory[name]) cpuHistory[name] = [];
        if (!memHistory[name]) memHistory[name] = [];

        cpuHistory[name].push(pm.cpu_usage_millicores || 0);
        memHistory[name].push(pm.memory_usage_mb || 0);

        if (cpuHistory[name].length > MAX_HISTORY) {
            cpuHistory[name] = cpuHistory[name].slice(-MAX_HISTORY);
        }
        if (memHistory[name].length > MAX_HISTORY) {
            memHistory[name] = memHistory[name].slice(-MAX_HISTORY);
        }
    }

    // Build datasets
    const podNames = Object.keys(cpuHistory);
    const cpuDatasets = podNames.map((name, i) => ({
        label: name,
        data: cpuHistory[name],
        borderColor: colors[i % colors.length],
        backgroundColor: colors[i % colors.length] + "20",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
        fill: true,
    }));

    const memDatasets = podNames.map((name, i) => ({
        label: name,
        data: memHistory[name],
        borderColor: colors[i % colors.length],
        backgroundColor: colors[i % colors.length] + "20",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
        fill: true,
    }));

    cpuChart.data.labels = [...timeLabels];
    cpuChart.data.datasets = cpuDatasets;
    cpuChart.update("none");

    memChart.data.labels = [...timeLabels];
    memChart.data.datasets = memDatasets;
    memChart.update("none");
}

// ---- HELPERS ----
function esc(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(isoString) {
    try {
        const d = new Date(isoString);
        return d.toLocaleTimeString("en-US", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return "";
    }
}

// ---- DETAIL MODAL ----
function showDetail(type) {
    if (!latestData) return;

    const overlay = document.getElementById("modalOverlay");
    const title = document.getElementById("modalTitle");
    const body = document.getElementById("modalBody");

    const snap = latestData.snapshot;

    if (type === "pods" || type === "running") {
        const pods = snap.pods || [];
        const filtered = type === "running" ? pods.filter(p => p.status === "Running") : pods;
        title.textContent = type === "running" ? `Running Pods (${filtered.length})` : `All Pods (${filtered.length})`;

        let html = `<table class="detail-table">
            <thead><tr>
                <th>Name</th><th>Status</th><th>Ready</th><th>Restarts</th><th>IP</th><th>Node</th><th>Age</th>
            </tr></thead><tbody>`;
        for (const p of filtered) {
            const containers = p.containers || [];
            const readyCount = containers.filter(c => c.ready).length;
            const statusClass = `status-${(p.status || "").toLowerCase()}`;
            html += `<tr>
                <td>${esc(p.name)}</td>
                <td class="${statusClass}">${p.status}</td>
                <td>${readyCount}/${containers.length}</td>
                <td>${p.restart_count || 0}</td>
                <td>${esc(p.ip || "-")}</td>
                <td>${esc(p.node || "-")}</td>
                <td>${esc(p.age || "-")}</td>
            </tr>`;
        }
        html += "</tbody></table>";
        body.innerHTML = html;

    } else if (type === "nodes") {
        const nodes = snap.nodes || [];
        title.textContent = `Nodes (${nodes.length})`;

        let html = `<table class="detail-table">
            <thead><tr>
                <th>Name</th><th>Status</th><th>Roles</th><th>Version</th><th>OS</th><th>Runtime</th><th>CPU</th><th>Memory</th>
            </tr></thead><tbody>`;
        for (const n of nodes) {
            const statusClass = n.status === "Ready" ? "node-ready" : "node-not-ready";
            const memGb = n.memory_allocatable ? (parseInt(n.memory_allocatable) / (1024 * 1024)).toFixed(1) + " GB" : "-";
            html += `<tr>
                <td>${esc(n.name)}</td>
                <td class="${statusClass}">${esc(n.status || "-")}</td>
                <td>${esc(n.roles || "-")}</td>
                <td>${esc(n.kubelet_version || "-")}</td>
                <td>${esc(n.os || "-")}</td>
                <td>${esc(n.container_runtime || "-")}</td>
                <td>${esc(n.cpu_capacity || "-")} cores</td>
                <td>${memGb}</td>
            </tr>`;
        }
        html += "</tbody></table>";
        body.innerHTML = html;

    } else if (type === "deployments") {
        const deps = snap.deployments || [];
        title.textContent = `Deployments (${deps.length})`;

        let html = `<table class="detail-table">
            <thead><tr>
                <th>Name</th><th>Namespace</th><th>Ready</th><th>Up-to-date</th><th>Available</th><th>Age</th>
            </tr></thead><tbody>`;
        for (const d of deps) {
            const readyColor = d.replicas_ready === d.replicas_desired ? "status-running" : "status-pending";
            html += `<tr>
                <td>${esc(d.name)}</td>
                <td>${esc(d.namespace)}</td>
                <td class="${readyColor}">${d.replicas_ready}/${d.replicas_desired}</td>
                <td>${d.replicas_updated || "-"}</td>
                <td>${d.replicas_available || 0}</td>
                <td>${esc(d.created || "-")}</td>
            </tr>`;
        }
        html += "</tbody></table>";
        body.innerHTML = html;

    } else if (type === "services") {
        const svcs = snap.services || [];
        title.textContent = `Services (${svcs.length})`;

        let html = `<table class="detail-table">
            <thead><tr>
                <th>Name</th><th>Type</th><th>Cluster IP</th><th>Ports</th><th>Namespace</th>
            </tr></thead><tbody>`;
        for (const s of svcs) {
            const ports = (s.ports || []).map(p => `${p.port}/${p.protocol}`).join(", ");
            html += `<tr>
                <td>${esc(s.name)}</td>
                <td>${esc(s.type || "-")}</td>
                <td>${esc(s.cluster_ip || "-")}</td>
                <td>${esc(ports || "-")}</td>
                <td>${esc(s.namespace || "-")}</td>
            </tr>`;
        }
        html += "</tbody></table>";
        body.innerHTML = html;

    } else if (type === "alerts") {
        const alerts = latestData.alerts || [];
        title.textContent = `Active Alerts (${alerts.length})`;

        if (alerts.length === 0) {
            body.innerHTML = '<p class="no-data">No active alerts - cluster is healthy</p>';
        } else {
            let html = `<table class="detail-table">
                <thead><tr>
                    <th>Severity</th><th>Type</th><th>Resource</th><th>Message</th><th>Time</th>
                </tr></thead><tbody>`;
            for (const a of alerts) {
                const sevClass = a.severity === "critical" ? "status-failed" :
                                 a.severity === "warning" ? "status-pending" : "";
                const resource = a.pod || a.deployment || a.object || "-";
                html += `<tr>
                    <td class="${sevClass}">${(a.severity || "").toUpperCase()}</td>
                    <td>${esc(a.type || "-")}</td>
                    <td>${esc(resource)}</td>
                    <td>${esc(a.message)}</td>
                    <td>${a.timestamp ? formatTime(a.timestamp) : "-"}</td>
                </tr>`;
            }
            html += "</tbody></table>";
            body.innerHTML = html;
        }
    }

    overlay.classList.add("active");
}

function closeModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById("modalOverlay").classList.remove("active");
}

// Close modal with Escape key
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        document.getElementById("modalOverlay").classList.remove("active");
    }
});
