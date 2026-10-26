from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from stockflow.models import Usuario
from stockflow.api.deps import get_current_admin
from stockflow.reports import RelatorioService

router = APIRouter(prefix="/relatorios", tags=["relatorios"])


@router.get("/faturamento")
def faturamento(data_inicio: Optional[str] = None,
                data_fim: Optional[str] = None,
                _: Usuario = Depends(get_current_admin)):
    return RelatorioService.faturamento(data_inicio, data_fim)


@router.get("/top-produtos")
def top_produtos(limite: int = 10,
                 _: Usuario = Depends(get_current_admin)):
    return RelatorioService.top_produtos(limite)


@router.get("/historico")
def historico(data_inicio: Optional[str] = None,
              data_fim: Optional[str] = None,
              _: Usuario = Depends(get_current_admin)):
    return [
        {
            "id": p.id, "data": p.data, "status": p.status,
            "cliente": p.cliente.nome if p.cliente else None,
            "subtotal": p.subtotal, "desconto": p.desconto,
            "frete": p.frete, "total": p.total,
        }
        for p in RelatorioService.historico(data_inicio, data_fim)
    ]


@router.get("/exportar-csv")
def exportar_csv(data_inicio: Optional[str] = None,
                 data_fim: Optional[str] = None,
                 _: Usuario = Depends(get_current_admin)):
    content = RelatorioService.gerar_csv(data_inicio, data_fim)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="vendas.csv"'},
    )