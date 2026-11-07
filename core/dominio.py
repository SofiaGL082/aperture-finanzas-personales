"""Tipos del dominio de FinTwin.

Este módulo no depende de Streamlit ni de SQLite: describe qué es un
movimiento, una categoría o una meta. El resto del núcleo trabaja con
estos tipos, y la interfaz solo los muestra.

Convención de dinero: todos los montos se guardan como enteros en la
unidad mínima de la moneda (centavos). Nunca se usan floats para dinero,
porque 0.1 + 0.2 != 0.3 y los totales dejarían de cuadrar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from core.monedas import Tasa


class TipoMovimiento(StrEnum):
    INGRESO = "ingreso"
    GASTO = "gasto"
    # Dinero que se mueve entre cuentas de la misma persona
    # (por ejemplo, pagar la tarjeta de crédito desde la cuenta de ahorros).
    # No es ingreso ni gasto: contarlo duplicaría las compras con tarjeta.
    TRANSFERENCIA = "transferencia"
    # Dinero prestado a otra persona o recibido de ella. Se registra para no
    # perderlo de vista, pero no cuenta como ingreso ni como gasto.
    PRESTAMO = "prestamo"

    @property
    def etiqueta(self) -> str:
        return {
            TipoMovimiento.INGRESO: "Ingreso",
            TipoMovimiento.GASTO: "Gasto",
            TipoMovimiento.TRANSFERENCIA: "Transferencia entre mis cuentas",
            TipoMovimiento.PRESTAMO: "Préstamo a o de otra persona",
        }[self]

    @property
    def afecta_ahorro(self) -> bool:
        return self in (TipoMovimiento.INGRESO, TipoMovimiento.GASTO)


class Naturaleza(StrEnum):
    """Con qué regularidad ocurre un movimiento.

    Es distinto de si una categoría es recortable: el arriendo es fijo y
    esencial; una suscripción es fija pero recortable; el mercado varía de
    un mes a otro pero es esencial.
    """

    FIJO = "fijo"
    VARIABLE = "variable"

    @property
    def etiqueta(self) -> str:
        return "Fijo" if self is Naturaleza.FIJO else "Variable"


class Fuente(StrEnum):
    MANUAL = "manual"
    IMPORTADO = "importado"


@dataclass(frozen=True, slots=True)
class Categoria:
    id: str
    nombre: str
    tipo: TipoMovimiento  # INGRESO o GASTO
    recortable: bool  # True si las recomendaciones pueden proponer reducirla
    naturaleza_sugerida: Naturaleza
    descripcion: str = ""


@dataclass(frozen=True, slots=True)
class Usuario:
    id: int
    nombre: str
    moneda: str
    es_demo: bool


@dataclass(frozen=True, slots=True)
class Movimiento:
    id: int | None
    usuario_id: int
    fecha: date
    descripcion: str
    monto: int  # centavos, siempre positivo; el tipo define el sentido
    tipo: TipoMovimiento
    categoria_id: str | None  # None para transferencias y préstamos
    naturaleza: Naturaleza
    cuenta: str = ""
    fuente: Fuente = Fuente.MANUAL

    moneda_original: str | None = None
    monto_original: int | None = None
    tasa_id: int | None = None
    fecha_original: date | None = None
    tasa_documentada: Tasa | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.monto, int) or isinstance(self.monto, bool):
            raise ValueError("El monto debe ser entero en unidades menores.")
        if self.monto_original is not None and (not isinstance(self.monto_original, int) or self.monto_original <= 0):
            raise ValueError("Monto original inválido.")
        if self.monto <= 0:
            raise ValueError("El monto debe ser mayor que cero.")
        if self.tipo.afecta_ahorro and not self.categoria_id:
            raise ValueError("Los ingresos y gastos necesitan una categoría.")


@dataclass(frozen=True, slots=True)
class Meta:
    id: int | None
    usuario_id: int
    nombre: str
    monto_objetivo: int  # centavos
    ahorrado: int  # centavos ya reunidos al crear o actualizar la meta
    fecha_limite: date | None = None

    def __post_init__(self) -> None:
        if self.monto_objetivo <= 0:
            raise ValueError("La meta debe ser mayor que cero.")
        if self.ahorrado < 0:
            raise ValueError("El dinero ahorrado no puede ser negativo.")

    moneda_original: str | None = None
    monto_objetivo_original: int | None = None
    ahorrado_original: int | None = None
    tasa_id: int | None = None
    fecha_valoracion: date | None = None

    @property
    def faltante(self) -> int:
        return max(self.monto_objetivo - self.ahorrado, 0)
