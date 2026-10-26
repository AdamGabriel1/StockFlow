import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError   # ← novo

from stockflow.database import inicializar
from stockflow.seed import seed_demo
from stockflow.api.routers import (
    produtos, clientes, carrinho, pedidos, relatorios, cupons, auth,   # ⬅️ auth
)
from stockflow.carrinho_repo import CarrinhoRepo


@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar()
    seed_demo()
    removidos = CarrinhoRepo.purgar_antigos(24)
    if removidos:
        print(f"🧹 {removidos} carrinho(s) antigo(s) purgado(s).")
    yield


app = FastAPI(
    title="StockFlow API",
    description="Sistema de estoque e vendas — REST",
    version="1.1.0",
    lifespan=lifespan,
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    # Pydantic v2: ValidationError herda de ValueError — não pode engolir
    if isinstance(exc, PydanticValidationError):
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro de validação de resposta", "errors": exc.errors()},
        )
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error_handler(request: Request, exc: sqlite3.IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": f"Conflito de dados: {exc}"},
    )


@app.get("/", tags=["meta"])
def root():
    return {"app": "StockFlow API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


app.include_router(produtos.router)
app.include_router(clientes.router)
app.include_router(carrinho.router)
app.include_router(pedidos.router)
app.include_router(relatorios.router)
app.include_router(cupons.router)
app.include_router(auth.router)