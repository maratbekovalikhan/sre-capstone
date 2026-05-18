#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ─── Step 1: Terraform destroy ─────────────────────────────────────────────
info "Destroying Terraform resources..."
cd "$REPO_ROOT/terraform/environments/local"
terraform destroy -auto-approve || warn "Terraform destroy had issues (cluster may already be stopped)"

# ─── Step 2: Stop Minikube ─────────────────────────────────────────────────
info "Stopping Minikube..."
minikube stop

# ─── Step 3: Optionally delete cluster ─────────────────────────────────────
echo ""
read -p "Delete Minikube cluster entirely? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
  info "Deleting Minikube cluster..."
  minikube delete
  info "Cluster deleted."
else
  info "Cluster stopped but preserved. Run 'minikube start' to resume."
fi
