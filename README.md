# KubeWatch

**Kubernetes Monitoring & Observability Platform**

A real-time Kubernetes cluster monitoring tool with a web dashboard, CLI interface, alerting engine, and Grafana integration. Built with Python, Flask, and Chart.js.

Created by **SULIMAN KHAN**

---

## Features

- **Real-time Dashboard** - Dark-themed web UI with auto-refresh (15s)
- **Health Scoring** - Per-service health scores (0-100) based on replicas, restarts, pod status
- **Smart Alerting** - Detects pod failures, crash loops, high CPU/memory, deployment issues
- **CLI Monitoring** - Terminal-based cluster snapshot with colored output
- **Log Aggregation** - Collect and search logs across all pods and containers
- **Metrics Collection** - CPU, memory, network metrics from Kubernetes Metrics API
- **Prometheus Integration** - PromQL queries for detailed cluster metrics
- **Grafana Dashboards** - Pre-configured dashboards for visual monitoring
- **Slack Alerts** - Optional webhook notifications for critical alerts

## Architecture

```
kubewatch/
├── src/
│   ├── main.py                  # Entry point (CLI + Dashboard)
│   ├── config.py                # Configuration
│   ├── collectors/
│   │   ├── k8s_connector.py     # Kubernetes API connector
│   │   ├── metrics_collector.py # CPU/Memory/Network metrics
│   │   └── log_collector.py     # Pod log aggregation
│   ├── alerting/
│   │   └── alert_engine.py      # Alert detection & health scoring
│   └── dashboard/
│       ├── app.py               # Flask web server + API
│       ├── templates/
│       │   └── index.html       # Dashboard HTML
│       └── static/
│           ├── css/dashboard.css
│           └── js/dashboard.js
├── k8s/manifests/
│   ├── sample-apps.yaml         # Sample deployments for testing
│   ├── prometheus.yaml          # Prometheus deployment + RBAC
│   └── grafana.yaml             # Grafana deployment + dashboards
├── run.sh                       # One-command start script
└── requirements.txt
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker
- Minikube or any Kubernetes cluster
- kubectl configured

### Setup

```bash
# Clone the repo
git clone https://github.com/Suliman8/KubeWatch.git
cd KubeWatch

# One-command start (sets up everything)
./run.sh dashboard
```

The run script will:
1. Check/start Minikube
2. Enable metrics-server
3. Deploy sample apps
4. Install Python dependencies
5. Start the dashboard at http://localhost:8080

### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start Minikube
minikube start
minikube addons enable metrics-server

# Deploy sample apps + monitoring
kubectl apply -f k8s/manifests/sample-apps.yaml
kubectl apply -f k8s/manifests/prometheus.yaml
kubectl apply -f k8s/manifests/grafana.yaml

# Start dashboard
python -m src.main dashboard
```

## Usage

### Web Dashboard
```bash
python -m src.main dashboard
# Open http://localhost:8080
```

### CLI Monitor
```bash
# Cluster snapshot
python -m src.main monitor

# With JSON output
python -m src.main monitor --json

# Specific namespace
python -m src.main monitor -n kube-system
```

### Log Viewer
```bash
# View pod logs
python -m src.main logs --pod web-server-xxx

# Scan all pods for errors
python -m src.main logs --errors
```

### Grafana
```bash
# Access Grafana (after deploying)
minikube service grafana --url
# Login: admin / kubewatch
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Dashboard UI |
| `GET /api/snapshot` | Full cluster state + alerts + health scores |
| `GET /api/pods` | Pod listing |
| `GET /api/logs/<pod>` | Pod logs |
| `GET /api/errors` | Error logs from all pods |
| `GET /api/alerts` | Current alerts + history |

## Alert Types

| Alert | Severity | Trigger |
|---|---|---|
| Pod Failed | Critical | Pod status = Failed |
| Pod Pending | Warning | Pod stuck in Pending |
| CrashLoopBackOff | Critical | Container in crash loop |
| Image Pull Error | Critical | Cannot pull container image |
| Deployment Down | Critical | 0 ready replicas |
| Deployment Degraded | Warning | Fewer replicas than desired |
| High Restarts | Warning/Critical | Restart count > threshold |
| High CPU | Warning/Critical | CPU > 70%/90% of limit |
| K8s Warning Events | Warning | Warning-type cluster events |

## Tech Stack

- **Backend**: Python 3, Flask, kubernetes-client
- **Frontend**: HTML5, CSS3, JavaScript, Chart.js
- **Monitoring**: Prometheus, Grafana
- **Cluster**: Kubernetes (Minikube for dev)

## License

MIT

---

*KubeWatch v1.0.0 | Created by SULIMAN KHAN | 2026*
