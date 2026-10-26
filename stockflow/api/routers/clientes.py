from typing import List
from fastapi import APIRouter, HTTPException

from stockflow.models import Cliente
from stockflow.repositories import ClienteRepo
from stockflow.api.schemas import ClienteIn, ClienteOut

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("", response_model=List[ClienteOut])
def listar():
    return [ClienteOut.from_model(c) for c in ClienteRepo.listar()]


@router.get("/cpf/{cpf}", response_model=ClienteOut)
def obter_por_cpf(cpf: str):
    c = ClienteRepo.buscar_por_cpf(cpf)
    if not c:
        raise HTTPException(404, "Cliente não encontrado")
    return ClienteOut.from_model(c)


@router.get("/{cliente_id}", response_model=ClienteOut)
def obter(cliente_id: int):
    c = ClienteRepo.buscar(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente não encontrado")
    return ClienteOut.from_model(c)


@router.post("", response_model=ClienteOut, status_code=201)
def criar(dados: ClienteIn):
    if ClienteRepo.buscar_por_cpf(dados.cpf):
        raise HTTPException(409, "CPF já cadastrado")
    cid = ClienteRepo.inserir(Cliente(dados.nome, dados.cpf, dados.email, dados.endereco))
    return ClienteOut.from_model(ClienteRepo.buscar(cid))


@router.put("/{cliente_id}", response_model=ClienteOut)
def atualizar(cliente_id: int, dados: ClienteIn):
    c = ClienteRepo.buscar(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente não encontrado")
    c.nome, c.cpf, c.email, c.endereco = dados.nome, dados.cpf, dados.email, dados.endereco
    ClienteRepo.atualizar(c)
    return ClienteOut.from_model(c)
