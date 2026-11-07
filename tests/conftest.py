from __future__ import annotations

from datetime import date

import pytest

from core.dominio import Movimiento, Naturaleza, TipoMovimiento
from core.repositorio import Repositorio

HOY = date(2026, 11, 6)


@pytest.fixture
def repo() -> Repositorio:
    r = Repositorio(":memory:")
    yield r
    r.cerrar()


def mov(usuario_id: int, fecha: date, monto_pesos: int, tipo: str, categoria: str | None,
        descripcion: str = "", naturaleza: Naturaleza = Naturaleza.VARIABLE) -> Movimiento:
    """Atajo para crear movimientos en pesos (se guardan en centavos)."""
    return Movimiento(None, usuario_id, fecha, descripcion, monto_pesos * 100,
                      TipoMovimiento(tipo), categoria, naturaleza)


@pytest.fixture
def usuario_con_historial(repo: Repositorio):
    """12 meses (nov-2025 a oct-2026): salario 3.000.000; ahorro de 400.000 al mes."""
    u = repo.crear_usuario("Ana")
    movs = []
    for i in range(12):
        anio, mes = (2025, 11 + i) if i < 2 else (2026, i - 1)
        movs += [
            mov(u.id, date(anio, mes, 1), 3_000_000, "ingreso", "salario"),
            mov(u.id, date(anio, mes, 3), 1_200_000, "gasto", "vivienda"),
            mov(u.id, date(anio, mes, 8), 700_000, "gasto", "alimentacion"),
            mov(u.id, date(anio, mes, 12), 400_000, "gasto", "restaurantes"),
            mov(u.id, date(anio, mes, 20), 300_000, "gasto", "entretenimiento"),
            mov(u.id, date(anio, mes, 25), 500_000, "transferencia", None, "Pago tarjeta"),
        ]
    repo.agregar_movimientos(movs)
    return u
