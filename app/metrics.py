from prometheus_client import Counter, Histogram

# Custom business metrics (HTTP metrics handled by prometheus-fastapi-instrumentator)
TASKS_CREATED = Counter("tasks_created_total", "Total tasks created")
TASKS_UPDATED = Counter("tasks_updated_total", "Total tasks updated")
TASKS_DELETED = Counter("tasks_deleted_total", "Total tasks deleted")
CACHE_HITS = Counter("cache_hits_total", "Redis cache hits")
CACHE_MISSES = Counter("cache_misses_total", "Redis cache misses")
DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds", "Database query duration", ["operation"]
)
WORK_REQUESTS = Counter("work_requests_total", "Total /work requests", ["result"])
WORK_DURATION = Histogram(
    "work_duration_seconds",
    "Duration of /work requests",
    buckets=[0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0],
)
