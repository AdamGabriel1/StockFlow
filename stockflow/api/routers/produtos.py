from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from stockflow.models import Produto, Usuario
from stockflow.repositories import ProdutoRepo
from stockflow.services import EstoqueService
from stockflow.api.deps import get_current_admin
from stockflow.api.schemas import (
    ProdutoCreate, ProdutoUpdate, ProdutoOut, ReporEstoque,
    Pagina,
)

router = APIRouter(prefix="/produtos", tags=["produtos"])


# ---------------- LISTAGEM PAGINADA ----------------
@router.get("", response_model=Pagina[ProdutoOut])
def listar(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, min_length=1),
    categoria: Optional[str] = None,
    preco_min: Optional[float] = Query(None, ge=0),
    preco_max: Optional[float] = Query(None, ge=0),
    apenas_alerta: bool = False,
    ordenar: str = Query("nome",
                         pattern="^-?(nome|preco|estoque|codigo)$"),
):
    items, total = ProdutoRepo.listar_paginado(
        limit=limit, offset=offset, q=q, categoria=categoria,
        preco_min=preco_min, preco_max=preco_max,
        apenas_alerta=apenas_alerta, ordenar=ordenar,
    )
    return Pagina[ProdutoOut](
        items=[ProdutoOut.from_model(p) for p in items],
        total=total, limit=limit, offset=offset,
        pagina=offset // limit + 1,
        total_paginas=(total + limit - 1) // limit if total else 0,
    )


# ---------------- ALERTAS (flat, semântico) ----------------
@router.get("/alertas", response_model=List[ProdutoOut])
def alertas():
    return [ProdutoOut.from_model(p) for p in EstoqueService.listar_alertas()]


# ---------------- BUSCA (legado — use ?q=) ----------------
@router.get("/busca", response_model=List[ProdutoOut], deprecated=True)
def buscar(nome: str):
    """DEPRECATED: prefira GET /produtos?q=<termo>."""
    return [ProdutoOut.from_model(p) for p in ProdutoRepo.buscar_por_nome(nome)]


# ---------------- ITEM ----------------
@router.get("/{codigo}", response_model=ProdutoOut)
def obter(codigo: str):
    p = ProdutoRepo.buscar(codigo)
    if not p:
        raise HTTPException(404, f"Produto '{codigo}' não encontrado")
    return ProdutoOut.from_model(p)


# ---------------- ADMIN ----------------
@router.post("", response_model=ProdutoOut, status_code=201)
def criar(dados: ProdutoCreate, _: Usuario = Depends(get_current_admin)):
    p = Produto(
        codigo=dados.codigo, nome=dados.nome, preco=dados.preco,
        estoque=dados.estoque, estoque_minimo=dados.estoque_minimo,
        categoria=dados.categoria,
    )
    ProdutoRepo.inserir(p)
    return ProdutoOut.from_model(p)


@router.put("/{codigo}", response_model=ProdutoOut)
def atualizar(codigo: str, dados: ProdutoUpdate,
              _: Usuario = Depends(get_current_admin)):
    p = ProdutoRepo.buscar(codigo)
    if not p:
        raise HTTPException(404, f"Produto '{codigo}' não encontrado")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(p, campo, valor)
    ProdutoRepo.atualizar(p)
    return ProdutoOut.from_model(p)


@router.delete("/{codigo}", status_code=204)
def excluir(codigo: str, _: Usuario = Depends(get_current_admin)):
    p = ProdutoRepo.buscar(codigo)
    if not p:
        raise HTTPException(404, f"Produto '{codigo}' não encontrado")
    ProdutoRepo.excluir(codigo)


@router.post("/{codigo}/repor", response_model=ProdutoOut)
def repor(codigo: str, dados: ReporEstoque,
          _: Usuario = Depends(get_current_admin)):
    p = EstoqueService.repor(codigo, dados.quantidade)
    return ProdutoOut.from_model(p)