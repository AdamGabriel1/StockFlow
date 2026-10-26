from typing import List, Optional
from .models import Produto, Carrinho, Pedido
from .repositories import ProdutoRepo, PedidoRepo
from .cupom_repo import CupomRepo
from decimal import Decimal, ROUND_HALF_UP


class EstoqueService:
    @staticmethod
    def listar_alertas() -> List[Produto]:
        return [p for p in ProdutoRepo.listar() if p.precisa_repor()]

    @staticmethod
    def repor(codigo: str, quantidade: int) -> Produto:
        if quantidade <= 0:
            raise ValueError("Quantidade deve ser positiva.")
        p = ProdutoRepo.buscar(codigo)
        if not p:
            raise ValueError(f"Produto '{codigo}' não encontrado.")
        p.estoque += quantidade
        ProdutoRepo.atualizar(p)
        return p


class DescontoService:
    """Descontos aplicados sobre o subtotal — pega sempre o mais vantajoso."""

    DESCONTO_POR_VOLUME = {
        50: Decimal("12.0"), 20: Decimal("8.0"), 10: Decimal("5.0"),
    }
    DESCONTO_POR_VALOR = {
        2000: Decimal("15.0"), 1000: Decimal("10.0"), 500: Decimal("5.0"),
    }

    @classmethod
    def calcular(cls, carrinho: Carrinho) -> Decimal:
        candidatos = []
        qtd = carrinho.total_itens()
        subtotal = carrinho.subtotal()
        for q, pct in cls.DESCONTO_POR_VOLUME.items():
            if qtd >= q:
                candidatos.append(pct)
                break
        for v, pct in cls.DESCONTO_POR_VALOR.items():
            if subtotal >= Decimal(v):
                candidatos.append(pct)
                break
        return max(candidatos) if candidatos else Decimal("0")


class FreteService:
    TAXA_BASE = Decimal("15.00")
    POR_ITEM = Decimal("2.50")
    FRETE_GRATIS_ACIMA = Decimal("500.00")

    @classmethod
    def calcular(cls, carrinho: Carrinho) -> Decimal:
        if carrinho.subtotal() >= cls.FRETE_GRATIS_ACIMA:
            return Decimal("0.00")
        bruto = cls.TAXA_BASE + cls.POR_ITEM * carrinho.total_itens()
        return bruto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CupomService:
    CAP_DESCONTO_TOTAL = Decimal("40.0")

    @staticmethod
    def validar_cupom(cupom, subtotal: Decimal) -> tuple[bool, str]:
        if cupom is None:
            return False, "Cupom não encontrado"
        if not cupom.ativo:
            return False, "Cupom inativo"
        if not cupom.vigente():
            if cupom.uso_maximo is not None and cupom.uso_atual >= cupom.uso_maximo:
                return False, "Cupom esgotado"
            return False, "Cupom fora do período de validade"
        if subtotal < cupom.valor_minimo:
            return False, f"Valor mínimo do pedido não atingido: R$ {cupom.valor_minimo:.2f}"
        return True, "OK"

    @staticmethod
    def calcular(cupom, subtotal: Decimal,
                 desconto_auto_pct: Decimal) -> Decimal:
        if subtotal <= 0:
            return Decimal("0.00")
        desc_auto = subtotal * desconto_auto_pct / Decimal(100)
        bruto = cupom.desconto_sobre(subtotal)
        cap = subtotal * CupomService.CAP_DESCONTO_TOTAL / Decimal(100)
        disponivel = max(Decimal("0.00"), cap - desc_auto)
        return min(bruto, disponivel).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


class VendaService:
    @staticmethod
    def _preparar_pedido(carrinho: Carrinho,
                         usuario_id: Optional[int] = None) -> Pedido:
        if not carrinho.cliente or carrinho.cliente.id is None:
            raise ValueError("Selecione um cliente antes de finalizar.")
        if not carrinho.itens:
            raise ValueError("Carrinho vazio.")

        pedido = Pedido(
            cliente=carrinho.cliente,
            itens=list(carrinho.itens),
            usuario_id=usuario_id,
        )
        pedido.desconto = DescontoService.calcular(carrinho)

        if carrinho.cupom_codigo:
            cupom = CupomRepo.buscar(carrinho.cupom_codigo)
            ok, motivo = CupomService.validar_cupom(cupom, carrinho.subtotal())
            if not ok:
                raise ValueError(f"Cupom inválido: {motivo}")
            pedido.cupom_codigo = cupom.codigo
            pedido.cupom_desconto = CupomService.calcular(
                cupom, carrinho.subtotal(), pedido.desconto,
            )

        pedido.frete = FreteService.calcular(carrinho)
        pedido.calcular_total()
        return pedido

    @staticmethod
    def finalizar(carrinho: Carrinho,
                  usuario_id: Optional[int] = None) -> Pedido:
        pedido = VendaService._preparar_pedido(carrinho, usuario_id=usuario_id)
        pedido.id = PedidoRepo.inserir(pedido)
        carrinho.limpar()
        return pedido

    @staticmethod
    def finalizar_do_carrinho(carrinho: Carrinho,
                              usuario_id: Optional[int] = None) -> Pedido:
        if carrinho.id is None:
            raise ValueError("Carrinho sem id persistido — use VendaService.finalizar.")
        pedido = VendaService._preparar_pedido(carrinho, usuario_id=usuario_id)
        pedido.id = PedidoRepo.inserir_e_limpar_carrinho(pedido, carrinho.id)
        return pedido

    @staticmethod
    def cancelar(pedido_id: int) -> None:
        PedidoRepo.cancelar(pedido_id)