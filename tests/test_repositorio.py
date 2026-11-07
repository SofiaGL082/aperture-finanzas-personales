from datetime import date

import pytest

from core.dominio import Meta, Movimiento, Naturaleza, TipoMovimiento
from core.repositorio import Repositorio
from tests.conftest import mov


def test_migraciones_se_aplican_una_sola_vez(tmp_path):
    ruta = tmp_path / "f.db"
    r1 = Repositorio(ruta)
    r1.crear_usuario("Ana")
    r1.cerrar()
    r2 = Repositorio(ruta)  # abrir de nuevo no debe recrear ni borrar nada
    assert r2.version_esquema == 2
    assert [u.nombre for u in r2.listar_usuarios()] == ["Ana"]


def test_crud_de_movimientos(repo):
    u = repo.crear_usuario("Ana")
    mid = repo.agregar_movimiento(mov(u.id, date(2026, 10, 3), 25_000, "gasto", "restaurantes", "Almuerzo"))
    guardado = repo.listar_movimientos(u.id)[0]
    assert guardado.id == mid and guardado.monto == 2_500_000

    editado = Movimiento(mid, u.id, date(2026, 10, 4), "Almuerzo con equipo", 3_000_000,
                         TipoMovimiento.GASTO, "restaurantes", Naturaleza.VARIABLE)
    repo.actualizar_movimiento(editado)
    assert repo.listar_movimientos(u.id)[0].descripcion == "Almuerzo con equipo"

    repo.eliminar_movimiento(mid, u.id)
    assert repo.listar_movimientos(u.id) == []


def test_un_usuario_no_puede_editar_movimientos_de_otro(repo):
    ana, luis = repo.crear_usuario("Ana"), repo.crear_usuario("Luis")
    mid = repo.agregar_movimiento(mov(ana.id, date(2026, 10, 3), 10_000, "gasto", "transporte"))
    ajeno = Movimiento(mid, luis.id, date(2026, 10, 3), "", 100, TipoMovimiento.GASTO,
                       "transporte", Naturaleza.VARIABLE)
    with pytest.raises(LookupError):
        repo.actualizar_movimiento(ajeno)
    repo.eliminar_movimiento(mid, luis.id)  # no borra nada
    assert len(repo.listar_movimientos(ana.id)) == 1


def test_borrar_usuario_borra_sus_datos(repo):
    u = repo.crear_usuario("Ana")
    repo.agregar_movimiento(mov(u.id, date(2026, 10, 3), 10_000, "gasto", "transporte"))
    repo.guardar_meta(Meta(None, u.id, "Viaje", 100, 0))
    repo.eliminar_usuario(u.id)
    assert repo.listar_movimientos(u.id) == [] and repo.listar_metas(u.id) == []


def test_filtro_por_fechas(repo):
    u = repo.crear_usuario("Ana")
    for d in (date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 1)):
        repo.agregar_movimiento(mov(u.id, d, 1_000, "gasto", "transporte"))
    septiembre = repo.listar_movimientos(u.id, desde=date(2026, 9, 1), hasta=date(2026, 9, 30))
    assert len(septiembre) == 2


def test_validaciones_del_dominio():
    with pytest.raises(ValueError):
        Movimiento(None, 1, date(2026, 1, 1), "", 0, TipoMovimiento.GASTO, "transporte", Naturaleza.VARIABLE)
    with pytest.raises(ValueError):
        Movimiento(None, 1, date(2026, 1, 1), "", 100, TipoMovimiento.GASTO, None, Naturaleza.VARIABLE)
    # transferencias y préstamos no necesitan categoría
    Movimiento(None, 1, date(2026, 1, 1), "", 100, TipoMovimiento.PRESTAMO, None, Naturaleza.VARIABLE)
    with pytest.raises(ValueError):
        Meta(None, 1, "x", 0, 0)


def test_metas(repo):
    u = repo.crear_usuario("Ana")
    mid = repo.guardar_meta(Meta(None, u.id, "Viaje", 260_000_000, 35_000_000, date(2027, 12, 1)))
    repo.guardar_meta(Meta(mid, u.id, "Viaje a Cartagena", 260_000_000, 50_000_000, date(2027, 12, 1)))
    (meta,) = repo.listar_metas(u.id)
    assert meta.nombre == "Viaje a Cartagena" and meta.faltante == 210_000_000
