from .database import inicializar
from .models import Produto, Cliente, Carrinho
from .repositories import ProdutoRepo, ClienteRepo, PedidoRepo
from .services import EstoqueService, VendaService, DescontoService, FreteService
from .reports import RelatorioService
from stockflow.seed import seed_demo


# ---------- helpers ----------
def linha(titulo=""):
    print("|" + "=" * 48 + "|")
    if titulo:
        print("|" + titulo.center(48) + "|")
        print("|" + "=" * 48 + "|")


def ler_float(msg):
    while True:
        try:
            return float(input(msg))
        except ValueError:
            print("Valor inválido.")


def ler_int(msg):
    while True:
        try:
            return int(input(msg))
        except ValueError:
            print("Valor inválido.")


# ---------- produtos ----------
def menu_produtos():
    while True:
        linha("Gerenciar Produtos")
        print("|1. Cadastrar                   |")
        print("|2. Listar                      |")
        print("|3. Buscar por nome             |")
        print("|4. Atualizar                   |")
        print("|5. Excluir                     |")
        print("|6. Alertas de reposição        |")
        print("|7. Repor estoque               |")
        print("|0. Voltar                      |")
        print("|" + "=" * 48 + "|")
        op = input("Escolha: ")

        if op == "1":
            codigo = input("Código: ").strip()
            if ProdutoRepo.buscar(codigo):
                print("Já existe produto com esse código.")
                continue
            nome = input("Nome: ").strip()
            preco = ler_float("Preço: ")
            estoque = ler_int("Estoque inicial: ")
            minimo = ler_int("Estoque mínimo: ")
            cat = input("Categoria: ").strip() or "Geral"
            ProdutoRepo.inserir(Produto(codigo, nome, preco, estoque, minimo, cat))
            print("✔ Produto cadastrado.")

        elif op == "2":
            for p in ProdutoRepo.listar():
                print(" ", p)

        elif op == "3":
            termo = input("Termo: ")
            for p in ProdutoRepo.buscar_por_nome(termo):
                print(" ", p)

        elif op == "4":
            codigo = input("Código: ").strip()
            p = ProdutoRepo.buscar(codigo)
            if not p:
                print("Produto não encontrado.")
                continue
            p.nome = input(f"Nome [{p.nome}]: ").strip() or p.nome
            novo = input(f"Preço [{p.preco}]: ").strip()
            if novo:
                p.preco = float(novo)
            novo = input(f"Estoque mínimo [{p.estoque_minimo}]: ").strip()
            if novo:
                p.estoque_minimo = int(novo)
            p.categoria = input(f"Categoria [{p.categoria}]: ").strip() or p.categoria
            ProdutoRepo.atualizar(p)
            print("✔ Atualizado.")

        elif op == "5":
            codigo = input("Código: ").strip()
            try:
                ProdutoRepo.excluir(codigo)
                print("✔ Excluído.")
            except Exception as e:
                print(f"Erro: {e}")

        elif op == "6":
            alertas = EstoqueService.listar_alertas()
            if not alertas:
                print("Nenhum produto em alerta. 👍")
            for p in alertas:
                print(f"  ⚠ {p.nome} (cód. {p.codigo}) — estoque {p.estoque} / mínimo {p.estoque_minimo}")

        elif op == "7":
            codigo = input("Código: ").strip()
            qtd = ler_int("Quantidade a repor: ")
            try:
                p = EstoqueService.repor(codigo, qtd)
                print(f"✔ Novo estoque de '{p.nome}': {p.estoque}")
            except ValueError as e:
                print(f"Erro: {e}")

        elif op == "0":
            return


# ---------- clientes ----------
def menu_clientes():
    while True:
        linha("Gerenciar Clientes")
        print("|1. Cadastrar                   |")
        print("|2. Listar                      |")
        print("|3. Buscar por CPF              |")
        print("|0. Voltar                      |")
        print("|" + "=" * 48 + "|")
        op = input("Escolha: ")

        if op == "1":
            nome = input("Nome: ").strip()
            cpf = input("CPF: ").strip()
            if ClienteRepo.buscar_por_cpf(cpf):
                print("CPF já cadastrado.")
                continue
            email = input("Email: ").strip()
            end = input("Endereço: ").strip()
            cid = ClienteRepo.inserir(Cliente(nome, cpf, email, end))
            print(f"✔ Cliente cadastrado (id={cid}).")

        elif op == "2":
            for c in ClienteRepo.listar():
                print(" ", c)

        elif op == "3":
            cpf = input("CPF: ").strip()
            c = ClienteRepo.buscar_por_cpf(cpf)
            print(" ", c if c else "Não encontrado.")

        elif op == "0":
            return


