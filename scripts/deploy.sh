#!/usr/bin/env bash
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ─── Step 1: Check cluster ─────────────────────────────────────────────────
info "Checking cluster connectivity..."
kubectl cluster-info > /dev/null 2>&1 || error "Cannot connect to Kubernetes cluster. Is minikube running?"

# ─── Step 2: Determine image ───────────────────────────────────────────────
if [[ -n "${1:-}" ]]; then
  IMAGE="$1"
else
  IMAGE=$(grep -oP 'image:\s*\K\S+' "$REPO_ROOT/k8s/05-app.yaml" | head -1)
fi

[[ -z "$IMAGE" ]] && error "Could not determine image. Pass it as argument: ./deploy.sh <image>"
info "Deploying image: $IMAGE"

# ─── Step 3: Pull image into Minikube ──────────────────────────────────────
if [[ "$IMAGE" == ghcr.io/* ]]; then
  info "Switching to Minikube Docker daemon..."
  eval $(minikube docker-env)

  info "Pulling image from registry..."
  docker pull "$IMAGE" || error "Failed to pull $IMAGE"
fi

# ─── Step 4: Deploy via Terraform ──────────────────────────────────────────
info "Running Terraform apply..."
cd "$REPO_ROOT/terraform/environments/local"
terraform apply -auto-approve -var="app_image=$IMAGE"

# ─── Step 5: Wait for rollout ──────────────────────────────────────────────
info "Waiting for rollout to complete..."
kubectl rollout status deployment/task-api -n task-api --timeout=300s

# ─── Step 6: Show status ──────────────────────────────────────────────────
info "Deployment complete! Pod status:"
kubectl get pods -n task-api -l app=task-api

echo ""
info "Access the app:"
echo "  kubectl port-forward -n task-api svc/task-api-service 8080:80"
echo "  curl http://localhost:8080/health"
