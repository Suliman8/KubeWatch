#!/bin/bash
# KubeWatch - One Command Run Script
# Created by SULIMAN KHAN

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║     KubeWatch - Quick Start           ║"
echo "║     By SULIMAN KHAN                   ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check if Minikube is running
echo -e "${YELLOW}[1/4] Checking Minikube...${NC}"
if ! minikube status | grep -q "Running" 2>/dev/null; then
    echo -e "${YELLOW}  Starting Minikube...${NC}"
    minikube start
else
    echo -e "${GREEN}  Minikube is running${NC}"
fi

# Check if metrics-server is enabled
echo -e "${YELLOW}[2/4] Checking metrics-server...${NC}"
if ! minikube addons list | grep "metrics-server" | grep -q "enabled"; then
    echo -e "${YELLOW}  Enabling metrics-server...${NC}"
    minikube addons enable metrics-server
else
    echo -e "${GREEN}  metrics-server is enabled${NC}"
fi

# Deploy sample apps if not present
echo -e "${YELLOW}[3/4] Checking sample apps...${NC}"
if ! kubectl get deployment web-server -n default &>/dev/null; then
    echo -e "${YELLOW}  Deploying sample apps...${NC}"
    kubectl apply -f k8s/manifests/sample-apps.yaml
else
    echo -e "${GREEN}  Sample apps are deployed${NC}"
fi

# Activate venv and start dashboard
echo -e "${YELLOW}[4/4] Starting KubeWatch Dashboard...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo -e "${YELLOW}  Creating virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt -q
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Dashboard starting at: http://localhost:8080${NC}"
echo -e "${GREEN}  Press Ctrl+C to stop${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""

python -m src.main "$@"
