/**
 * KubeWatch Dashboard - Frontend Logic
 * Fetches cluster data from Flask API, renders UI, auto-refreshes.
 */

const API_BASE = "";
const REFRESH_INTERVAL = 15000; // 15 seconds

// Chart instances
let cpuChart = null;
let memChart = null;

// Chart data history (keep last 20 data points)
const MAX_HISTORY = 20;
let cpuHistory = {};
let memHistory = {};
let timeLabels = [];

// ---- INIT ----
document.addEventListener("DOMContentLoaded", () => {
    initCharts();
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
            setConnected(true);
            renderStats(data);
            renderHealthScores(data.health_scores);
            renderAlerts(data.alerts);
            renderPods(data.snapshot.pods);
            renderEvents(data.snapshot.events);
            updateCharts(data.metrics.pods);
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

        html += `
            <div class="pod-item">
                <span class="pod-status-dot ${statusLower}"></span>
                <span class="pod-name">${esc(pod.name)}</span>
                <div class="pod-info">
                    <span>${pod.status}</span>
                    ${restartHtml}
                    <span>${pod.ready || ""}</span>
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
        html += `
            <div class="event-item ${evt.type}">
                <span class="event-type ${evt.type}">${evt.type}</span>
                <span class="event-msg">
                    <span class="event-object">${esc(evt.object)}</span>
                    ${esc(evt.reason)} - ${esc(evt.message || "").substring(0, 120)}
                </span>
                <span class="event-time">${esc(evt.age || "")}</span>
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
