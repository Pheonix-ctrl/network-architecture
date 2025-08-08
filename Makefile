# Makefile
.PHONY: help build up down logs shell test lint format clean

# Default target
help:
	@echo "MJ Network Development Commands:"
	@echo "  build     - Build Docker images"
	@echo "  up        - Start all services"
	@echo "  down      - Stop all services"
	@echo "  logs      - Show application logs"
	@echo "  shell     - Access application shell"
	@echo "  test      - Run tests"
	@echo "  lint      - Run linting"
	@echo "  format    - Format code"
	@echo "  clean     - Clean up Docker resources"

# Docker commands
build:
	docker-compose build

up:
	docker-compose up -d
	@echo "🚀 MJ Network is starting..."
	@echo "📊 API Documentation: http://localhost:8000/docs"
	@echo "🔗 WebSocket: ws://localhost:8000/ws/{user_id}"

down:
	docker-compose down

logs:
	docker-compose logs -f mj-network

shell:
	docker-compose exec mj-network /bin/bash

# Development commands
test:
	docker-compose exec mj-network pytest

lint:
	docker-compose exec mj-network black --check src/
	docker-compose exec mj-network isort --check-only src/
	docker-compose exec mj-network mypy src/

format:
	docker-compose exec mj-network black src/
	docker-compose exec mj-network isort src/

# Cleanup
clean:
	docker-compose down -v
	docker system prune -f

# Database operations
migrate:
	docker-compose exec mj-network alembic upgrade head

create-migration:
	docker-compose exec mj-network alembic revision --autogenerate -m "$(name)"

# Production deployment
deploy-prod:
	docker-compose --profile production up -d

# Monitoring
monitor:
	docker-compose --profile monitoring up -d
	@echo "📊 Prometheus: http://localhost:9090"
	@echo "📈 Grafana: http://localhost:3000 (admin/admin)"