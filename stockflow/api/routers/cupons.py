from typing import List

from fastapi import APIRouter, Depends, HTTPException

from stockflow.models import Cupom, Usuario
from stockflow.cupom_repo import CupomRepo
from stockflow.api.deps import get_current_admin
from stockflow.api.schemas import CupomIn, CupomOut

router = APIRouter(prefix="/cupons", tags=["cupons"])


@router.get("", response_model=List[CupomOut])
def listar(incluir_inativos: bool = True,
           _: Usuario = Depends(get_current_admin)):
    return [CupomOut.from_model(c)
            for c in CupomRepo.listar(incluir_inativos)]


@router.get("/{codigo}", response_model=CupomOut)
def obter(codigo: str, _: Usuario = Depends(get_current_admin)):
    c = CupomRepo.buscar(codigo)
    if not c:
        raise HTTPException(404, f"Cupom '{codigo}' não encontrado")
    return CupomOut.from_model(c)


@router.post("", response_model=CupomOut, status_code=201)
def criar(dados: CupomIn, _: Usuario = Depends(get_current_admin)):
    if CupomRepo.buscar(dados.codigo):
        raise HTTPException(409, f"Cupom '{dados.codigo}' já existe")
    c = Cupom(
        codigo=dados.codigo.upper(), tipo=dados.tipo, valor=dados.valor,
        valor_minimo=dados.valor_minimo,
        data_inicio=dados.data_inicio, data_fim=dados.data_fim,
        uso_maximo=dados.uso_maximo, ativo=dados.ativo,
    )
    CupomRepo.inserir(c)
    return CupomOut.from_model(c)


@router.put("/{codigo}", response_model=CupomOut)
def atualizar(codigo: str, dados: CupomIn,
              _: Usuario = Depends(get_current_admin)):
    c = CupomRepo.buscar(codigo)
    if not c:
        raise HTTPException(404, f"Cupom '{codigo}' não encontrado")
    c.tipo = dados.tipo
    c.valor = dados.valor
    c.valor_minimo = dados.valor_minimo
    c.data_inicio = dados.data_inicio
    c.data_fim = dados.data_fim
    c.uso_maximo = dados.uso_maximo
    c.ativo = dados.ativo
    CupomRepo.atualizar(c)
    return CupomOut.from_model(c)


@router.delete("/{codigo}", status_code=204)
def desativar(codigo: str, _: Usuario = Depends(get_current_admin)):
    c = CupomRepo.buscar(codigo)
    if not c:
        raise HTTPException(404, f"Cupom '{codigo}' não encontrado")
    CupomRepo.desativar(codigo)