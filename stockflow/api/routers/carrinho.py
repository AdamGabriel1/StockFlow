from fastapi import APIRouter, Depends, HTTPException

from stockflow.carrinho_repo import CarrinhoRepo
from stockflow.repositories import ProdutoRepo, ClienteRepo
from stockflow.cupom_repo import CupomRepo
from stockflow.services import DescontoService, FreteService, CupomService
from stockflow.models import Carrinho
from stockflow.api.deps import get_cart_pair
from stockflow.api.schemas import (
    CarrinhoOut, AddItemCarrinho, SetClienteCarrinho,
    AplicarCupom, ItemOut, ClienteOut,
)
from decimal import Decimal, ROUND_HALF_UP

router = APIRouter(prefix="/carrinho", tags=["carrinho"])


def _to_out(cid: str, car: Carrinho) -> CarrinhoOut:
    sub = car.subtotal()                        # Decimal
    desc_auto = DescontoService.calcular(car)   # Decimal

    cupom = None
    cupom_valor = Decimal("0.00")
    if car.cupom_codigo:
        cupom = CupomRepo.buscar(car.cupom_codigo)
        if cupom:
            ok, _ = CupomService.validar_cupom(cupom, sub)
            if ok:
                cupom_valor = CupomService.calcular(cupom, sub, desc_auto)

    frete = FreteService.calcular(car)          # Decimal
    base = sub - (sub * desc_auto / Decimal(100)) - cupom_valor
    total = (base + frete).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return CarrinhoOut(
        cart_id=cid,
        cliente=ClienteOut.from_model(car.cliente) if car.cliente else None,
        itens=[ItemOut.from_model(i) for i in car.itens],
        cupom_codigo=car.cupom_codigo,
        cupom_desconto=float(cupom_valor),
        subtotal=float(sub), desconto=float(desc_auto),
        frete=float(frete), total_estimado=float(total),
    )


@router.post("", status_code=201)
def criar():
    car = CarrinhoRepo.criar()
    return {"cart_id": car.id}


@router.get("", response_model=CarrinhoOut)
def ver(pair=Depends(get_cart_pair)):
    return _to_out(*pair)


@router.post("/cliente", response_model=CarrinhoOut)
def definir_cliente(dados: SetClienteCarrinho, pair=Depends(get_cart_pair)):
    cid, _ = pair
    c = ClienteRepo.buscar(dados.cliente_id)
    if not c:
        raise HTTPException(404, "Cliente não encontrado")
    CarrinhoRepo.definir_cliente(cid, c.id)
    return _to_out(cid, CarrinhoRepo.buscar(cid))


@router.post("/itens", response_model=CarrinhoOut)
def adicionar_item(dados: AddItemCarrinho, pair=Depends(get_cart_pair)):
    cid, _ = pair
    p = ProdutoRepo.buscar(dados.produto_codigo)
    if not p:
        raise HTTPException(404, f"Produto '{dados.produto_codigo}' não encontrado")
    if dados.quantidade > p.estoque:
        raise HTTPException(400, f"Estoque insuficiente: disponível {p.estoque}")
    CarrinhoRepo.adicionar_item(cid, p, dados.quantidade)
    return _to_out(cid, CarrinhoRepo.buscar(cid))


@router.delete("/itens/{codigo}", response_model=CarrinhoOut)
def remover_item(codigo: str, pair=Depends(get_cart_pair)):
    cid, _ = pair
    if not CarrinhoRepo.remover_item(cid, codigo):
        raise HTTPException(404, "Item não estava no carrinho")
    return _to_out(cid, CarrinhoRepo.buscar(cid))


@router.delete("/itens", response_model=CarrinhoOut)
def limpar_itens(pair=Depends(get_cart_pair)):
    cid, _ = pair
    CarrinhoRepo.limpar_itens(cid)
    return _to_out(cid, CarrinhoRepo.buscar(cid))


# ---------------- CUPOM ----------------
@router.post("/cupom", response_model=CarrinhoOut)
def aplicar_cupom(dados: AplicarCupom, pair=Depends(get_cart_pair)):
    cid, car = pair
    cupom = CupomRepo.buscar(dados.codigo)
    if not cupom:
        raise HTTPException(404, f"Cupom '{dados.codigo}' não encontrado")
    ok, motivo = CupomService.validar_cupom(cupom, car.subtotal())
    if not ok:
        raise HTTPException(400, f"Cupom inválido: {motivo}")
    CarrinhoRepo.definir_cupom(cid, cupom.codigo)
    return _to_out(cid, CarrinhoRepo.buscar(cid))


@router.delete("/cupom", response_model=CarrinhoOut)
def remover_cupom(pair=Depends(get_cart_pair)):
    cid, _ = pair
    CarrinhoRepo.definir_cupom(cid, None)
    return _to_out(cid, CarrinhoRepo.buscar(cid))


@router.delete("", status_code=204)
def descartar(pair=Depends(get_cart_pair)):
    cid, _ = pair
    CarrinhoRepo.remover(cid)