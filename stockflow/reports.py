import csv
from typing import Dict, List, Optional
from .database import get_conn
from .repositories import PedidoRepo


class RelatorioService:
    @staticmethod
    def historico(data_inicio: Optional[str] = None,
                  data_fim: Optional[str] = None) -> List:
        return PedidoRepo.listar(data_inicio, data_fim)

    @staticmethod
    def faturamento(data_inicio: Optional[str] = None,
                    data_fim: Optional[str] = None) -> Dict:
        conn = get_conn()
        try:
            sql = """SELECT
                COUNT(*)                                       AS n_pedidos,
                COALESCE(SUM(total), 0)                        AS faturamento,
                COALESCE(SUM(subtotal * desconto_pct / 100),0) AS total_descontos,
                COALESCE(SUM(frete), 0)                        AS total_frete
                FROM pedidos WHERE status != 'CANCELADO'"""
            params = []
            if data_inicio and data_fim:
                sql += " AND data BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            return dict(conn.execute(sql, params).fetchone())
        finally:
            conn.close()

    @staticmethod
    def top_produtos(limite: int = 10) -> List[Dict]:
        conn = get_conn()
        try:
            sql = """
                SELECT ip.produto_codigo, ip.produto_nome,
                       SUM(ip.quantidade)                       AS qtd_total,
                       SUM(ip.quantidade * ip.preco_unitario)   AS receita
                FROM itens_pedido ip
                JOIN pedidos p ON p.id = ip.pedido_id
                WHERE p.status != 'CANCELADO'
                GROUP BY ip.produto_codigo, ip.produto_nome
                ORDER BY qtd_total DESC
                LIMIT ?
            """
            return [dict(r) for r in conn.execute(sql, (limite,)).fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _csv_rows(data_inicio=None, data_fim=None):
        pedidos = PedidoRepo.listar(data_inicio, data_fim)
        rows = [[
            "pedido_id", "data", "cliente", "status",
            "subtotal", "desconto_pct", "frete", "total", "itens",
        ]]
        for p in pedidos:
            itens = "; ".join(
                f"{i.produto.nome} x{i.quantidade} @R${i.preco_unitario:.2f}"
                for i in p.itens
            )
            rows.append([
                p.id, p.data,
                p.cliente.nome if p.cliente else "-",
                p.status,
                f"{p.subtotal:.2f}", f"{p.desconto:.2f}",
                f"{p.frete:.2f}", f"{p.total:.2f}", itens,
            ])
        return rows

    @staticmethod
    def gerar_csv(data_inicio=None, data_fim=None) -> str:
        import io
        buf = io.StringIO()
        csv.writer(buf, delimiter=";").writerows(
            RelatorioService._csv_rows(data_inicio, data_fim)
        )
        return buf.getvalue()

    @staticmethod
    def exportar_csv(caminho, data_inicio=None, data_fim=None) -> int:
        rows = RelatorioService._csv_rows(data_inicio, data_fim)
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            csv.writer(f, delimiter=";").writerows(rows)
        return len(rows) - 1