# ---------- vendas ----------
def fluxo_venda():
    carrinho = Carrinho()
    print("\n--- Novo Carrinho ---")

    # 1) cliente
    while True:
        cpf = input("CPF do cliente (ou Enter para listar): ").strip()
        if not cpf:
            for c in ClienteRepo.listar():
                print(" ", c)
            continue
        cliente = ClienteRepo.buscar_por_cpf(cpf)
        if cliente:
            carrinho.cliente = cliente
            print(f"Cliente: {cliente.nome}")
            break
        print("Cliente não encontrado.")

    # 2) itens
    while True:
        if carrinho.itens:
            print("\n--- Carrinho ---")
            for it in carrinho.itens:
                print(" ", it)
            sub = carrinho.subtotal()
            desc = DescontoService.calcular(carrinho)
            frete = FreteService.calcular(carrinho)
            print(f"  Subtotal: R$ {sub:.2f} | Desconto: {desc:.0f}% | Frete: R$ {frete:.2f}")
            print(f"  Total estimado: R$ {sub * (1 - desc / 100) + frete:.2f}")

        print("\n1 - Adicionar item | 2 - Remover item | 3 - Finalizar | 0 - Cancelar")
        op = input("Opção: ")
        if op == "1":
            codigo = input("Código do produto: ").strip()
            p = ProdutoRepo.buscar(codigo)
            if not p:
                print("Produto não encontrado.")
                continue
            qtd = ler_int("Quantidade: ")
            if qtd > p.estoque:
                print(f"Estoque insuficiente. Disponível: {p.estoque}")
                continue
            carrinho.adicionar(p, qtd)
            print(f"✔ {p.nome} x{qtd} adicionado.")
        elif op == "2":
            codigo = input("Código a remover: ").strip()
            print("✔ Removido." if carrinho.remover(codigo) else "Não estava no carrinho.")
        elif op == "3":
            try:
                pedido = VendaService.finalizar(carrinho)
                print(f"\n✔ Pedido #{pedido.id} finalizado!")
                print(f"  Cliente : {pedido.cliente.nome}")
                print(f"  Subtotal: R$ {pedido.subtotal:.2f}")
                print(f"  Desconto: {pedido.desconto:.0f}%")
                print(f"  Frete   : R$ {pedido.frete:.2f}")
                print(f"  Total   : R$ {pedido.total:.2f}")
                return
            except ValueError as e:
                print(f"Erro ao finalizar: {e}")
        elif op == "0":
            print("Venda cancelada.")
            return


def menu_vendas():
    while True:
        linha("Vendas")
        print("|1. Nova venda                  |")
        print("|2. Cancelar pedido             |")
        print("|3. Ver pedido                  |")
        print("|0. Voltar                      |")
        print("|" + "=" * 48 + "|")
        op = input("Escolha: ")

        if op == "1":
            fluxo_venda()
        elif op == "2":
            pid = ler_int("ID do pedido: ")
            try:
                VendaService.cancelar(pid)
                print("✔ Pedido cancelado e estoque devolvido.")
            except ValueError as e:
                print(f"Erro: {e}")
        elif op == "3":
            pid = ler_int("ID do pedido: ")
            p = PedidoRepo.buscar(pid)
            if not p:
                print("Pedido não encontrado.")
                continue
            print(f"\nPedido #{p.id} | {p.data} | {p.status}")
            print(f"Cliente: {p.cliente.nome if p.cliente else '-'}")
            for it in p.itens:
                print(" ", it)
            print(f"  Subtotal: R$ {p.subtotal:.2f} | Desconto: {p.desconto:.0f}% "
                  f"| Frete: R$ {p.frete:.2f} | Total: R$ {p.total:.2f}")
        elif op == "0":
            return


# ---------- relatórios ----------
def menu_relatorios():
    while True:
        linha("Relatórios")
        print("|1. Histórico de vendas         |")
        print("|2. Faturamento                 |")
        print("|3. Top produtos                |")
        print("|4. Exportar CSV                |")
        print("|0. Voltar                      |")
        print("|" + "=" * 48 + "|")
        op = input("Escolha: ")

        if op == "1":
            ini = input("Data início (AAAA-MM-DD, Enter=pular): ").strip() or None
            fim = input("Data fim  (AAAA-MM-DD, Enter=pular): ").strip() or None
            for p in RelatorioService.historico(ini, fim):
                print(f"  #{p.id:<4} {p.data}  {p.status:<10}  R$ {p.total:>9.2f}  {p.cliente.nome if p.cliente else '-'}")

        elif op == "2":
            ini = input("Data início (AAAA-MM-DD, Enter=pular): ").strip() or None
            fim = input("Data fim  (AAAA-MM-DD, Enter=pular): ").strip() or None
            r = RelatorioService.faturamento(ini, fim)
            print(f"  Pedidos: {r['n_pedidos']}")
            print(f"  Faturamento: R$ {r['faturamento']:.2f}")
            print(f"  Descontos  : R$ {r['total_descontos']:.2f}")
            print(f"  Frete      : R$ {r['total_frete']:.2f}")

        elif op == "3":
            for i, p in enumerate(RelatorioService.top_produtos(10), 1):
                print(f"  {i:>2}. {p['produto_nome']:<25} qtd={p['qtd_total']:<5} receita=R$ {p['receita']:>9.2f}")

        elif op == "4":
            caminho = input("Nome do arquivo (ex: vendas.csv): ").strip() or "vendas.csv"
            n = RelatorioService.exportar_csv(caminho)
            print(f"✔ {n} pedidos exportados para {caminho}")

        elif op == "0":
            return


# ---------- principal ----------
def run():
    inicializar()
    seed_demo()
    while True:
        linha("StockFlow v1.0 — Estoque & Vendas")
        print("|1. Produtos                    |")
        print("|2. Clientes                    |")
        print("|3. Vendas                      |")
        print("|4. Relatórios                  |")
        print("|0. Sair                        |")
        print("|" + "=" * 48 + "|")
        op = input("Escolha: ")
        if op == "1":   menu_produtos()
        elif op == "2": menu_clientes()
        elif op == "3": menu_vendas()
        elif op == "4": menu_relatorios()
        elif op == "0":
            print("Até logo! 👋")
            return
