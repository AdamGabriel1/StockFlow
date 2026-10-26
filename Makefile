.PHONY: up down logs shell test build clean

up:            ## sobe a API (build se necessário)
	docker compose up --build -d
	@echo "API em http://localhost:$${STOCKFLOW_PORT:-8000}/docs"

down:          ## derruba containers (mantém volume do banco)
	docker compose down

logs:          ## tail dos logs
	docker compose logs -f api

shell:         ## shell no container
	docker compose exec api bash

test:          ## roda a suíte local (sem docker)
	python -m unittest discover -s tests -v

build:         ## só reconstrói a imagem
	docker compose build

clean:         ## ⚠️ destrói containers + volume (apaga o banco!)
	docker compose down -v
