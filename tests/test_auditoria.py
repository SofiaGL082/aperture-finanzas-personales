"""Regresiones de la auditoría; sin red ni datos privados."""
from datetime import date
import pytest
from core.dominio import Movimiento, Naturaleza, TipoMovimiento, Meta
from core.metas import meses_para_reunir, estimar
from core import reportes
from tests.conftest import mov


def test_plazo_no_pierde_precision_con_enteros_grandes():
    assert meses_para_reunir(9_007_199_254_740_993, 1) == 9_007_199_254_740_993


def test_aporte_necesario_no_pierde_unidad_menor():
    m = Meta(None, 1, "Prueba exacta", 9_007_199_254_740_993, 0, date(2026, 12, 31))
    e = estimar(m, [], date(2026, 11, 6))
    assert e.ahorro_necesario == m.monto_objetivo


@pytest.mark.parametrize("operacion", ["agregar", "actualizar", "lote"])
def test_repositorio_rechaza_categoria_incompatible(repo, operacion):
    u = repo.crear_usuario("Prueba")
    mid = repo.agregar_movimiento(mov(u.id, date(2026, 10, 1), 10, "gasto", "transporte"))
    invalido = Movimiento(mid, u.id, date(2026, 10, 1), "", 100,
                          TipoMovimiento.GASTO, "salario", Naturaleza.VARIABLE)
    with pytest.raises(ValueError, match="categoría"):
        if operacion == "agregar":
            repo.agregar_movimiento(invalido)
        elif operacion == "actualizar":
            repo.actualizar_movimiento(invalido)
        else:
            repo.agregar_movimientos([invalido])
    assert len(repo.listar_movimientos(u.id)) == 1
    assert repo.listar_movimientos(u.id)[0].categoria_id == "transporte"


def test_meses_ausentes_no_son_ahorro_cero(repo):
    u = repo.crear_usuario("Prueba")
    repo.agregar_movimientos([
        mov(u.id, date(2026, 7, 1), 100, "ingreso", "salario"),
        mov(u.id, date(2026, 9, 1), 200, "ingreso", "salario"),
    ])
    df = reportes.tabla(repo.listar_movimientos(u.id))
    assert reportes.ahorros_mensuales(df, date(2026, 11, 6)) == [10_000, 20_000]


def test_gasto_tipico_no_incluye_meses_ausentes(repo):
    u = repo.crear_usuario("Prueba")
    repo.agregar_movimientos([
        mov(u.id, date(2026, 7, 1), 100, "gasto", "restaurantes"),
        mov(u.id, date(2026, 9, 1), 200, "gasto", "restaurantes"),
    ])
    df = reportes.tabla(repo.listar_movimientos(u.id))
    assert reportes.gasto_tipico_por_categoria(df, date(2026, 11, 6))["restaurantes"] == 15_000
