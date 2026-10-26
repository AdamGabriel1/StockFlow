from stockflow.models import Produto, Cliente, Cupom
from stockflow.repositories import ProdutoRepo, ClienteRepo
from stockflow.cupom_repo import CupomRepo
from stockflow.auth import hash_senha
from stockflow.models import Produto, Cliente, Cupom, Usuario
from stockflow.repositories import ProdutoRepo, ClienteRepo
from stockflow.cupom_repo import CupomRepo
from stockflow.usuario_repo import UsuarioRepo


def seed_demo() -> None:
    if not ProdutoRepo.listar():
        demo = [
            Produto("P001", "Caneta Esferográfica", 2.50, 100, 20, "Papelaria"),
            Produto("P002", "Caderno 100 folhas", 15.90, 50, 10, "Papelaria"),
            Produto("P003", "Mochila Escolar", 120.00, 15, 5, "Acessórios"),
            Produto("P004", 'Notebook 15"', 3500.00, 5, 2, "Eletrônicos"),
            Produto("P005", "Mouse Sem Fio", 89.90, 30, 10, "Eletrônicos"),
            Produto("P006", "Lápis HB", 1.20, 8, 30, "Papelaria"),
        ]
        for p in demo:
            try:
                ProdutoRepo.inserir(p)
            except Exception:
                pass

    if not ClienteRepo.listar():
        ClienteRepo.inserir(Cliente("João Silva", "111.111.111-11",
                                    "joao@x.com", "Rua A, 123"))
        ClienteRepo.inserir(Cliente("Maria Souza", "222.222.222-22",
                                    "maria@x.com", "Av. B, 456"))

    if not CupomRepo.listar():
        demo_cupons = [
            Cupom(codigo="BEMVINDO10", tipo="PERCENTUAL", valor=10.0),
            Cupom(codigo="NATAL20",    tipo="PERCENTUAL", valor=20.0,
                  valor_minimo=100.0, uso_maximo=100),
            Cupom(codigo="ABATE15",    tipo="FIXO",       valor=15.0,
                  valor_minimo=50.0),
        ]
        for c in demo_cupons:
            try:
                CupomRepo.inserir(c)
            except Exception:
                pass
    # ---- usuário admin ----
    if not UsuarioRepo.buscar_por_email("admin@stockflow.local"):
        admin = Usuario(
            nome="Admin",
            email="admin@stockflow.local",
            senha_hash=hash_senha("admin123"),
            role="admin",
        )
        UsuarioRepo.inserir(admin)
        print("👤 Admin criado → email: admin@stockflow.local | senha: admin123")
        print("   ⚠️  troque a senha em produção (env STOCKFLOW_SECRET_KEY + dados)")

    print("📦 Dados de demonstração carregados.")