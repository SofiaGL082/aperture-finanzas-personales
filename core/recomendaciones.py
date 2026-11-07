"""¿Qué recortes permiten cumplir una meta dentro del plazo?

Regla, en palabras: se calcula cuánto falta ahorrar cada mes para llegar a
tiempo y se reparte ese faltante entre las categorías recortables que la
persona aceptó recortar, aplicando EL MISMO PORCENTAJE a todas.

¿Por qué el mismo porcentaje? Entre todas las formas de reunir un mismo
monto, recortar igual en proporción es la que hace que el recorte más
grande sea lo más pequeño posible: nadie pierde el 40 % de algo para que
otra categoría quede intacta. Además se explica en una frase.

Límites: ninguna categoría se recorta más de ``TOPE_RECORTE``; las
categorías esenciales (vivienda, mercado, transporte, salud, educación,
deudas) nunca se proponen. Si ni con el tope se alcanza, el plan lo dice y
calcula hasta dónde se llega.
"""

from __future__ import annotations

import math
from decimal import Decimal
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from core import categorias
from core.metas import EstadoMeta, Estimacion, meses_para_reunir

TOPE_RECORTE = 0.30


class EstadoPlan(StrEnum):
    NO_APLICA = "no_aplica"  # sin plazo, meta cumplida o sin historial
    YA_CUMPLE = "ya_cumple"  # con el ahorro actual se llega a tiempo
    ALCANZABLE = "alcanzable"
    INSUFICIENTE = "insuficiente"  # ni con el tope de recorte se llega a tiempo
    SIN_CANDIDATAS = "sin_candidatas"  # no hay gasto recortable que proponer


@dataclass(frozen=True)
class Recorte:
    categoria_id: str
    gasto_tipico: int
    reduccion: int

    @property
    def gasto_sugerido(self) -> int:
        return self.gasto_tipico - self.reduccion

    @property
    def porcentaje(self) -> float:
        return self.reduccion / self.gasto_tipico if self.gasto_tipico else 0.0


@dataclass(frozen=True)
class Plan:
    estado: EstadoPlan
    ahorro_actual: int | None = None
    ahorro_necesario: int | None = None
    recortes: list[Recorte] = field(default_factory=list)
    meses_con_plan: int | None = None
    deficit_mensual: int = 0  # lo que sigue faltando por mes si es INSUFICIENTE

    @property
    def reduccion_total(self) -> int:
        return sum(r.reduccion for r in self.recortes)

    @property
    def ahorro_con_plan(self) -> int | None:
        if self.ahorro_actual is None:
            return None
        return self.ahorro_actual + self.reduccion_total

    @property
    def porcentaje_comun(self) -> float:
        base = sum(r.gasto_tipico for r in self.recortes)
        return self.reduccion_total / base if base else 0.0


def _redondear_arriba(valor: float, unidad: int) -> int:
    return int(math.ceil(valor / unidad) * unidad) if unidad > 1 else int(math.ceil(valor))


def planear(
    estimacion: Estimacion,
    gasto_tipico: Mapping[str, int],
    permitidas: Iterable[str] | None = None,
    tope: float = TOPE_RECORTE,
    redondeo: int = 1,
) -> Plan:
    """Construye el plan de recortes para cumplir el plazo de la meta.

    ``gasto_tipico``: gasto mensual típico por categoría (centavos).
    ``permitidas``: categorías que la persona acepta recortar; por defecto,
    todas las recortables. ``redondeo``: unidad en centavos a la que se
    redondea cada recorte (p. ej. 100_000 = $1.000 COP).
    """
    limite = Decimal(str(tope))
    if not limite.is_finite() or not 0 <= limite <= 1:
        raise ValueError("El tope debe estar entre cero y uno.")
    if not isinstance(redondeo,int) or redondeo < 1:
        raise ValueError("El redondeo debe ser un entero positivo.")
    if (
        not estimacion.tiene_plazo
        or estimacion.estado in (EstadoMeta.CUMPLIDA, EstadoMeta.SIN_HISTORIAL)
        or estimacion.ahorro_tipico is None
    ):
        return Plan(EstadoPlan.NO_APLICA)

    actual = estimacion.ahorro_tipico
    necesario = estimacion.ahorro_necesario
    if necesario is None:  # el plazo ya venció: no hay meses para ahorrar
        return Plan(EstadoPlan.INSUFICIENTE, actual, None, deficit_mensual=estimacion.faltante)

    falta = necesario - actual
    if falta <= 0:
        return Plan(EstadoPlan.YA_CUMPLE, actual, necesario, meses_con_plan=estimacion.meses)

    recortables = {c.id for c in categorias.recortables()}
    elegidas = recortables if permitidas is None else recortables & set(permitidas)
    base = {c: g for c, g in gasto_tipico.items() if c in elegidas and g > 0}
    if not base:
        return Plan(EstadoPlan.SIN_CANDIDATAS, actual, necesario, deficit_mensual=falta)

    total = sum(base.values())
    porcentaje = min(Decimal(falta) / Decimal(total), limite)
    recortes = []
    for cat, g in sorted(base.items(), key=lambda kv: kv[1], reverse=True):
        maximo = int(Decimal(g) * limite)
        reduccion = min(_redondear_arriba(Decimal(g) * porcentaje, redondeo), maximo)
        if reduccion > 0:
            recortes.append(Recorte(cat, g, reduccion))

    reunido = sum(r.reduccion for r in recortes)
    nuevo_ahorro = actual + reunido
    meses = meses_para_reunir(estimacion.faltante, nuevo_ahorro)
    if reunido >= falta:
        return Plan(EstadoPlan.ALCANZABLE, actual, necesario, recortes, meses)
    return Plan(EstadoPlan.INSUFICIENTE, actual, necesario, recortes, meses, falta - reunido)
