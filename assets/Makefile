.PHONY: mock-up mock-down db-schema

mock-up:
	docker compose up --build -d

mock-down:
	docker compose down

db-schema:
	psql $$DATABASE_URL -f db/schema.sql
