"""Piezas comunes a todos los importadores.

Un importador convierte un archivo externo en movimientos del dominio y
reporta lo que no pudo clasificar, en vez de esconderlo.
"""

from __future__ import annotations

import calendar
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from core.dominio import Movimiento


@dataclass
class ResultadoImportacion:
    movimientos: list[Movimiento] = field(default_factory=list)
    moneda: str = "COP"
    desplazamiento_meses: int = 0
    fuente_moneda: str = ""
    # categoría original -> número de filas enviadas a "Otros"
    sin_mapear: Counter = field(default_factory=Counter)
    descartadas: int = 0  # filas sin fecha o con monto inválido

    @property
    def total(self) -> int:
        return len(self.movimientos)


def desplazar(d: date, meses: int) -> date:
    """Mueve una fecha ``meses`` meses, ajustando el día si el mes es más corto."""
    total = d.year * 12 + (d.month - 1) + meses
    anio, mes = divmod(total, 12)
    mes += 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def meses_para_alinear(ultima_fecha: date, mes_destino: date) -> int:
    """Cuántos meses hay que mover los datos para que su último mes sea ``mes_destino``."""
    return (mes_destino.year - ultima_fecha.year) * 12 + (mes_destino.month - ultima_fecha.month)


def mes_anterior(hoy: date) -> date:
    return desplazar(hoy.replace(day=1), -1)
