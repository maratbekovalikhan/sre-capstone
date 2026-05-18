import asyncio
import json
import logging
import random
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import redis_client
from app.config import settings
from app.database import engine, get_db
from app.metrics import (
    CACHE_HITS,
    CACHE_MISSES,
    DB_QUERY_DURATION,
    TASKS_CREATED,
    TASKS_DELETED,
    TASKS_UPDATED,
    WORK_DURATION,
    WORK_REQUESTS,
)
from app.models import Task
from app.schemas import TaskCreate, TaskResponse, TaskUpdate

CACHE_TTL = 60  # seconds

logger = logging.getLogger("app")


# ── JSON logging ─────────────────────────────────────────────────


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log)


def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ── Lifespan (startup + graceful shutdown) ───────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("starting up", extra={"service": settings.app_name})
    yield
    # Graceful shutdown: close DB pool and Redis
    logger.info("shutting down — closing connections")
    await engine.dispose()
    await redis_client.aclose()
    logger.info("shutdown complete")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

# Prometheus metrics — auto-instruments all HTTP metrics on /metrics
Instrumentator().instrument(app).expose(app)


# ── Root & probes ────────────────────────────────────────────────


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Liveness probe — app process is running."""
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness probe — dependencies (DB, Redis) are reachable."""
    checks = {"database": "ok", "redis": "ok"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "unavailable"
    try:
        await redis_client.ping()
    except Exception:
        checks["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}


# ── /work — chaos endpoint for load testing ──────────────────────


@app.get("/work")
async def work(
    delay: int = Query(0, ge=0, le=10000, description="Simulated delay in ms"),
    fail_rate: float = Query(0.0, ge=0.0, le=1.0, description="Probability of 500 error"),
):
    """Simulate slow/failing requests. Use for load testing and alerting demos."""
    start = time.perf_counter()

    if delay > 0:
        await asyncio.sleep(delay / 1000.0)

    if fail_rate > 0 and random.random() < fail_rate:
        WORK_REQUESTS.labels(result="error").inc()
        WORK_DURATION.observe(time.perf_counter() - start)
        logger.warning("simulated failure", extra={"delay": delay, "fail_rate": fail_rate})
        raise HTTPException(status_code=500, detail="Simulated failure")

    elapsed = time.perf_counter() - start
    WORK_REQUESTS.labels(result="success").inc()
    WORK_DURATION.observe(elapsed)
    return {"status": "ok", "delay_ms": delay, "elapsed_ms": round(elapsed * 1000, 2)}


# ── CRUD ─────────────────────────────────────────────────────────


@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    start = time.perf_counter()
    task = Task(**body.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    DB_QUERY_DURATION.labels(operation="insert").observe(time.perf_counter() - start)
    TASKS_CREATED.inc()
    logger.info("task created", extra={"task_id": task.id})
    return task


@app.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    start = time.perf_counter()
    result = await db.execute(select(Task).order_by(Task.created_at.desc()))
    tasks = result.scalars().all()
    DB_QUERY_DURATION.labels(operation="select").observe(time.perf_counter() - start)
    return tasks


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = f"task:{task_id}"

    # Try cache first
    cached = await redis_client.get(cache_key)
    if cached:
        CACHE_HITS.inc()
        return json.loads(cached)

    CACHE_MISSES.inc()
    start = time.perf_counter()
    task = await db.get(Task, task_id)
    DB_QUERY_DURATION.labels(operation="select").observe(time.perf_counter() - start)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Store in cache
    response = TaskResponse.model_validate(task)
    await redis_client.setex(cache_key, CACHE_TTL, response.model_dump_json())
    return task


@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int, body: TaskUpdate, db: AsyncSession = Depends(get_db)
):
    start = time.perf_counter()
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    DB_QUERY_DURATION.labels(operation="update").observe(time.perf_counter() - start)
    TASKS_UPDATED.inc()

    # Invalidate cache
    await redis_client.delete(f"task:{task_id}")
    return task


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    start = time.perf_counter()
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
    DB_QUERY_DURATION.labels(operation="delete").observe(time.perf_counter() - start)
    TASKS_DELETED.inc()

    # Invalidate cache
    await redis_client.delete(f"task:{task_id}")


# ── Global middleware ────────────────────────────────────────────


@app.middleware("http")
async def simulate_failures(request, call_next):
    """Inject artificial delay and errors via env vars (global, for all endpoints)."""
    if settings.simulate_delay_ms > 0:
        await asyncio.sleep(settings.simulate_delay_ms / 1000.0)

    if settings.simulate_error_rate > 0 and random.random() < settings.simulate_error_rate:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=500,
            content={"detail": "Simulated error for testing"},
        )

    return await call_next(request)
