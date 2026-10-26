from decimal import Decimal
from typing import List, Optional

from .database import get_conn, transacao, to_sql
from .models import Cupom


class CupomRepo:

    @staticmethod
    def _row(row) -> Cupom:
        return Cupom(
            codigo=row["codigo"], tipo=row["tipo"],
            valor=Decimal(str(row["valor"])),
            valor_minimo=Decimal(str(row["valor_minimo"])),
            data_inicio=row["data_inicio"], data_fim=row["data_fim"],
            uso_maximo=row["uso_maximo"], uso_atual=row["uso_atual"],
            ativo=bool(row["ativo"]),
        )

    @staticmethod
    def buscar(codigo: str) -> Optional[Cupom]:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM cupons WHERE codigo=?", (codigo.upper(),)
            ).fetchone()
            return CupomRepo._row(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def listar(incluir_inativos: bool = True) -> List[Cupom]:
        conn = get_conn()
        try:
            sql = "SELECT * FROM cupons"
            if not incluir_inativos:
                sql += " WHERE ativo=1"
            sql += " ORDER BY codigo"
            return [CupomRepo._row(r) for r in conn.execute(sql).fetchall()]
        finally:
            conn.close()

    @staticmethod
    def inserir(c: Cupom) -> None:
        with transacao() as conn:
            conn.execute(
                """INSERT INTO cupons
                   (codigo, tipo, valor, valor_minimo, data_inicio, data_fim,
                    uso_maximo, uso_atual, ativo)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (c.codigo.upper(), c.tipo,
                 to_sql(c.valor), to_sql(c.valor_minimo),
                 c.data_inicio, c.data_fim, c.uso_maximo, c.uso_atual,
                 int(c.ativo)),
            )

    @staticmethod
    def atualizar(c: Cupom) -> None:
        with transacao() as conn:
            conn.execute(
                """UPDATE cupons SET
                     tipo=?, valor=?, valor_minimo=?,
                     data_inicio=?, data_fim=?, uso_maximo=?, ativo=?
                   WHERE codigo=?""",
                (c.tipo, to_sql(c.valor), to_sql(c.valor_minimo),
                 c.data_inicio, c.data_fim, c.uso_maximo, int(c.ativo),
                 c.codigo.upper()),
            )

    @staticmethod
    def desativar(codigo: str) -> None:
        with transacao() as conn:
            cur = conn.execute(
                "UPDATE cupons SET ativo=0 WHERE codigo=?", (codigo.upper(),)
            )
            if cur.rowcount == 0:
                raise ValueError(f"Cupom '{codigo}' não encontrado.")

    @staticmethod
    def consumir_no_conn(conn, codigo: str) -> None:
        row = conn.execute(
            "SELECT uso_maximo, uso_atual FROM cupons WHERE codigo=?",
            (codigo.upper(),),
        ).fetchone()
        if row is None:
            raise ValueError(f"Cupom '{codigo}' não encontrado.")
        if row["uso_maximo"] is not None and row["uso_atual"] >= row["uso_maximo"]:
            raise ValueError(f"Cupom '{codigo}' esgotado.")
        conn.execute(
            "UPDATE cupons SET uso_atual = uso_atual + 1 WHERE codigo=?",
            (codigo.upper(),),
        )

    @staticmethod
    def estornar_no_conn(conn, codigo: str) -> None:
        conn.execute(
            "UPDATE cupons SET uso_atual = max(0, uso_atual - 1) WHERE codigo=?",
            (codigo.upper(),),
        )