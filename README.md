# StockFlow

Sistema de estoque e vendas — API REST em FastAPI + SQLite.

## Rodar com Docker (recomendado)

```bash
cp .env.example .env
python -c "import secrets;print('STOCKFLOW_SECRET_KEY=' + secrets.token_hex(32))" >> .env
docker compose up --build -d
```

- API: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Admin: `admin@stockflow.local` / `admin123` (troque em produção!)

## Rodar localmente (dev)

```bash
pip install -r requirements.txt
python run_api.py
```

## Testes

```bash
python -m unittest discover -s tests -v
```

## Parar

```bash
docker compose down       # mantém volume
docker compose down -v    # ⚠️ apaga o banco
```