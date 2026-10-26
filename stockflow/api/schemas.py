from typing import List, Optional
from pydantic import BaseModel, Field
from typing import Generic, TypeVar
from decimal import Decimal


# ------------------ PRODUTO ------------------
class ProdutoCreate(BaseModel):
    codigo: str = Field(..., min_length=1)
    nome: str = Field(..., min_length=1)
    preco: Decimal = Field(..., gt=0)            # ⬅️
    estoque: int = Field(0, ge=0)
    estoque_minimo: int = Field(0, ge=0)
    categoria: str = "Geral"


class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    preco: Optional[Decimal] = Field(None, ge=0)  # ⬅️
    estoque: Optional[int] = Field(None, ge=0)
    estoque_minimo: Optional[int] = Field(None, ge=0)
    categoria: Optional[str] = None


class ProdutoOut(BaseModel):
    codigo: str
    nome: str
    preco: float
    estoque: int
    estoque_minimo: int
    categoria: str
    precisa_repor: bool

    @classmethod
    def from_model(cls, p) -> "ProdutoOut":
        return cls(
            codigo=p.codigo, nome=p.nome, preco=p.preco,
            estoque=p.estoque, estoque_minimo=p.estoque_minimo,
            categoria=p.categoria, precisa_repor=p.precisa_repor(),
        )


class ReporEstoque(BaseModel):
    quantidade: int = Field(..., gt=0)


# ------------------ CLIENTE ------------------
class ClienteIn(BaseModel):
    nome: str = Field(..., min_length=1)
    cpf: str = Field(..., min_length=1)
    email: str = ""
    endereco: str = ""


class ClienteOut(BaseModel):
    id: int
    nome: str
    cpf: str
    email: str
    endereco: str

    @classmethod
    def from_model(cls, c) -> "ClienteOut":
        return cls(
            id=c.id, nome=c.nome, cpf=c.cpf,
            email=c.email or "", endereco=c.endereco or "",
        )


# ------------------ ITEM / PEDIDO ------------------
class ItemIn(BaseModel):
    produto_codigo: str
    quantidade: int = Field(..., gt=0)


class ItemOut(BaseModel):
    produto_codigo: str
    produto_nome: str
    quantidade: int
    preco_unitario: float
    desconto: float
    subtotal: float

    @classmethod
    def from_model(cls, it) -> "ItemOut":
        return cls(
            produto_codigo=it.produto.codigo,
            produto_nome=it.produto.nome,
            quantidade=it.quantidade,
            preco_unitario=it.preco_unitario,
            desconto=it.desconto,
            subtotal=it.subtotal(),
        )


class PedidoCreate(BaseModel):
    """Pedido direto (sem passar por carrinho)."""
    cliente_id: int
    itens: List[ItemIn] = Field(..., min_length=1)


class PedidoOut(BaseModel):
    id: int
    data: str
    status: str
    cliente: ClienteOut
    itens: List[ItemOut]
    subtotal: float
    desconto: float
    frete: float
    total: float
    cupom_codigo: Optional[str] = None
    cupom_desconto: float = 0.0
    usuario_id: Optional[int] = None              # ⬅️ NOVO

    @classmethod
    def from_model(cls, p) -> "PedidoOut":
        return cls(
            id=p.id, data=p.data, status=p.status,
            cliente=ClienteOut.from_model(p.cliente),
            itens=[ItemOut.from_model(i) for i in p.itens],
            subtotal=p.subtotal, desconto=p.desconto,
            frete=p.frete, total=p.total,
            cupom_codigo=p.cupom_codigo,
            cupom_desconto=p.cupom_desconto,
            usuario_id=p.usuario_id,              # ⬅️ NOVO
        )


# ------------------ CARRINHO ------------------
class CarrinhoOut(BaseModel):
    cart_id: str
    cliente: Optional[ClienteOut]
    itens: List[ItemOut]
    cupom_codigo: Optional[str] = None       # ⬅️ NOVO
    cupom_desconto: float = 0.0              # ⬅️ NOVO
    subtotal: float
    desconto: float
    frete: float
    total_estimado: float


class SetClienteCarrinho(BaseModel):
    cliente_id: int


class AddItemCarrinho(BaseModel):
    produto_codigo: str
    quantidade: int = Field(..., gt=0)

# ------------------ CUPOM ------------------
class CupomIn(BaseModel):
    codigo: str = Field(..., min_length=2, max_length=32)
    tipo: str = Field(..., pattern="^(PERCENTUAL|FIXO)$")
    valor: Decimal = Field(..., gt=0)             # ⬅️
    valor_minimo: Decimal = Field(Decimal("0"), ge=0)  # ⬅️
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    uso_maximo: Optional[int] = Field(None, ge=1)
    ativo: bool = True


class CupomOut(BaseModel):
    codigo: str
    tipo: str
    valor: float
    valor_minimo: float
    data_inicio: Optional[str]
    data_fim: Optional[str]
    uso_maximo: Optional[int]
    uso_atual: int
    ativo: bool
    vigente: bool

    @classmethod
    def from_model(cls, c) -> "CupomOut":
        return cls(
            codigo=c.codigo, tipo=c.tipo, valor=c.valor,
            valor_minimo=c.valor_minimo,
            data_inicio=c.data_inicio, data_fim=c.data_fim,
            uso_maximo=c.uso_maximo, uso_atual=c.uso_atual,
            ativo=c.ativo, vigente=c.vigente(),
        )


class AplicarCupom(BaseModel):
    codigo: str = Field(..., min_length=1)


# ------------------ USUÁRIO / AUTH ------------------
class UsuarioIn(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=120)
    senha: str = Field(..., min_length=6, max_length=100)


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    role: str
    ativo: bool

    @classmethod
    def from_model(cls, u) -> "UsuarioOut":
        return cls(
            id=u.id, nome=u.nome, email=u.email,
            role=u.role, ativo=u.ativo,
        )


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ------------------ PAGINAÇÃO ------------------
T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int
    pagina: int
    total_paginas: int