# SRE Capstone: Task Manager API

**Team:** Alihan & Nurassyl | **Cloud:** AWS EKS | **Stack:** FastAPI + PostgreSQL + Redis + Prometheus

Production-ready microservice with full observability, CI/CD, and infrastructure as code.

## Quick Start (Docker)

```bash
git clone <repo-url> && cd sre-capstone
docker compose up --build -d
```

Services:

| Service | URL |
|---------|-----|
| API (Swagger UI) | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |
| Alertmanager | http://localhost:9093 |

DB migrations run automatically on startup.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (checks DB + Redis) |
| POST | `/tasks` | Create task |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{id}` | Get task (Redis-cached) |
| PUT | `/tasks/{id}` | Update task |
| DELETE | `/tasks/{id}` | Delete task |
| GET | `/work?delay=500&fail_rate=0.1` | Chaos endpoint for load testing |
| GET | `/metrics` | Prometheus metrics |

## Local Development (without Docker)

```bash
# Prerequisites: Python 3.11+, PostgreSQL, Redis running locally
pip install -r requirements.txt

# Create database and run migrations
createdb taskmanager
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

## Running Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

## Environment Variables

See `.env.example` for all options:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/taskmanager` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `SIMULATE_DELAY_MS` | `0` | Global artificial delay (ms) |
| `SIMULATE_ERROR_RATE` | `0.0` | Global error injection (0.0–1.0) |
| `DEBUG` | `false` | Enable debug logging |

## Load Testing

```bash
# Chaos endpoint — simulate 50% errors with 200ms delay
curl 'http://localhost:8000/work?delay=200&fail_rate=0.5'

# Locust (full load test)
pip install locust
locust -f locust/locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m --headless

# Simple Python load test (no extra deps)
python scripts/load_test.py --url http://localhost:8000 --requests 300 --concurrency 30
```

## AWS Deployment

### 1. Infrastructure (Terraform)

```bash
# One-time: create S3 state backend
cd terraform/bootstrap && terraform init && terraform apply

# Provision VPC + EKS + ECR
cd terraform && terraform init && terraform apply -var-file=terraform.tfvars
```

### 2. Application (Kubernetes)

```bash
aws eks update-kubeconfig --region us-east-1 --name sre-ecommerce-cluster
./scripts/install_metrics_server.sh

IMAGE_URI=<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/sre-ecommerce-app:latest
sed "s|IMAGE_PLACEHOLDER|$IMAGE_URI|g" k8s/deployment.yaml | kubectl apply -f -
```

### 3. Monitoring (Helm)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f monitoring/kube-prometheus-stack-values.yml

kubectl apply -f monitoring/servicemonitor.yaml
kubectl apply -f monitoring/prometheus-rule.yaml
```

## SLOs

| SLI | SLO | Alert Threshold |
|-----|-----|-----------------|
| Availability | >= 99.9% | Error rate > 0.1% |
| Latency p99 | < 500ms | p99 > 500ms for 3min |
| Task success rate | >= 99.5% | < 99% for 10min |

## CI/CD

GitHub Actions pipeline (`.github/workflows/ci-cd.yml`):
1. Run tests with pytest
2. Build Docker image and push to ECR
3. Deploy to EKS (main branch only)

Required secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

## Project Structure

```
├── app/                    # FastAPI application
│   ├── main.py             # Endpoints + middleware
│   ├── config.py           # Settings via env vars
│   ├── database.py         # Async SQLAlchemy
│   ├── cache.py            # Async Redis
│   ├── models.py           # Task model
│   ├── schemas.py          # Pydantic schemas
│   └── metrics.py          # Custom Prometheus metrics
├── alembic/                # Database migrations
├── tests/                  # pytest tests
├── terraform/              # AWS infrastructure (VPC, EKS, ECR)
├── k8s/                    # Kubernetes manifests + HPA
├── monitoring/             # Prometheus, Grafana, Alertmanager configs
├── locust/                 # Load testing
├── docker-compose.yml      # Full local stack
├── Dockerfile              # Multi-stage build
└── requirements.txt
```
