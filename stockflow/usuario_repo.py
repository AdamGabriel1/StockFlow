from typing import List, Optional

from .database import get_conn, transacao
from .models import Usuario


class UsuarioRepo:

    @staticmethod
    def _row(row) -> Usuario:
        return Usuario(
            id=row["id"], nome=row["nome"], email=row["email"],
            senha_hash=row["senha_hash"], role=row["role"],
            ativo=bool(row["ativo"]), criado_em=row["criado_em"],
        )

    @staticmethod
    def buscar(id_: int) -> Optional[Usuario]:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM usuarios WHERE id=?", (id_,)).fetchone()
            return UsuarioRepo._row(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def buscar_por_email(email: str) -> Optional[Usuario]:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM usuarios WHERE email=?", (email.lower(),)
            ).fetchone()
            return UsuarioRepo._row(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def listar() -> List[Usuario]:
        conn = get_conn()
        try:
            rows = conn.execute("SELECT * FROM usuarios ORDER BY nome").fetchall()
            return [UsuarioRepo._row(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def inserir(u: Usuario) -> int:
        with transacao() as conn:
            cur = conn.execute(
                """INSERT INTO usuarios
                   (nome, email, senha_hash, role, ativo, criado_em)
                   VALUES (?,?,?,?,?,?)""",
                (u.nome, u.email.lower(), u.senha_hash,
                 u.role, int(u.ativo), u.criado_em),
            )
            return cur.lastrowid

    @staticmethod
    def atualizar_role(id_: int, role: str) -> None:
        if role not in ("admin", "cliente"):
            raise ValueError("role deve ser 'admin' ou 'cliente'.")
        with transacao() as conn:
            cur = conn.execute(
                "UPDATE usuarios SET role=? WHERE id=?", (role, id_)
            )
            if cur.rowcount == 0:
                raise ValueError("Usuário não encontrado.")

    @staticmethod
    def desativar(id_: int) -> None:
        with transacao() as conn:
            cur = conn.execute(
                "UPDATE usuarios SET ativo=0 WHERE id=?", (id_,)
            )
            if cur.rowcount == 0:
                raise ValueError("Usuário não encontrado.")
