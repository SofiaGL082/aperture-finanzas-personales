"""¿En cuántos meses se logra una meta de ahorro?

Cálculo principal (explicable):
    meses = techo( faltante / ahorro mensual típico )
donde el ahorro mensual típico es la MEDIANA del ahorro (ingresos − gastos)
de los últimos meses completos. Se usa la mediana y no el promedio porque un
mes atípico (una prima, una reparación) no la mueve.

Rango (simulación): se repiten miles de futuros posibles tomando al azar
meses del propio historial (bootstrap). En cada futuro se cuenta cuántos
meses tarda en reunirse el faltante. El rango son los percentiles 10 y 90:
"si te van bien o mal los meses, entre X y Y meses".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import numpy as np

from core.dominio import Meta

MESES_MINIMOS = 3  # con menos meses completos la estimación es solo orientativa
VENTANA_MESES = 12  # solo se usan los últimos 12 meses completos
SIMULACIONES = 4000
HORIZONTE_MAXIMO = 240  # 20 años: más allá de eso se informa "más de 20 años"
SEMILLA = 2026  # fija: la misma entrada da siempre el mismo rango


class EstadoMeta(StrEnum):
    CUMPLIDA = "cumplida"
    SIN_HISTORIAL = "sin_historial"  # menos de 3 meses y sin ahorro declarado
    SIN_CAPACIDAD = "sin_capacidad"  # el ahorro típico es cero o negativo
    ESTIMADA = "estimada"


@dataclass(frozen=True)
class Estimacion:
    estado: EstadoMeta
    faltante: int
    meses_usados: int
    ahorro_tipico: int | None = None
    meses: int | None = None
    fecha_estimada: date | None = None  # primer día del mes en que se logra
    rango: tuple[int, int | None] | None = None  # (p10, p90); None arriba = > 20 años
    orientativa: bool = False  # True si se basó en un ahorro declarado
    meses_disponibles: int | None = None  # meses hasta la fecha límite
    ahorro_necesario: int | None = None  # ahorro mensual para cumplir el plazo

    @property
    def tiene_plazo(self) -> bool:
        return self.meses_disponibles is not None

    @property
    def cumple_plazo(self) -> bool | None:
        if not self.tiene_plazo:
            return None
        if self.estado is EstadoMeta.CUMPLIDA:
            return True
        if self.meses is None:
            return False
        return self.meses <= (self.meses_disponibles or 0)


def sumar_meses(d: date, meses: int) -> date:
    """Primer día del mes que está ``meses`` después del mes de ``d``."""
    total = d.year * 12 + (d.month - 1) + meses
    return date(total // 12, total % 12 + 1, 1)


def meses_entre(desde: date, hasta: date) -> int:
    """Meses completos de ahorro entre hoy y la fecha límite (0 si ya pasó).

    Se cuenta por meses de calendario: hoy en noviembre y fecha límite en
    febrero dan 3 meses (diciembre, enero y febrero).
    """
    return max((hasta.year - desde.year) * 12 + (hasta.month - desde.month), 0)


def meses_para_reunir(faltante: int, ahorro_mensual: int) -> int | None:
    if faltante <= 0:
        return 0
    if ahorro_mensual <= 0:
        return None
    return (faltante + ahorro_mensual - 1) // ahorro_mensual


def rango_simulado(
    ahorros: Sequence[int], faltante: int, simulaciones: int = SIMULACIONES, semilla: int = SEMILLA
) -> tuple[int, int | None] | None:
    """Percentiles 10 y 90 de los meses necesarios, remuestreando meses reales."""
    if faltante <= 0 or len(ahorros) < MESES_MINIMOS:
        return None
    rng = np.random.default_rng(semilla)
    muestras = rng.choice(np.asarray(ahorros, dtype=np.int64), size=(simulaciones, HORIZONTE_MAXIMO))
    acumulado = muestras.cumsum(axis=1)
    alcanzo = acumulado >= faltante
    # argmax da el primer True; si nunca llega, se marca más allá del horizonte
    meses = np.where(alcanzo.any(axis=1), alcanzo.argmax(axis=1) + 1, HORIZONTE_MAXIMO + 1)
    p10, p90 = np.percentile(meses, [10, 90], method="nearest")
    if p10 > HORIZONTE_MAXIMO:
        return None
    return int(p10), (int(p90) if p90 <= HORIZONTE_MAXIMO else None)


def estimar(
    meta: Meta,
    ahorros_mensuales: Sequence[int],
    hoy: date,
    ahorro_declarado: int | None = None,
) -> Estimacion:
    """Estima cuándo se logra la meta a partir del ahorro de los meses completos.

    ``ahorros_mensuales`` va del mes más antiguo al más reciente.
    ``ahorro_declarado`` se usa solo si hay menos de ``MESES_MINIMOS`` meses.
    """
    faltante = meta.faltante
    recientes = list(ahorros_mensuales)[-VENTANA_MESES:]

    plazo: dict = {}
    if meta.fecha_limite is not None:
        disponibles = meses_entre(hoy, meta.fecha_limite)
        plazo = {
            "meses_disponibles": disponibles,
            "ahorro_necesario": (faltante + disponibles - 1) // disponibles if disponibles > 0 else None,
        }

    if faltante == 0:
        return Estimacion(EstadoMeta.CUMPLIDA, 0, len(recientes), meses=0, **plazo)

    orientativa = len(recientes) < MESES_MINIMOS
    if orientativa:
        if ahorro_declarado is None:
            return Estimacion(EstadoMeta.SIN_HISTORIAL, faltante, len(recientes), **plazo)
        tipico = int(ahorro_declarado)
    else:
        tipico = int(round(float(np.median(recientes))))

    if tipico <= 0:
        return Estimacion(
            EstadoMeta.SIN_CAPACIDAD, faltante, len(recientes),
            ahorro_tipico=tipico, orientativa=orientativa, **plazo,
        )

    meses = meses_para_reunir(faltante, tipico)
    return Estimacion(
        estado=EstadoMeta.ESTIMADA,
        faltante=faltante,
        meses_usados=len(recientes),
        ahorro_tipico=tipico,
        meses=meses,
        fecha_estimada=sumar_meses(hoy, meses),
        rango=None if orientativa else rango_simulado(recientes, faltante),
        orientativa=orientativa,
        **plazo,
    )
