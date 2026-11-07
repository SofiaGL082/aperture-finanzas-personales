from datetime import date

from core.dominio import Meta
from core.metas import estimar
from core.recomendaciones import EstadoPlan, planear
from tests.conftest import HOY

COP = 100_000  # redondeo a $1.000

GASTO = {  # gasto típico mensual en centavos
    "vivienda": 1_200_000_00,
    "alimentacion": 700_000_00,
    "restaurantes": 400_000_00,
    "entretenimiento": 200_000_00,
}


def estimacion(faltante_pesos, ahorro_pesos, limite):
    return estimar(Meta(None, 1, "Meta", faltante_pesos * 100, 0, limite), [ahorro_pesos * 100] * 6, HOY)


def test_reparte_el_mismo_porcentaje_y_no_toca_esenciales():
    # faltan 2.000.000 en 8 meses -> 250.000/mes; ahorra 200.000 -> faltan 50.000/mes
    plan = planear(estimacion(2_000_000, 200_000, date(2027, 7, 1)), GASTO, redondeo=COP)
    assert plan.estado is EstadoPlan.ALCANZABLE
    assert {r.categoria_id for r in plan.recortes} == {"restaurantes", "entretenimiento"}
    assert plan.reduccion_total >= 50_000_00
    porcentajes = [round(r.porcentaje, 2) for r in plan.recortes]
    assert max(porcentajes) - min(porcentajes) <= 0.01  # mismo porcentaje en todas
    assert plan.meses_con_plan <= 8


def test_respeta_las_categorias_que_la_persona_acepta_recortar():
    plan = planear(estimacion(2_000_000, 200_000, date(2027, 7, 1)), GASTO,
                   permitidas=["restaurantes"], redondeo=COP)
    assert [r.categoria_id for r in plan.recortes] == ["restaurantes"]


def test_insuficiente_cuando_ni_con_el_tope_alcanza():
    # faltan 450.000/mes; el tope es 30 % de 600.000 = 180.000
    plan = planear(estimacion(5_000_000, 50_000, date(2027, 7, 1)), GASTO, redondeo=COP)
    assert plan.estado is EstadoPlan.INSUFICIENTE
    assert all(r.porcentaje <= 0.30 for r in plan.recortes)
    assert plan.deficit_mensual > 0 and plan.meses_con_plan > 8


def test_ya_cumple_sin_recortes():
    plan = planear(estimacion(1_000_000, 300_000, date(2027, 7, 1)), GASTO)
    assert plan.estado is EstadoPlan.YA_CUMPLE and plan.recortes == []


def test_sin_plazo_no_hay_plan():
    assert planear(estimacion(1_000_000, 300_000, None), GASTO).estado is EstadoPlan.NO_APLICA


def test_sin_gastos_recortables():
    plan = planear(estimacion(2_000_000, 200_000, date(2027, 7, 1)), {"vivienda": 1_000_000_00})
    assert plan.estado is EstadoPlan.SIN_CANDIDATAS and plan.deficit_mensual == 50_000_00
