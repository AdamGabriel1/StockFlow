import os
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from stockflow import database
from stockflow.api.main import app


class TestStockFlowAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls._orig = database.DB_NAME
        database.DB_NAME = os.path.join(cls.tmp, "test_api.db")

    @classmethod
    def tearDownClass(cls):
        database.DB_NAME = cls._orig
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        database.inicializar()
        with database.transacao() as conn:
            conn.execute("DELETE FROM carrinho_itens")
            conn.execute("DELETE FROM carrinhos")
            conn.execute("DELETE FROM itens_pedido")
            conn.execute("DELETE FROM pedidos")
            conn.execute("DELETE FROM cupons")
            conn.execute("DELETE FROM produtos")
            conn.execute("DELETE FROM clientes")
            conn.execute("DELETE FROM usuarios")
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN "
                "('clientes','pedidos','itens_pedido','usuarios')"
            )

        self.client = TestClient(app)

        from stockflow.auth import hash_senha
        from stockflow.models import Usuario
        from stockflow.usuario_repo import UsuarioRepo

        UsuarioRepo.inserir(Usuario(
            nome="Admin", email="admin@test.local",
            senha_hash=hash_senha("admin123"), role="admin",
        ))
        r = self.client.post("/auth/login", data={
            "username": "admin@test.local",
            "password": "admin123",
        })
        assert r.status_code == 200, r.text
        self.admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ------- helpers -------
    def _cria_produto(self, codigo="A1", nome="Caneta", preco=2.5,
                      estoque=10, categoria="Teste", estoque_minimo=2):
        r = self.client.post("/produtos", headers=self.admin_h, json={
            "codigo": codigo, "nome": nome, "preco": preco,
            "estoque": estoque, "estoque_minimo": estoque_minimo,
            "categoria": categoria,
        })
        assert r.status_code == 201, r.text
        return r.json()

    def _cria_cliente(self, cpf="123"):
        r = self.client.post("/clientes", json={
            "nome": "Fulano", "cpf": cpf, "email": "f@x.com", "endereco": "Rua 1",
        })
        assert r.status_code == 201, r.text
        return r.json()

    def _cria_cupom(self, codigo="X10", tipo="PERCENTUAL", valor=10.0,
                    valor_minimo=0.0, uso_maximo=None):
        r = self.client.post("/cupons", headers=self.admin_h, json={
            "codigo": codigo, "tipo": tipo, "valor": valor,
            "valor_minimo": valor_minimo, "uso_maximo": uso_maximo,
        })
        assert r.status_code == 201, r.text
        return r.json()

    # ------- base -------
    def test_health(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_crud_produto(self):
        self._cria_produto()
        r = self.client.get("/produtos/A1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nome"], "Caneta")

        r = self.client.put("/produtos/A1", json={"preco": 3.0},
                            headers=self.admin_h)
        self.assertEqual(r.json()["preco"], 3.0)

        r = self.client.delete("/produtos/A1", headers=self.admin_h)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.client.get("/produtos/A1").status_code, 404)

    def test_duplicado_retorna_409(self):
        self._cria_produto()
        r = self.client.post("/produtos", headers=self.admin_h, json={
            "codigo": "A1", "nome": "X", "preco": 1,
        })
        self.assertEqual(r.status_code, 409)

    def test_alerta_reposicao(self):
        self._cria_produto("A1", "OK", estoque=10)
        self.client.post("/produtos", headers=self.admin_h, json={
            "codigo": "A2", "nome": "Baixo", "preco": 1,
            "estoque": 1, "estoque_minimo": 5, "categoria": "X",
        })
        r = self.client.get("/produtos/alertas")
        self.assertEqual([p["codigo"] for p in r.json()], ["A2"])

    def test_fluxo_carrinho_e_checkout(self):
        self._cria_produto("A1", estoque=20, preco=10.0)
        cli = self._cria_cliente()

        cid = self.client.post("/carrinho").json()["cart_id"]
        h = {"X-Cart-Id": cid}

        r = self.client.post("/carrinho/cliente", headers=h,
                             json={"cliente_id": cli["id"]})
        self.assertEqual(r.status_code, 200)

        r = self.client.post("/carrinho/itens", headers=h,
                             json={"produto_codigo": "A1", "quantidade": 15})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["desconto"], 5.0)

        r = self.client.post("/pedidos/checkout", headers=h)
        self.assertEqual(r.status_code, 201, r.text)
        pedido = r.json()
        self.assertEqual(pedido["subtotal"], 150.0)
        self.assertEqual(pedido["desconto"], 5.0)
        self.assertEqual(self.client.get("/produtos/A1").json()["estoque"], 5)
        self.assertEqual(self.client.get("/carrinho", headers=h).status_code, 404)

    def test_estoque_insuficiente_via_api(self):
        self._cria_produto("A1", estoque=2)
        cli = self._cria_cliente()
        cid = self.client.post("/carrinho").json()["cart_id"]
        h = {"X-Cart-Id": cid}
        self.client.post("/carrinho/cliente", headers=h,
                         json={"cliente_id": cli["id"]})
        r = self.client.post("/carrinho/itens", headers=h,
                             json={"produto_codigo": "A1", "quantidade": 10})
        self.assertEqual(r.status_code, 400)

    def test_cancelar_restaura_estoque(self):
        self._cria_produto("A1", estoque=10)
        cli = self._cria_cliente()
        r = self.client.post("/pedidos", json={
            "cliente_id": cli["id"],
            "itens": [{"produto_codigo": "A1", "quantidade": 4}],
        })
        self.assertEqual(r.status_code, 201, r.text)
        pid = r.json()["id"]
        self.assertEqual(self.client.get("/produtos/A1").json()["estoque"], 6)

        self.client.post(f"/pedidos/{pid}/cancelar", headers=self.admin_h)
        self.assertEqual(self.client.get("/produtos/A1").json()["estoque"], 10)

    def test_exportar_csv(self):
        self._cria_produto("A1", estoque=10, preco=5.0)
        cli = self._cria_cliente()
        self.client.post("/pedidos", json={
            "cliente_id": cli["id"],
            "itens": [{"produto_codigo": "A1", "quantidade": 2}],
        })
        r = self.client.get("/relatorios/exportar-csv", headers=self.admin_h)
        self.assertEqual(r.status_code, 200)
        self.assertIn("pedido_id", r.text)
        self.assertIn("Fulano", r.text)

    # ------- Cap. 2: carrinho persistido -------
    def test_carrinho_persiste_no_banco(self):
        from stockflow.carrinho_repo import CarrinhoRepo
        cid = self.client.post("/carrinho").json()["cart_id"]
        car = CarrinhoRepo.buscar(cid)
        self.assertIsNotNone(car)
        self.assertEqual(car.id, cid)

    def test_purgar_carrinhos_antigos(self):
        from stockflow.carrinho_repo import CarrinhoRepo
        from stockflow.database import transacao

        cid = self.client.post("/carrinho").json()["cart_id"]
        with transacao() as conn:
            conn.execute(
                "UPDATE carrinhos SET atualizado_em='2000-01-01T00:00:00' WHERE id=?",
                (cid,),
            )
        removidos = CarrinhoRepo.purgar_antigos(24)
        self.assertEqual(removidos, 1)
        self.assertIsNone(CarrinhoRepo.buscar(cid))

    # ------- Cap. 3: cupons -------
    def test_criar_e_listar_cupom(self):
        c = self._cria_cupom("X10")
        self.assertEqual(c["codigo"], "X10")
        self.assertTrue(c["vigente"])
        ids = [x["codigo"]
               for x in self.client.get("/cupons", headers=self.admin_h).json()]
        self.assertIn("X10", ids)

    def test_aplicar_cupom_no_carrinho(self):
        self._cria_produto("A1", preco=100.0, estoque=10)
        self._cria_cupom("X10", valor=10.0)
        cid = self.client.post("/carrinho").json()["cart_id"]
        h = {"X-Cart-Id": cid}
        self.client.post("/carrinho/itens", headers=h,
                         json={"produto_codigo": "A1", "quantidade": 1})
        r = self.client.post("/carrinho/cupom", headers=h,
                             json={"codigo": "X10"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["cupom_codigo"], "X10")
        self.assertEqual(r.json()["cupom_desconto"], 10.0)

    def test_cupom_minimo_rejeitado(self):
        self._cria_produto("A1", preco=10.0, estoque=10)
        self._cria_cupom("MIN50", valor=10.0, valor_minimo=50.0)
        cid = self.client.post("/carrinho").json()["cart_id"]
        h = {"X-Cart-Id": cid}
        self.client.post("/carrinho/itens", headers=h,
                         json={"produto_codigo": "A1", "quantidade": 1})
        r = self.client.post("/carrinho/cupom", headers=h,
                             json={"codigo": "MIN50"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("mínimo", r.json()["detail"])

    def test_cupom_esgotado(self):
        self._cria_produto("A1", preco=10.0, estoque=100)
        cli = self._cria_cliente()
        self._cria_cupom("ONCE", valor=5.0, uso_maximo=1)

        cid = self.client.post("/carrinho").json()["cart_id"]
        h = {"X-Cart-Id": cid}
        self.client.post("/carrinho/cliente", headers=h,
                         json={"cliente_id": cli["id"]})
        self.client.post("/carrinho/itens", headers=h,
                         json={"produto_codigo": "A1", "quantidade": 1})
        r = self.client.post("/carrinho/cupom", headers=h,
                             json={"codigo": "ONCE"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/pedidos/checkout", headers=h)
        self.assertEqual(r.status_code, 201, r.text)

        self.assertEqual(
            self.client.get("/cupons/ONCE", headers=self.admin_h).json()["uso_atual"],
            1,
        )

        cid2 = self.client.post("/carrinho").json()["cart_id"]
        h2 = {"X-Cart-Id": cid2}
        self.client.post("/carrinho/cliente", headers=h2,
                         json={"cliente_id": cli["id"]})
        self.client.post("/carrinho/itens", headers=h2,
                         json={"produto_codigo": "A1", "quantidade": 1})
        r = self.client.post("/carrinho/cupom", headers=h2,
                             json={"codigo": "ONCE"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("esgotado", r.json()["detail"])

    def test_cancelar_pedido_devolve_uso_do_cupom(self):
        self._cria_produto("A1", preco=10.0, estoque=10)
        cli = self._cria_cliente()
        self._cria_cupom("ONCE", valor=5.0, uso_maximo=1)

        cid = self.client.post("/carrinho").json()["cart_id"]
        h = {"X-Cart-Id": cid}
        self.client.post("/carrinho/cliente", headers=h,
                         json={"cliente_id": cli["id"]})
        self.client.post("/carrinho/itens", headers=h,
                         json={"produto_codigo": "A1", "quantidade": 1})
        self.client.post("/carrinho/cupom", headers=h,
                         json={"codigo": "ONCE"})
        pid = self.client.post("/pedidos/checkout", headers=h).json()["id"]

        c = self.client.get("/cupons/ONCE", headers=self.admin_h).json()
        self.assertEqual(c["uso_atual"], 1)

        self.client.post(f"/pedidos/{pid}/cancelar", headers=self.admin_h)
        c = self.client.get("/cupons/ONCE", headers=self.admin_h).json()
        self.assertEqual(c["uso_atual"], 0)

    # ------- Cap. 4: auth -------
    def test_register_login_me(self):
        r = self.client.post("/auth/register", json={
            "nome": "Novo", "email": "novo@x.com", "senha": "senha123",
        })
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["role"], "cliente")

        r = self.client.post("/auth/login", data={
            "username": "novo@x.com", "password": "senha123",
        })
        self.assertEqual(r.status_code, 200)
        token = r.json()["access_token"]

        r = self.client.get("/auth/me",
                            headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["email"], "novo@x.com")

    def test_login_senha_errada(self):
        self.client.post("/auth/register", json={
            "nome": "X", "email": "x@x.com", "senha": "certo",
        })
        r = self.client.post("/auth/login", data={
            "username": "x@x.com", "password": "errada",
        })
        self.assertEqual(r.status_code, 401)

    def test_endpoint_admin_sem_token_retorna_401(self):
        r = self.client.post("/produtos", json={
            "codigo": "A1", "nome": "X", "preco": 1,
        })
        self.assertEqual(r.status_code, 401)

    def test_nao_admin_nao_cria_produto(self):
        self.client.post("/auth/register", json={
            "nome": "Cli", "email": "cli@x.com", "senha": "senha123",
        })
        r = self.client.post("/auth/login", data={
            "username": "cli@x.com", "password": "senha123",
        })
        token = r.json()["access_token"]
        r = self.client.post(
            "/produtos",
            headers={"Authorization": f"Bearer {token}"},
            json={"codigo": "A1", "nome": "X", "preco": 1},
        )
        self.assertEqual(r.status_code, 403)

    # ------- Cap. 5: paginação + filtros -------
    def test_paginacao_produtos(self):
        for i in range(25):
            self._cria_produto(f"P{i:02d}", nome=f"Prod{i}", preco=10.0 + i)
        r = self.client.get("/produtos", params={"limit": 10, "offset": 0})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["total"], 25)
        self.assertEqual(len(d["items"]), 10)
        self.assertEqual(d["pagina"], 1)
        self.assertEqual(d["total_paginas"], 3)

        r = self.client.get("/produtos", params={"limit": 10, "offset": 20})
        d = r.json()
        self.assertEqual(len(d["items"]), 5)
        self.assertEqual(d["pagina"], 3)

    def test_filtro_produtos_por_categoria(self):
        self._cria_produto("A1", nome="A", categoria="Papelaria")
        self._cria_produto("A2", nome="B", categoria="Eletrônicos")
        self._cria_produto("A3", nome="C", categoria="Papelaria")
        r = self.client.get("/produtos", params={"categoria": "Papelaria"})
        d = r.json()
        self.assertEqual(d["total"], 2)
        self.assertEqual({p["codigo"] for p in d["items"]}, {"A1", "A3"})

    def test_filtro_produtos_por_preco(self):
        self._cria_produto("A1", preco=10.0)
        self._cria_produto("A2", preco=50.0)
        self._cria_produto("A3", preco=100.0)
        r = self.client.get("/produtos",
                            params={"preco_min": 20, "preco_max": 100})
        d = r.json()
        self.assertEqual(d["total"], 2)
        self.assertEqual({p["codigo"] for p in d["items"]}, {"A2", "A3"})

    def test_busca_produtos_q(self):
        self._cria_produto("A1", nome="Notebook Dell")
        self._cria_produto("A2", nome="Mouse Logitech")
        self._cria_produto("A3", nome="Notebook Lenovo")
        r = self.client.get("/produtos", params={"q": "Notebook"})
        d = r.json()
        self.assertEqual(d["total"], 2)
        self.assertEqual({p["codigo"] for p in d["items"]}, {"A1", "A3"})

    def test_ordenacao_produtos(self):
        self._cria_produto("A1", preco=30.0)
        self._cria_produto("A2", preco=10.0)
        self._cria_produto("A3", preco=20.0)

        r = self.client.get("/produtos", params={"ordenar": "preco"})
        self.assertEqual([p["codigo"] for p in r.json()["items"]],
                         ["A2", "A3", "A1"])

        r = self.client.get("/produtos", params={"ordenar": "-preco"})
        self.assertEqual([p["codigo"] for p in r.json()["items"]],
                         ["A1", "A3", "A2"])

        # valor fora da whitelist → 422 (pattern do Query)
        r = self.client.get("/produtos", params={"ordenar": "; DROP TABLE"})
        self.assertEqual(r.status_code, 422)

    def test_filtro_apenas_alerta(self):
        self._cria_produto("A1", estoque=10, estoque_minimo=2)   # ok
        self._cria_produto("A2", estoque=1, estoque_minimo=5)    # alerta
        r = self.client.get("/produtos", params={"apenas_alerta": "true"})
        d = r.json()
        self.assertEqual(d["total"], 1)
        self.assertEqual(d["items"][0]["codigo"], "A2")

    def test_paginacao_pedidos(self):
        self._cria_produto("A1", preco=10.0, estoque=100)
        cli = self._cria_cliente()
        for _ in range(3):
            r = self.client.post("/pedidos", json={
                "cliente_id": cli["id"],
                "itens": [{"produto_codigo": "A1", "quantidade": 1}],
            })
            self.assertEqual(r.status_code, 201, r.text)

        r = self.client.get("/pedidos", params={"limit": 2, "offset": 0},
                            headers=self.admin_h)                  # ⬅️ auth
        d = r.json()
        self.assertEqual(d["total"], 3)
        self.assertEqual(len(d["items"]), 2)
        self.assertEqual(d["pagina"], 1)

        r = self.client.get("/pedidos", params={"limit": 2, "offset": 2},
                            headers=self.admin_h)                  # ⬅️ auth
        d = r.json()
        self.assertEqual(len(d["items"]), 1)

    # ------- Cap. 9: isolamento de pedidos -------
    def _login_cliente(self, email="cli@x.com", senha="senha123"):
        self.client.post("/auth/register", json={
            "nome": "Cli", "email": email, "senha": senha,
        })
        r = self.client.post("/auth/login", data={
            "username": email, "password": senha,
        })
        token = r.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_get_pedidos_sem_auth_retorna_401(self):
        r = self.client.get("/pedidos")
        self.assertEqual(r.status_code, 401)

    def test_cliente_ve_apenas_seus_pedidos(self):
        self._cria_produto("A1", preco=10.0, estoque=100)
        cli = self._cria_cliente()

        # 2 pedidos guest (usuario_id=NULL)
        for _ in range(2):
            r = self.client.post("/pedidos", json={
                "cliente_id": cli["id"],
                "itens": [{"produto_codigo": "A1", "quantidade": 1}],
            })
            self.assertEqual(r.status_code, 201)

        user_h = self._login_cliente()

        # cliente recém-registrado não tem pedidos → 0
        r = self.client.get("/pedidos", headers=user_h)
        self.assertEqual(r.json()["total"], 0)

        # admin vê os 2 guest
        r = self.client.get("/pedidos", headers=self.admin_h)
        self.assertEqual(r.json()["total"], 2)

        # cliente logado faz checkout → só ele vê
        cid = self.client.post("/carrinho").json()["cart_id"]
        h = {"X-Cart-Id": cid, **user_h}
        self.client.post("/carrinho/cliente", headers=h,
                         json={"cliente_id": cli["id"]})
        self.client.post("/carrinho/itens", headers=h,
                         json={"produto_codigo": "A1", "quantidade": 1})
        r = self.client.post("/pedidos/checkout", headers=h)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertIsNotNone(r.json()["usuario_id"])           # foi associado

        r = self.client.get("/pedidos", headers=user_h)
        self.assertEqual(r.json()["total"], 1)

        # admin continua vendo os 3
        r = self.client.get("/pedidos", headers=self.admin_h)
        self.assertEqual(r.json()["total"], 3)

    def test_cliente_nao_ve_pedido_alheio(self):
        self._cria_produto("A1", preco=10.0, estoque=100)
        cli = self._cria_cliente()

        # pedido guest (usuario_id=NULL)
        r = self.client.post("/pedidos", json={
            "cliente_id": cli["id"],
            "itens": [{"produto_codigo": "A1", "quantidade": 1}],
        })
        pid = r.json()["id"]

        user_h = self._login_cliente()

        # cliente não vê pedido alheio → 404 (não vaza existência)
        r = self.client.get(f"/pedidos/{pid}", headers=user_h)
        self.assertEqual(r.status_code, 404)

        # admin vê normalmente
        r = self.client.get(f"/pedidos/{pid}", headers=self.admin_h)
        self.assertEqual(r.status_code, 200)

        # cliente não pode cancelar pedido alheio
        r = self.client.post(f"/pedidos/{pid}/cancelar", headers=user_h)
        self.assertEqual(r.status_code, 404)

    # ------- Cap. 8: PDF do pedido -------
    def test_pedido_pdf_admin(self):
        self._cria_produto("A1", preco=10.0, estoque=10)
        cli = self._cria_cliente()
        r = self.client.post("/pedidos", json={
            "cliente_id": cli["id"],
            "itens": [{"produto_codigo": "A1", "quantidade": 2}],
        })
        pid = r.json()["id"]

        r = self.client.get(f"/pedidos/{pid}/pdf", headers=self.admin_h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"),
                        "PDF deve começar com magic bytes %PDF")
        self.assertGreater(len(r.content), 1000,
                           "PDF de teste deve ter conteúdo real")
        self.assertIn("pedido_", r.headers.get("content-disposition", ""))

    def test_pedido_pdf_sem_auth_401(self):
        r = self.client.get("/pedidos/1/pdf")
        self.assertEqual(r.status_code, 401)

    def test_pedido_pdf_de_outro_cliente_404(self):
        self._cria_produto("A1", preco=10.0, estoque=10)
        cli = self._cria_cliente()

        # pedido guest (usuario_id=NULL) - só admin vê
        r = self.client.post("/pedidos", json={
            "cliente_id": cli["id"],
            "itens": [{"produto_codigo": "A1", "quantidade": 1}],
        })
        pid = r.json()["id"]

        # registra e loga um cliente
        self.client.post("/auth/register", json={
            "nome": "Bob", "email": "bob@x.com", "senha": "bob123",
        })
        r = self.client.post("/auth/login", data={
            "username": "bob@x.com", "password": "bob123",
        })
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = self.client.get(f"/pedidos/{pid}/pdf", headers=h)
        self.assertEqual(r.status_code, 404)

        # o dono logado consegue baixar o próprio
        cid = self.client.post("/carrinho").json()["cart_id"]
        h_cart = {"X-Cart-Id": cid, **h}
        self.client.post("/carrinho/cliente", headers=h_cart,
                         json={"cliente_id": cli["id"]})
        self.client.post("/carrinho/itens", headers=h_cart,
                         json={"produto_codigo": "A1", "quantidade": 1})
        r = self.client.post("/pedidos/checkout", headers=h_cart)
        meu_pid = r.json()["id"]

        r = self.client.get(f"/pedidos/{meu_pid}/pdf", headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()