#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ─── Step 1: Check prerequisites ──────────────────────────────────────────
info "Checking prerequisites..."
MISSING=()
for cmd in brew minikube kubectl helm terraform docker; do
  if ! command -v "$cmd" &> /dev/null; then
    MISSING+=("$cmd")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  warn "Missing tools: ${MISSING[*]}"
  warn "Install them before proceeding."
  if [[ " ${MISSING[*]} " == *" minikube "* ]] || [[ " ${MISSING[*]} " == *" kubectl "* ]] || [[ " ${MISSING[*]} " == *" terraform "* ]]; then
    error "Critical tools missing. Cannot continue."
  fi
fi

info "All critical tools found."

# ─── Step 2: Start Minikube ───────────────────────────────────────────────
info "Starting Minikube cluster..."
minikube start --cpus=4 --memory=6144 --driver=docker

# ─── Step 3: Enable addons ────────────────────────────────────────────────
info "Enabling ingress addon..."
minikube addons enable ingress

info "Enabling metrics-server addon..."
minikube addons enable metrics-server

# ─── Step 4: Build Docker image ───────────────────────────────────────────
info "Building Docker image inside Minikube..."
eval $(minikube docker-env)
docker build -t task-api:local "$REPO_ROOT"

# ─── Step 5: Terraform init & apply ───────────────────────────────────────
info "Initializing Terraform..."
cd "$REPO_ROOT/terraform/environments/local"

if [[ ! -f terraform.tfvars ]]; then
  info "Creating terraform.tfvars from example..."
  cp terraform.tfvars.example terraform.tfvars
fi

terraform init
info "Applying Terraform..."
terraform apply -auto-approve

# ─── Step 6: Wait for pods ────────────────────────────────────────────────
info "Waiting for deployments to be ready..."
kubectl rollout status deployment/postgres -n task-api --timeout=120s
kubectl rollout status deployment/redis -n task-api --timeout=120s
kubectl rollout status deployment/task-api -n task-api --timeout=300s

# ─── Done ─────────────────────────────────────────────────────────────────
echo ""
info "Setup complete!"
echo ""
echo "Access services:"
echo "  App:        kubectl port-forward -n task-api svc/task-api-service 8080:80"
echo "  Grafana:    kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80"
echo "  Prometheus: kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090"
echo ""
echo "Or add to /etc/hosts:"
echo "  echo \"\$(minikube ip) task-api.local grafana.local\" | sudo tee -a /etc/hosts"
