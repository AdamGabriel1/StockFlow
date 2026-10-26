from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional


CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")


def _q(v: Decimal) -> Decimal:
    """Quantiza para 2 casas com ROUND_HALF_UP (arredondamento comercial)."""
    return v.quantize(CENTAVO, rounding=ROUND_HALF_UP)


@dataclass
class Produto:
    codigo: str
    nome: str
    preco: Decimal
    estoque: int = 0
    estoque_minimo: int = 0
    categoria: str = "Geral"

    def __post_init__(self):
        if not isinstance(self.preco, Decimal):
            self.preco = Decimal(str(self.preco))

    def precisa_repor(self) -> bool:
        return self.estoque <= self.estoque_minimo

    def __str__(self):
        alerta = " ⚠" if self.precisa_repor() else ""
        return (f"[{self.codigo}] {self.nome:<25} "
                f"R$ {self.preco:>8.2f}  estoque: {self.estoque:>4}{alerta}")


@dataclass
class Cliente:
    nome: str
    cpf: str
    email: str = ""
    endereco: str = ""
    id: Optional[int] = None

    def __str__(self):
        return f"#{self.id} - {self.nome} ({self.cpf})"


@dataclass
class Cupom:
    codigo: str
    tipo: str                          # "PERCENTUAL" | "FIXO"
    valor: Decimal
    valor_minimo: Decimal = ZERO
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    uso_maximo: Optional[int] = None
    uso_atual: int = 0
    ativo: bool = True

    def __post_init__(self):
        if not isinstance(self.valor, Decimal):
            self.valor = Decimal(str(self.valor))
        if not isinstance(self.valor_minimo, Decimal):
            self.valor_minimo = Decimal(str(self.valor_minimo))

    def vigente(self, agora: Optional[str] = None) -> bool:
        if not self.ativo:
            return False
        agora = agora or datetime.now().isoformat(timespec="seconds")
        if self.data_inicio and agora < self.data_inicio:
            return False
        if self.data_fim and agora > self.data_fim:
            return False
        if self.uso_maximo is not None and self.uso_atual >= self.uso_maximo:
            return False
        return True

    def desconto_sobre(self, subtotal: Decimal) -> Decimal:
        if subtotal < self.valor_minimo:
            return ZERO
        if self.tipo == "PERCENTUAL":
            return _q(subtotal * self.valor / Decimal(100))
        return _q(min(self.valor, subtotal))

    def __str__(self):
        estado = "ativo" if self.vigente() else "inativo/esgotado"
        return f"[{self.codigo}] {self.tipo} {self.valor} ({estado})"


@dataclass
class ItemPedido:
    produto: Produto
    quantidade: int
    preco_unitario: Decimal
    desconto: float = 0.0              # percentual do item (0-100)

    def __post_init__(self):
        if not isinstance(self.preco_unitario, Decimal):
            self.preco_unitario = Decimal(str(self.preco_unitario))

    def subtotal(self) -> Decimal:
        bruto = self.preco_unitario * self.quantidade
        if self.desconto:
            desc = Decimal(str(self.desconto)) / Decimal(100)
            bruto = bruto * (Decimal(1) - desc)
        return _q(bruto)

    def __str__(self):
        return f"{self.produto.nome:<25} x{self.quantidade:<3} = R$ {self.subtotal():>8.2f}"


@dataclass
class Pedido:
    cliente: Cliente
    itens: List[ItemPedido] = field(default_factory=list)
    id: Optional[int] = None
    data: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    status: str = "PENDENTE"
    frete: Decimal = ZERO
    desconto: float = 0.0              # percentual (0-100)
    subtotal: Decimal = ZERO
    total: Decimal = ZERO
    cupom_codigo: Optional[str] = None
    cupom_desconto: Decimal = ZERO
    usuario_id: Optional[int] = None

    def __post_init__(self):
        for fld in ("frete", "subtotal", "total", "cupom_desconto"):
            v = getattr(self, fld)
            if not isinstance(v, Decimal):
                setattr(self, fld, Decimal(str(v)))

    def calcular_subtotal(self) -> Decimal:
        self.subtotal = _q(sum((i.subtotal() for i in self.itens), ZERO))
        return self.subtotal

    def calcular_total(self) -> Decimal:
        self.calcular_subtotal()
        desc_pct = Decimal(str(self.desconto))
        base = self.subtotal - (self.subtotal * desc_pct / Decimal(100))
        base = max(base - self.cupom_desconto, ZERO)
        self.total = _q(base + self.frete)
        return self.total


@dataclass
class Carrinho:
    cliente: Optional[Cliente] = None
    itens: List[ItemPedido] = field(default_factory=list)
    id: Optional[str] = None
    cupom_codigo: Optional[str] = None

    def adicionar(self, produto: Produto, quantidade: int) -> None:
        if quantidade <= 0:
            raise ValueError("Quantidade deve ser positiva.")
        for item in self.itens:
            if item.produto.codigo == produto.codigo:
                item.quantidade += quantidade
                return
        self.itens.append(ItemPedido(produto, quantidade, produto.preco))

    def remover(self, codigo: str) -> bool:
        antes = len(self.itens)
        self.itens = [i for i in self.itens if i.produto.codigo != codigo]
        return len(self.itens) < antes

    def total_itens(self) -> int:
        return sum(i.quantidade for i in self.itens)

    def subtotal(self) -> Decimal:
        return _q(sum((i.subtotal() for i in self.itens), ZERO))

    def limpar(self) -> None:
        self.itens.clear()
        self.cliente = None


@dataclass
class Usuario:
    nome: str
    email: str
    senha_hash: str = ""
    role: str = "cliente"
    ativo: bool = True
    id: Optional[int] = None
    criado_em: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def __str__(self):
        return f"#{self.id} {self.nome} <{self.email}> [{self.role}]"