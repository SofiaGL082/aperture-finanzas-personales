from datetime import date

from core.dominio import Meta
from core.metas import EstadoMeta, estimar, meses_entre, rango_simulado, sumar_meses
from tests.conftest import HOY


def meta(objetivo, ahorrado=0, limite=None):
    return Meta(None, 1, "Meta", objetivo * 100, ahorrado * 100, limite)


def test_ejemplo_del_prototipo_del_equipo():
    # Meta $2.600.000, ya ahorrado $350.000, ahorro real de $200.000 al mes
    e = estimar(meta(2_600_000, 350_000), [200_000_00] * 6, HOY)
    assert e.estado is EstadoMeta.ESTIMADA
    assert e.faltante == 225_000_000
    assert e.meses == 12  # 11,25 meses se redondea hacia arriba
    assert e.fecha_estimada == date(2027, 11, 1)


def test_usa_la_mediana_y_no_el_promedio():
    # un mes con prima no debe acortar la estimación
    ahorros = [100_000_00, 100_000_00, 100_000_00, 100_000_00, 2_000_000_00]
    e = estimar(meta(1_000_000), ahorros, HOY)
    assert e.ahorro_tipico == 100_000_00 and e.meses == 10


def test_meta_cumplida():
    e = estimar(meta(1_000_000, 1_200_000), [], HOY)
    assert e.estado is EstadoMeta.CUMPLIDA and e.meses == 0


def test_sin_historial_y_con_ahorro_declarado():
    assert estimar(meta(1_000_000), [50_000_00], HOY).estado is EstadoMeta.SIN_HISTORIAL
    e = estimar(meta(1_000_000), [50_000_00], HOY, ahorro_declarado=250_000_00)
    assert e.estado is EstadoMeta.ESTIMADA and e.orientativa and e.meses == 4 and e.rango is None


def test_sin_capacidad_de_ahorro():
    e = estimar(meta(1_000_000), [-10_000_00, 0, 5_000_00, -2_000_00], HOY)
    assert e.estado is EstadoMeta.SIN_CAPACIDAD and e.meses is None


def test_plazo_y_ahorro_necesario():
    e = estimar(meta(1_200_000, 300_000, date(2027, 5, 31)), [160_000_00] * 6, HOY)
    assert e.meses_disponibles == 6  # dic, ene, feb, mar, abr, may
    assert e.ahorro_necesario == 150_000_00
    assert e.meses == 6 and e.cumple_plazo is True


def test_plazo_vencido():
    e = estimar(meta(1_000_000, 0, date(2026, 10, 1)), [100_000_00] * 6, HOY)
    assert e.meses_disponibles == 0 and e.ahorro_necesario is None and e.cumple_plazo is False


def test_rango_es_reproducible_y_contiene_la_estimacion():
    ahorros = [300_000_00, 50_000_00, 250_000_00, 180_000_00, 220_000_00, 120_000_00]
    e = estimar(meta(2_000_000), ahorros, HOY)
    assert e.rango == rango_simulado(ahorros, e.faltante)  # misma semilla, mismo resultado
    bajo, alto = e.rango
    assert bajo <= e.meses <= alto


def test_ahorro_siempre_igual_da_rango_exacto():
    assert rango_simulado([100_000_00] * 6, 1_000_000_00) == (10, 10)


def test_fechas():
    assert sumar_meses(date(2026, 11, 6), 2) == date(2027, 1, 1)
    assert meses_entre(date(2026, 11, 6), date(2027, 2, 1)) == 3
