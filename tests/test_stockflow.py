import os
import shutil
import tempfile
import unittest

from stockflow import database
from stockflow import models
from stockflow.repositories import ProdutoRepo, ClienteRepo
from stockflow.services import (
    VendaService, DescontoService, FreteService, EstoqueService,
)


class TestStockFlow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls._orig = database.DB_NAME
        database.DB_NAME = os.path.join(cls.tmp, "test.db")
        database.inicializar()

    @classmethod
    def tearDownClass(cls):
        database.DB_NAME = cls._orig
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        with database.transacao() as conn:
            conn.execute("DELETE FROM itens_pedido")
            conn.execute("DELETE FROM pedidos")
            conn.execute("DELETE FROM produtos")
            conn.execute("DELETE FROM clientes")

    def _cliente(self, nome="Fulano", cpf="123"):
        cid = ClienteRepo.inserir(models.Cliente(nome, cpf))
        return ClienteRepo.buscar(cid)

    def test_cadastro_e_busca(self):
        ProdutoRepo.inserir(models.Produto("A1", "Caneta", 2.5, 10, 2, "Papelaria"))
        p = ProdutoRepo.buscar("A1")
        self.assertEqual(p.nome, "Caneta")
        self.assertIn(p, ProdutoRepo.buscar_por_nome("Can"))

    def test_venda_baixa_estoque(self):
        ProdutoRepo.inserir(models.Produto("A1", "Caneta", 2.5, 10, 0, "X"))
        c = self._cliente()
        car = models.Carrinho(cliente=c)
        car.adicionar(ProdutoRepo.buscar("A1"), 3)
        ped = VendaService.finalizar(car)
        self.assertEqual(ped.subtotal, 7.5)
        self.assertEqual(ProdutoRepo.buscar("A1").estoque, 7)

    def test_estoque_insuficiente_nao_vaza(self):
        ProdutoRepo.inserir(models.Produto("A1", "Caneta", 2.5, 1, 0, "X"))
        c = self._cliente()
        car = models.Carrinho(cliente=c)
        car.adicionar(ProdutoRepo.buscar("A1"), 5)
        with self.assertRaises(ValueError):
            VendaService.finalizar(car)
        self.assertEqual(ProdutoRepo.buscar("A1").estoque, 1)

    def test_cancelamento_restaura_estoque(self):
        ProdutoRepo.inserir(models.Produto("A1", "Caneta", 2.5, 10, 0, "X"))
        c = self._cliente()
        car = models.Carrinho(cliente=c)
        car.adicionar(ProdutoRepo.buscar("A1"), 4)
        ped = VendaService.finalizar(car)
        self.assertEqual(ProdutoRepo.buscar("A1").estoque, 6)
        VendaService.cancelar(ped.id)
        self.assertEqual(ProdutoRepo.buscar("A1").estoque, 10)

    def test_desconto_por_volume(self):
        ProdutoRepo.inserir(models.Produto("A1", "Caneta", 1.0, 100, 0, "X"))
        car = models.Carrinho()
        car.adicionar(ProdutoRepo.buscar("A1"), 15)
        self.assertEqual(DescontoService.calcular(car), 5.0)

    def test_desconto_por_valor(self):
        ProdutoRepo.inserir(models.Produto("A1", "Notebook", 600.0, 10, 0, "X"))
        car = models.Carrinho()
        car.adicionar(ProdutoRepo.buscar("A1"), 2)  # 1200
        self.assertEqual(DescontoService.calcular(car), 10.0)

    def test_frete_gratis(self):
        ProdutoRepo.inserir(models.Produto("A1", "Notebook", 600.0, 10, 0, "X"))
        car = models.Carrinho()
        car.adicionar(ProdutoRepo.buscar("A1"), 1)
        self.assertEqual(FreteService.calcular(car), 0.0)

    def test_alerta_de_reposicao(self):
        ProdutoRepo.inserir(models.Produto("A1", "X", 1.0, 1, 5, "X"))
        ProdutoRepo.inserir(models.Produto("A2", "Y", 1.0, 10, 5, "X"))
        alertas = EstoqueService.listar_alertas()
        self.assertEqual([a.codigo for a in alertas], ["A1"])

    def test_item_pedido_subtotal_usa_decimal(self):
        from decimal import Decimal
        from stockflow.models import Produto, ItemPedido
        p = Produto("X1", "Item", Decimal("33.33"))
        item = ItemPedido(p, 3, Decimal("33.33"))
        # 33.33 * 3 = 99.99 EXATO em Decimal (em float seria 99.99000000000001)
        self.assertEqual(item.subtotal(), Decimal("99.99"))
        self.assertIsInstance(item.subtotal(), Decimal)

    def test_calcular_total_sem_drift(self):
        from decimal import Decimal
        from stockflow.models import Cliente, Produto, ItemPedido, Pedido

        cli = Cliente(nome="X", cpf="1", id=1)
        p = Produto("X1", "Item", Decimal("0.10"))
        # 10 itens de R$0.10 = R$1.00 EXATO
        itens = [ItemPedido(p, 10, Decimal("0.10"))]
        ped = Pedido(cliente=cli, itens=itens)
        ped.desconto = 0.0
        ped.frete = Decimal("0.00")
        total = ped.calcular_total()
        self.assertEqual(total, Decimal("1.00"))


if __name__ == "__main__":
    unittest.main()
