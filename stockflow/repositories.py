from typing import List, Optional

from .database import get_conn, transacao, to_sql
from .models import Produto, Cliente, Pedido, ItemPedido
from .cupom_repo import CupomRepo
from decimal import Decimal


# =====================================================================
# ProdutoRepo
# =====================================================================
class ProdutoRepo:
    _ORDEM_PRODUTO = {
        "codigo":   "codigo ASC",
        "nome":     "nome ASC",
        "-nome":    "nome DESC",
        "preco":    "preco ASC",
        "-preco":   "preco DESC",
        "estoque":  "estoque ASC",
        "-estoque": "estoque DESC",
    }

    @staticmethod
    def listar_paginado(
        limit: int = 20,
        offset: int = 0,
        q: Optional[str] = None,
        categoria: Optional[str] = None,
        preco_min: Optional[float] = None,
        preco_max: Optional[float] = None,
        apenas_alerta: bool = False,
        ordenar: str = "nome",
    ):
        """Devolve (items, total). Usa whitelist para ordenar (evita SQLi)."""
        where, params = [], []
        if q:
            where.append("nome LIKE ?")
            params.append(f"%{q}%")
        if categoria:
            where.append("categoria = ?")
            params.append(categoria)
        if preco_min is not None:
            where.append("preco >= ?")
            params.append(to_sql(preco_min))
        if preco_max is not None:
            where.append("preco <= ?")
            params.append(to_sql(preco_max))
        if apenas_alerta:
            where.append("estoque <= estoque_minimo")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        order_sql = ProdutoRepo._ORDEM_PRODUTO.get(ordenar, "nome ASC")

        conn = get_conn()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM produtos {where_sql}", params
            ).fetchone()["c"]
            rows = conn.execute(
                f"SELECT * FROM produtos {where_sql} "
                f"ORDER BY {order_sql} LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
            return [ProdutoRepo._row(r) for r in rows], total
        finally:
            conn.close()

    @staticmethod
    def inserir(p: Produto) -> None:
        with transacao() as conn:
            conn.execute(
                """INSERT INTO produtos
                   (codigo, nome, preco, estoque, estoque_minimo, categoria)
                   VALUES (?,?,?,?,?,?)""",
                (p.codigo, p.nome, to_sql(p.preco),
                 p.estoque, p.estoque_minimo, p.categoria),
            )

    @staticmethod
    def atualizar(p: Produto) -> None:
        with transacao() as conn:
            conn.execute(
                """UPDATE produtos
                   SET nome=?, preco=?, estoque=?, estoque_minimo=?, categoria=?
                   WHERE codigo=?""",
                (p.nome, to_sql(p.preco),
                 p.estoque, p.estoque_minimo, p.categoria, p.codigo),
            )

    @staticmethod
    def excluir(codigo: str) -> None:
        with transacao() as conn:
            conn.execute("DELETE FROM produtos WHERE codigo=?", (codigo,))

    @staticmethod
    def _row(row) -> Produto:
        return Produto(
            codigo=row["codigo"], nome=row["nome"],
            preco=Decimal(str(row["preco"])),        # ⬅️
            estoque=row["estoque"], estoque_minimo=row["estoque_minimo"],
            categoria=row["categoria"],
        )

    @staticmethod
    def buscar(codigo: str) -> Optional[Produto]:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM produtos WHERE codigo=?", (codigo,)
            ).fetchone()
            return ProdutoRepo._row(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def listar() -> List[Produto]:
        conn = get_conn()
        try:
            rows = conn.execute("SELECT * FROM produtos ORDER BY nome").fetchall()
            return [ProdutoRepo._row(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def buscar_por_nome(termo: str) -> List[Produto]:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM produtos WHERE nome LIKE ? ORDER BY nome",
                (f"%{termo}%",),
            ).fetchall()
            return [ProdutoRepo._row(r) for r in rows]
        finally:
            conn.close()


# =====================================================================
# ClienteRepo
# =====================================================================
class ClienteRepo:
    @staticmethod
    def inserir(c: Cliente) -> int:
        with transacao() as conn:
            cur = conn.execute(
                "INSERT INTO clientes (nome, cpf, email, endereco) VALUES (?,?,?,?)",
                (c.nome, c.cpf, c.email, c.endereco),
            )
            return cur.lastrowid

    @staticmethod
    def atualizar(c: Cliente) -> None:
        with transacao() as conn:
            conn.execute(
                "UPDATE clientes SET nome=?, cpf=?, email=?, endereco=? WHERE id=?",
                (c.nome, c.cpf, c.email, c.endereco, c.id),
            )

    @staticmethod
    def _row(row) -> Cliente:
        return Cliente(
            id=row["id"], nome=row["nome"], cpf=row["cpf"],
            email=row["email"] or "", endereco=row["endereco"] or "",
        )

    @staticmethod
    def buscar(id_: int) -> Optional[Cliente]:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM clientes WHERE id=?", (id_,)).fetchone()
            return ClienteRepo._row(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def buscar_por_cpf(cpf: str) -> Optional[Cliente]:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM clientes WHERE cpf=?", (cpf,)).fetchone()
            return ClienteRepo._row(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def listar() -> List[Cliente]:
        conn = get_conn()
        try:
            rows = conn.execute("SELECT * FROM clientes ORDER BY nome").fetchall()
            return [ClienteRepo._row(r) for r in rows]
        finally:
            conn.close()


# =====================================================================
# PedidoRepo
# =====================================================================
class PedidoRepo:

    @staticmethod
    def listar_paginado(
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        cliente_id: Optional[int] = None,
        usuario_id: Optional[int] = None,          # ⬅️ NOVO
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None,
    ):
        where, params = [], []
        if status:
            where.append("status = ?")
            params.append(status.upper())
        if cliente_id is not None:
            where.append("cliente_id = ?")
            params.append(cliente_id)
        if usuario_id is not None:                 # ⬅️ NOVO
            where.append("usuario_id = ?")
            params.append(usuario_id)
        if data_inicio:
            where.append("data >= ?")
            params.append(data_inicio)
        if data_fim:
            where.append("data <= ?")
            params.append(data_fim)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        conn = get_conn()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM pedidos {where_sql}", params
            ).fetchone()["c"]
            ids = [
                r["id"] for r in conn.execute(
                    f"SELECT id FROM pedidos {where_sql} "
                    f"ORDER BY id DESC LIMIT ? OFFSET ?",
                    params + [limit, offset],
                ).fetchall()
            ]
        finally:
            conn.close()
        return [p for p in (PedidoRepo.buscar(i) for i in ids) if p], total

    # ---- helper interno: trabalha numa conexão já aberta ----------------
    @staticmethod
    def _inserir_no_conn(conn, pedido: Pedido) -> int:
        # 1) valida estoque
        for item in pedido.itens:
            row = conn.execute(
                "SELECT estoque FROM produtos WHERE codigo=?",
                (item.produto.codigo,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Produto {item.produto.codigo} não encontrado.")
            if row["estoque"] < item.quantidade:
                raise ValueError(
                    f"Estoque insuficiente para '{item.produto.nome}': "
                    f"disponível {row['estoque']}, solicitado {item.quantidade}."
                )

        # 1.5) consome cupom atomicamente
        if pedido.cupom_codigo:
            CupomRepo.consumir_no_conn(conn, pedido.cupom_codigo)

        # 2) cria o pedido — TODOS os monetários/percentuais passam por to_sql
        cur = conn.execute(
            """INSERT INTO pedidos
               (cliente_id, data, status, subtotal, desconto_pct, frete, total,
                cupom_codigo, cupom_desconto, usuario_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (pedido.cliente.id, pedido.data, pedido.status,
             to_sql(pedido.subtotal), to_sql(pedido.desconto),
             to_sql(pedido.frete), to_sql(pedido.total),
             pedido.cupom_codigo, to_sql(pedido.cupom_desconto),
             pedido.usuario_id),
        )
        pedido_id = cur.lastrowid

        for item in pedido.itens:
            conn.execute(
                """INSERT INTO itens_pedido
                   (pedido_id, produto_codigo, produto_nome,
                    quantidade, preco_unitario, desconto_pct)
                   VALUES (?,?,?,?,?,?)""",
                (pedido_id, item.produto.codigo, item.produto.nome,
                 item.quantidade, to_sql(item.preco_unitario),
                 to_sql(item.desconto)),
            )
            conn.execute(
                "UPDATE produtos SET estoque = estoque - ? WHERE codigo=?",
                (item.quantidade, item.produto.codigo),
            )
        return pedido_id

    # ---- entradas públicas ---------------------------------------------
    @staticmethod
    def inserir(pedido: Pedido) -> int:
        with transacao() as conn:
            return PedidoRepo._inserir_no_conn(conn, pedido)

    @staticmethod
    def inserir_e_limpar_carrinho(pedido: Pedido, carrinho_id: str) -> int:
        """Checkout atômico: pedido + baixa de estoque + remoção do carrinho."""
        with transacao() as conn:
            pid = PedidoRepo._inserir_no_conn(conn, pedido)
            conn.execute(
                "DELETE FROM carrinho_itens WHERE carrinho_id=?", (carrinho_id,)
            )
            conn.execute("DELETE FROM carrinhos WHERE id=?", (carrinho_id,))
            return pid

    @staticmethod
    def cancelar(pedido_id: int) -> None:
        with transacao() as conn:
            row = conn.execute(
                "SELECT status FROM pedidos WHERE id=?", (pedido_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Pedido não encontrado.")
            if row["status"] == "CANCELADO":
                raise ValueError("Pedido já está cancelado.")

            itens = conn.execute(
                "SELECT produto_codigo, quantidade FROM itens_pedido WHERE pedido_id=?",
                (pedido_id,),
            ).fetchall()
            for it in itens:
                conn.execute(
                    "UPDATE produtos SET estoque = estoque + ? WHERE codigo=?",
                    (it["quantidade"], it["produto_codigo"]),
                )
            conn.execute(
                "UPDATE pedidos SET status='CANCELADO' WHERE id=?", (pedido_id,)
            )
            cupom_row = conn.execute(
                "SELECT cupom_codigo FROM pedidos WHERE id=?", (pedido_id,)
            ).fetchone()
            if cupom_row and cupom_row["cupom_codigo"]:
                CupomRepo.estornar_no_conn(conn, cupom_row["cupom_codigo"])

    @staticmethod
    def buscar(pedido_id: int) -> Optional[Pedido]:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM pedidos WHERE id=?", (pedido_id,)
            ).fetchone()
            if not row:
                return None

            cliente_row = conn.execute(
                "SELECT * FROM clientes WHERE id=?", (row["cliente_id"],)
            ).fetchone()
            cliente = ClienteRepo._row(cliente_row) if cliente_row else None

            itens_rows = conn.execute(
                "SELECT * FROM itens_pedido WHERE pedido_id=?", (pedido_id,)
            ).fetchall()
            itens = []
            for ir in itens_rows:
                prod = Produto(
                    codigo=ir["produto_codigo"],
                    nome=ir["produto_nome"],
                    preco=Decimal(str(ir["preco_unitario"])),      # ⬅️
                )
                itens.append(ItemPedido(
                    produto=prod,
                    quantidade=ir["quantidade"],
                    preco_unitario=Decimal(str(ir["preco_unitario"])),  # ⬅️
                    desconto=ir["desconto_pct"],
                ))

            return Pedido(
                id=row["id"], cliente=cliente, itens=itens, data=row["data"],
                status=row["status"],
                subtotal=Decimal(str(row["subtotal"])),               # ⬅️
                desconto=row["desconto_pct"],
                frete=Decimal(str(row["frete"])),                     # ⬅️
                total=Decimal(str(row["total"])),                     # ⬅️
                cupom_codigo=row["cupom_codigo"],
                cupom_desconto=Decimal(str(row["cupom_desconto"])),   # ⬅️
                usuario_id=row["usuario_id"],
            )
        finally:
            conn.close()

    @staticmethod
    def listar(data_inicio: Optional[str] = None,
               data_fim: Optional[str] = None) -> List[Pedido]:
        conn = get_conn()
        try:
            sql = "SELECT id FROM pedidos"
            params = []
            if data_inicio and data_fim:
                sql += " WHERE data BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            sql += " ORDER BY id DESC"
            ids = [r["id"] for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
        return [p for p in (PedidoRepo.buscar(i) for i in ids) if p]