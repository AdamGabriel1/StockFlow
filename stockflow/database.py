import os
import sqlite3
from contextlib import contextmanager
from decimal import Decimal

# Adaptador global: qualquer Decimal bindado vira float.
# Se alguém esquecer to_sql() no futuro, isso ainda salva.
sqlite3.register_adapter(Decimal, float)


def to_sql(v):
    """Converte Decimal → float para o SQLite (que não tem DECIMAL).
    Retorna None/str/int inalterados."""
    return float(v) if isinstance(v, Decimal) else v

DB_NAME = os.getenv("STOCKFLOW_DB", "stockflow.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS produtos (
    codigo         TEXT PRIMARY KEY,
    nome           TEXT NOT NULL,
    preco          REAL NOT NULL CHECK (preco >= 0),
    estoque        INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0),
    estoque_minimo INTEGER NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
    categoria      TEXT NOT NULL DEFAULT 'Geral'
);

CREATE TABLE IF NOT EXISTS clientes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nome     TEXT NOT NULL,
    cpf      TEXT NOT NULL UNIQUE,
    email    TEXT,
    endereco TEXT
);

CREATE TABLE IF NOT EXISTS cupons (
    codigo       TEXT PRIMARY KEY,
    tipo         TEXT NOT NULL CHECK (tipo IN ('PERCENTUAL','FIXO')),
    valor        REAL NOT NULL CHECK (valor > 0),
    valor_minimo REAL NOT NULL DEFAULT 0 CHECK (valor_minimo >= 0),
    data_inicio  TEXT,
    data_fim     TEXT,
    uso_maximo   INTEGER,
    uso_atual    INTEGER NOT NULL DEFAULT 0 CHECK (uso_atual >= 0),
    ativo        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    senha_hash TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'cliente'
               CHECK (role IN ('admin','cliente')),
    ativo      INTEGER NOT NULL DEFAULT 1,
    criado_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pedidos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id     INTEGER NOT NULL,
    data           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'PENDENTE',
    subtotal       REAL NOT NULL DEFAULT 0,
    desconto_pct   REAL NOT NULL DEFAULT 0,
    frete          REAL NOT NULL DEFAULT 0,
    total          REAL NOT NULL DEFAULT 0,
    cupom_codigo   TEXT,
    cupom_desconto REAL NOT NULL DEFAULT 0,
    usuario_id     INTEGER,                              -- ⬅️ NOVO
    FOREIGN KEY (cliente_id)   REFERENCES clientes(id),
    FOREIGN KEY (cupom_codigo) REFERENCES cupons(codigo) ON DELETE SET NULL,
    FOREIGN KEY (usuario_id)   REFERENCES usuarios(id)   ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id      INTEGER NOT NULL,
    produto_codigo TEXT NOT NULL,
    produto_nome   TEXT NOT NULL,
    quantidade     INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario REAL NOT NULL,
    desconto_pct   REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    FOREIGN KEY (produto_codigo) REFERENCES produtos(codigo)
);

CREATE TABLE IF NOT EXISTS carrinhos (
    id            TEXT PRIMARY KEY,
    cliente_id    INTEGER,
    cupom_codigo  TEXT,
    criado_em     TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    FOREIGN KEY (cliente_id)   REFERENCES clientes(id) ON DELETE SET NULL,
    FOREIGN KEY (cupom_codigo) REFERENCES cupons(codigo) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS carrinho_itens (
    carrinho_id    TEXT NOT NULL,
    produto_codigo TEXT NOT NULL,
    quantidade     INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario REAL NOT NULL,
    PRIMARY KEY (carrinho_id, produto_codigo),
    FOREIGN KEY (carrinho_id)    REFERENCES carrinhos(id)  ON DELETE CASCADE,
    FOREIGN KEY (produto_codigo) REFERENCES produtos(codigo)
);

CREATE INDEX IF NOT EXISTS idx_carrinhos_atualizado ON carrinhos(atualizado_em);
CREATE INDEX IF NOT EXISTS idx_pedidos_data         ON pedidos(data);
CREATE INDEX IF NOT EXISTS idx_itens_pedido         ON itens_pedido(pedido_id);
CREATE INDEX IF NOT EXISTS idx_cupons_ativo         ON cupons(ativo);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transacao():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _coluna_existe(conn, tabela: str, coluna: str) -> bool:
    return coluna in [r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")]


def _migrar():
    """Adiciona colunas novas em bancos criados em versões anteriores."""
    conn = get_conn()
    try:
        if not _coluna_existe(conn, "pedidos", "usuario_id"):
            conn.execute("ALTER TABLE pedidos ADD COLUMN usuario_id INTEGER")
        if not _coluna_existe(conn, "pedidos", "cupom_codigo"):
            conn.execute("ALTER TABLE pedidos ADD COLUMN cupom_codigo TEXT")
        if not _coluna_existe(conn, "pedidos", "cupom_desconto"):
            conn.execute(
                "ALTER TABLE pedidos ADD COLUMN cupom_desconto REAL NOT NULL DEFAULT 0"
            )
        if not _coluna_existe(conn, "carrinhos", "cupom_codigo"):
            conn.execute("ALTER TABLE carrinhos ADD COLUMN cupom_codigo TEXT")
        conn.commit()
    finally:
        conn.close()


def inicializar():
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    _migrar()