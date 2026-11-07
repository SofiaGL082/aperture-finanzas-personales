from datetime import date

import pandas as pd

from core import reportes
from tests.conftest import HOY, mov


def test_resumen_excluye_transferencias_y_rellena_meses_vacios(repo):
    u = repo.crear_usuario("Ana")
    repo.agregar_movimientos([
        mov(u.id, date(2026, 7, 1), 1_000_000, "ingreso", "salario"),
        mov(u.id, date(2026, 7, 5), 600_000, "gasto", "vivienda"),
        mov(u.id, date(2026, 7, 9), 900_000, "transferencia", None),
        mov(u.id, date(2026, 9, 1), 1_000_000, "ingreso", "salario"),
    ])
    res = reportes.resumen_mensual(reportes.tabla(repo.listar_movimientos(u.id)))
    assert list(res.index.astype(str)) == ["2026-07", "2026-08", "2026-09"]
    assert res.loc[pd.Period("2026-07"), "ahorro"] == 40_000_000
    assert res.loc[pd.Period("2026-08"), "ahorro"] == 0
    assert bool(res.loc[pd.Period("2026-08"), "sin_registros"]) is True


def test_ahorros_mensuales_excluye_el_mes_en_curso(repo, usuario_con_historial):
    u = usuario_con_historial
    repo.agregar_movimiento(mov(u.id, date(2026, 11, 2), 50_000, "gasto", "restaurantes"))
    ahorros = reportes.ahorros_mensuales(reportes.tabla(repo.listar_movimientos(u.id)), HOY)
    assert len(ahorros) == 12
    assert set(ahorros) == {40_000_000}  # 3.000.000 − 2.600.000, en centavos


def test_tabla_vacia_no_rompe_nada():
    df = reportes.tabla([])
    assert reportes.resumen_mensual(df).empty
    assert reportes.ahorros_mensuales(df, HOY) == []
    assert reportes.gasto_tipico_por_categoria(df, HOY) == {}
    c = reportes.comparar_mes(df, pd.Period("2026-10"))
    assert c.gastos == 0 and c.alertas == []


def test_comparar_mes_detecta_gasto_inusual(repo, usuario_con_historial):
    u = usuario_con_historial
    repo.agregar_movimiento(mov(u.id, date(2026, 10, 28), 500_000, "gasto", "restaurantes", "Cumpleaños"))
    df = reportes.tabla(repo.listar_movimientos(u.id))
    c = reportes.comparar_mes(df, pd.Period("2026-10"))
    fila = c.por_categoria.loc["restaurantes"]
    assert fila["actual"] == 90_000_000 and fila["mediana_3m"] == 40_000_000
    assert c.alertas == ["restaurantes"]
    assert c.ahorro_anterior == 40_000_000 and c.ahorro == -10_000_000


def test_gasto_tipico_por_categoria(repo, usuario_con_historial):
    df = reportes.tabla(repo.listar_movimientos(usuario_con_historial.id))
    tipico = reportes.gasto_tipico_por_categoria(df, HOY)
    assert tipico["restaurantes"] == 40_000_000 and "salario" not in tipico
