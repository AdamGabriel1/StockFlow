from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from stockflow.models import Carrinho, Usuario
from stockflow.repositories import ProdutoRepo, ClienteRepo, PedidoRepo
from stockflow.services import VendaService
from stockflow.api.deps import (
    get_cart_pair, get_current_admin, get_current_user, get_optional_user,
)
from stockflow.api.schemas import (
    PedidoCreate, PedidoOut, Pagina,
)
from fastapi.responses import Response
from stockflow.pdf import gerar_pedido_pdf

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


# ---------------- CRIAÇÃO (aceita guest) ----------------
@router.post("", response_model=PedidoOut, status_code=201)
def criar_pedido(
    dados: PedidoCreate,
    user: Optional[Usuario] = Depends(get_optional_user),
):
    cliente = ClienteRepo.buscar(dados.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado")
    car = Carrinho(cliente=cliente)
    for item in dados.itens:
        p = ProdutoRepo.buscar(item.produto_codigo)
        if not p:
            raise HTTPException(404,
                                f"Produto '{item.produto_codigo}' não encontrado")
        car.adicionar(p, item.quantidade)
    usuario_id = user.id if (user and user.role == "cliente") else None
    pedido = VendaService.finalizar(car, usuario_id=usuario_id)
    return PedidoOut.from_model(pedido)


@router.post("/checkout", response_model=PedidoOut, status_code=201)
def checkout(
    pair=Depends(get_cart_pair),
    user: Optional[Usuario] = Depends(get_optional_user),
):
    _, car = pair
    usuario_id = user.id if (user and user.role == "cliente") else None
    pedido = VendaService.finalizar_do_carrinho(car, usuario_id=usuario_id)
    return PedidoOut.from_model(pedido)


# ---------------- LISTAGEM (requer login) ----------------
@router.get("", response_model=Pagina[PedidoOut])
def listar(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None,
                                  pattern="^(PENDENTE|CANCELADO|PAGO|ENVIADO)$"),
    cliente_id: Optional[int] = Query(None, ge=1),
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    user: Usuario = Depends(get_current_user),
):
    if user.role == "admin":
        items, total = PedidoRepo.listar_paginado(
            limit=limit, offset=offset, status=status,
            cliente_id=cliente_id,
            data_inicio=data_inicio, data_fim=data_fim,
        )
    else:
        items, total = PedidoRepo.listar_paginado(
            limit=limit, offset=offset, status=status,
            usuario_id=user.id,
            data_inicio=data_inicio, data_fim=data_fim,
        )
    return Pagina[PedidoOut](
        items=[PedidoOut.from_model(p) for p in items],
        total=total, limit=limit, offset=offset,
        pagina=offset // limit + 1,
        total_paginas=(total + limit - 1) // limit if total else 0,
    )


# ---------------- DETALHE (dono ou admin) ----------------
@router.get("/{pedido_id}", response_model=PedidoOut)
def obter(pedido_id: int, user: Usuario = Depends(get_current_user)):
    p = PedidoRepo.buscar(pedido_id)
    if not p:
        raise HTTPException(404, "Pedido não encontrado")
    if user.role != "admin" and p.usuario_id != user.id:
        raise HTTPException(404, "Pedido não encontrado")   # não vaza existência
    return PedidoOut.from_model(p)


# ---------------- CANCELAMENTO (dono ou admin) ----------------
@router.post("/{pedido_id}/cancelar", response_model=PedidoOut)
def cancelar(pedido_id: int, user: Usuario = Depends(get_current_user)):
    p = PedidoRepo.buscar(pedido_id)
    if not p:
        raise HTTPException(404, "Pedido não encontrado")
    if user.role != "admin" and p.usuario_id != user.id:
        raise HTTPException(404, "Pedido não encontrado")
    VendaService.cancelar(pedido_id)
    return PedidoOut.from_model(PedidoRepo.buscar(pedido_id))

@router.get("/{pedido_id}/pdf")
def pedido_pdf(pedido_id: int, user: Usuario = Depends(get_current_user)):
    p = PedidoRepo.buscar(pedido_id)
    if not p:
        raise HTTPException(404, "Pedido não encontrado")
    if user.role != "admin" and p.usuario_id != user.id:
        raise HTTPException(404, "Pedido não encontrado")

    content = gerar_pedido_pdf(p)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="pedido_{pedido_id}.pdf"'
        },
    )