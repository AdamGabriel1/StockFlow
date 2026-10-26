import uuid
from datetime import datetime, timedelta
from typing import Optional

from .database import get_conn, transacao, to_sql
from .models import Carrinho, Cliente, ItemPedido, Produto
from decimal import Decimal


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CarrinhoRepo:

    @staticmethod
    def criar() -> Carrinho:
        cid = str(uuid.uuid4())
        agora = _agora()
        with transacao() as conn:
            conn.execute(
                "INSERT INTO carrinhos (id, cliente_id, criado_em, atualizado_em) "
                "VALUES (?, NULL, ?, ?)",
                (cid, agora, agora),
            )
        return Carrinho(id=cid)

    @staticmethod
    def buscar(cid: str) -> Optional[Carrinho]:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT id, cliente_id, cupom_codigo FROM carrinhos WHERE id=?", (cid,)
            ).fetchone()
            if not row:
                return None

            cliente = None
            if row["cliente_id"] is not None:
                crow = conn.execute(
                    "SELECT * FROM clientes WHERE id=?", (row["cliente_id"],)
                ).fetchone()
                if crow:
                    cliente = Cliente(
                        id=crow["id"], nome=crow["nome"], cpf=crow["cpf"],
                        email=crow["email"] or "", endereco=crow["endereco"] or "",
                    )

            itens_rows = conn.execute(
                "SELECT ci.produto_codigo, ci.quantidade, ci.preco_unitario, "
                "       p.nome, p.preco, p.estoque, p.estoque_minimo, p.categoria "
                "FROM carrinho_itens ci "
                "JOIN produtos p ON p.codigo = ci.produto_codigo "
                "WHERE ci.carrinho_id=?",
                (cid,),
            ).fetchall()

            itens = [
                ItemPedido(
                    produto=Produto(
                        codigo=ir["produto_codigo"], nome=ir["nome"],
                        preco=Decimal(str(ir["preco"])),           # ⬅️
                        estoque=ir["estoque"],
                        estoque_minimo=ir["estoque_minimo"],
                        categoria=ir["categoria"],
                    ),
                    quantidade=ir["quantidade"],
                    preco_unitario=Decimal(str(ir["preco_unitario"])),  # ⬅️
                )
                for ir in itens_rows
            ]

            return Carrinho(
                cliente=cliente, itens=itens, id=row["id"],
                cupom_codigo=row["cupom_codigo"],
            )
        finally:
            conn.close()

    @staticmethod
    def _touch(conn, cid: str) -> None:
        conn.execute(
            "UPDATE carrinhos SET atualizado_em=? WHERE id=?",
            (_agora(), cid),
        )

    @staticmethod
    def definir_cliente(cid: str, cliente_id: int) -> None:
        with transacao() as conn:
            cur = conn.execute(
                "UPDATE carrinhos SET cliente_id=?, atualizado_em=? WHERE id=?",
                (cliente_id, _agora(), cid),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Carrinho '{cid}' não encontrado")

    @staticmethod
    def adicionar_item(cid: str, produto: Produto, quantidade: int) -> None:
        with transacao() as conn:
            if conn.execute(
                "SELECT 1 FROM carrinho_itens "
                "WHERE carrinho_id=? AND produto_codigo=?",
                (cid, produto.codigo),
            ).fetchone():
                conn.execute(
                    "UPDATE carrinho_itens SET quantidade = quantidade + ? "
                    "WHERE carrinho_id=? AND produto_codigo=?",
                    (quantidade, cid, produto.codigo),
                )
            else:
                conn.execute(
                    "INSERT INTO carrinho_itens "
                    "(carrinho_id, produto_codigo, quantidade, preco_unitario) "
                    "VALUES (?, ?, ?, ?)",
                    (cid, produto.codigo, quantidade,
                     to_sql(produto.preco)),                 # ⬅️
                )
            CarrinhoRepo._touch(conn, cid)

    @staticmethod
    def remover_item(cid: str, codigo: str) -> bool:
        with transacao() as conn:
            cur = conn.execute(
                "DELETE FROM carrinho_itens "
                "WHERE carrinho_id=? AND produto_codigo=?",
                (cid, codigo),
            )
            if cur.rowcount > 0:
                CarrinhoRepo._touch(conn, cid)
                return True
            return False

    @staticmethod
    def limpar_itens(cid: str) -> None:
        with transacao() as conn:
            conn.execute("DELETE FROM carrinho_itens WHERE carrinho_id=?", (cid,))
            CarrinhoRepo._touch(conn, cid)

    @staticmethod
    def remover(cid: str) -> None:
        with transacao() as conn:
            conn.execute("DELETE FROM carrinho_itens WHERE carrinho_id=?", (cid,))
            conn.execute("DELETE FROM carrinhos WHERE id=?", (cid,))

    @staticmethod
    def purgar_antigos(horas: int = 24) -> int:
        limite = (datetime.now() - timedelta(hours=horas)).isoformat(timespec="seconds")
        with transacao() as conn:
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM carrinhos WHERE atualizado_em < ?", (limite,)
            ).fetchall()]
            for cid in ids:
                conn.execute("DELETE FROM carrinho_itens WHERE carrinho_id=?", (cid,))
                conn.execute("DELETE FROM carrinhos WHERE id=?", (cid,))
            return len(ids)

    # ---- cupom ----
    @staticmethod
    def definir_cupom(cid: str, codigo: Optional[str]) -> None:
        with transacao() as conn:
            cur = conn.execute(
                "UPDATE carrinhos SET cupom_codigo=?, atualizado_em=? WHERE id=?",
                (codigo.upper() if codigo else None, _agora(), cid),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Carrinho '{cid}' não encontrado")