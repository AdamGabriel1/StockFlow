"""Geração de PDF do pedido com fpdf2 (API moderna, sem deprecations)."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .models import Pedido

_NL = dict(new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _brl(v: Decimal) -> str:
    s = f"{v:.2f}"
    inteiro, decimal = s.split(".")
    partes = []
    while len(inteiro) > 3:
        partes.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    partes.insert(0, inteiro)
    return "R$ " + ".".join(partes) + "," + decimal


def _safe(texto: Optional[str]) -> str:
    if not texto:
        return ""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


class _PedidoPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"StockFlow - pagina {self.page_no()}", align="C")


def gerar_pedido_pdf(pedido: Pedido) -> bytes:
    pdf = _PedidoPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()

    # Cabeçalho
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 10, f"StockFlow - Pedido #{pedido.id}", **_NL)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, f"Data: {_safe(pedido.data)}", **_NL)
    pdf.cell(0, 6, f"Status: {_safe(pedido.status)}", **_NL)
    pdf.ln(3)

    # Cliente
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 8, "Cliente", **_NL)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    if pedido.cliente:
        pdf.cell(0, 5, f"Nome: {_safe(pedido.cliente.nome)}", **_NL)
        pdf.cell(0, 5, f"CPF: {_safe(pedido.cliente.cpf)}", **_NL)
        if pedido.cliente.email:
            pdf.cell(0, 5, f"Email: {_safe(pedido.cliente.email)}", **_NL)
        if pedido.cliente.endereco:
            pdf.cell(0, 5, f"Endereco: {_safe(pedido.cliente.endereco)}", **_NL)
    pdf.ln(3)

    # Itens
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 8, "Itens", **_NL)

    w_prod, w_qtd, w_unit, w_sub = 90, 15, 35, 35
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(235, 235, 235)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(w_prod, 8, "Produto", border=1, fill=True)
    pdf.cell(w_qtd, 8, "Qtd", border=1, fill=True, align="C")
    pdf.cell(w_unit, 8, "Unitario", border=1, fill=True, align="R")
    pdf.cell(w_sub, 8, "Subtotal", border=1, fill=True, align="R", **_NL)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    for item in pedido.itens:
        nome = _safe(item.produto.nome)
        if len(nome) > 45:
            nome = nome[:42] + "..."
        pdf.cell(w_prod, 8, nome, border=1)
        pdf.cell(w_qtd, 8, str(item.quantidade), border=1, align="C")
        pdf.cell(w_unit, 8, _brl(item.preco_unitario), border=1, align="R")
        pdf.cell(w_sub, 8, _brl(item.subtotal()), border=1, align="R", **_NL)

    pdf.ln(4)

    # Totais
    largura_rotulo, largura_valor = 140, 40

    def linha_total(rotulo: str, valor: str, bold: bool = False):
        pdf.set_font("Helvetica", "B" if bold else "", 11 if bold else 10)
        pdf.cell(largura_rotulo, 7, rotulo, align="R")
        pdf.cell(largura_valor, 7, valor, align="R", **_NL)

    linha_total("Subtotal:", _brl(pedido.subtotal))

    if pedido.desconto:
        desc_valor = (
            pedido.subtotal * Decimal(str(pedido.desconto)) / Decimal(100)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        linha_total(f"Desconto ({pedido.desconto:.0f}%):", "- " + _brl(desc_valor))

    if pedido.cupom_codigo:
        linha_total(f"Cupom {pedido.cupom_codigo}:",
                    "- " + _brl(pedido.cupom_desconto))

    linha_total("Frete:", _brl(pedido.frete))

    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y() + 1, 195, pdf.get_y() + 1)
    pdf.ln(2)
    pdf.set_text_color(20, 20, 20)
    linha_total("TOTAL:", _brl(pedido.total), bold=True)

    return bytes(pdf.output())