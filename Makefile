.PHONY: run test docker-up docker-down

run:
	uvicorn app.main:app --reload --port 8000

test:
	python -m pytest tests/ -v

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(msg)"
