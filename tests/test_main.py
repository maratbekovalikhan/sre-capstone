import pytest


@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "Task Manager API"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_ready(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("ready", "degraded")


@pytest.mark.asyncio
async def test_metrics(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests" in resp.text


@pytest.mark.asyncio
async def test_create_and_get_task(client):
    # Create
    resp = await client.post("/tasks", json={"title": "Write tests"})
    assert resp.status_code == 201
    task = resp.json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    task_id = task["id"]

    # Get
    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_update_task(client):
    resp = await client.post("/tasks", json={"title": "To update"})
    task_id = resp.json()["id"]

    resp = await client.put(f"/tasks/{task_id}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_delete_task(client):
    resp = await client.post("/tasks", json={"title": "To delete"})
    task_id = resp.json()["id"]

    resp = await client.delete(f"/tasks/{task_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_task_not_found(client):
    resp = await client.get("/tasks/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_work_success(client):
    resp = await client.get("/work")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_work_with_delay(client):
    resp = await client.get("/work?delay=100")
    assert resp.status_code == 200
    assert resp.json()["elapsed_ms"] >= 90  # allow small tolerance


@pytest.mark.asyncio
async def test_work_fail_rate_full(client):
    resp = await client.get("/work?fail_rate=1.0")
    assert resp.status_code == 500
    assert "Simulated failure" in resp.json()["detail"]
