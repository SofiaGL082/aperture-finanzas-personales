"""Formato de dinero y fechas en español de Colombia.

No depende del locale del sistema (que cambia entre Windows, Mac y la nube),
así que se ve igual en cualquier computador.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

# símbolo y número de decimales que se muestran
MONEDAS: dict[str, tuple[str, int]] = {
    "COP": ("$", 0),
    "USD": ("US$", 2),
    "INR": ("₹", 2),
    "EUR": ("€", 2),
}


def _miles(entero: int) -> str:
    return f"{entero:,}".replace(",", ".")


def dinero(centavos: int | None, moneda: str = "COP", con_signo: bool = False) -> str:
    """``dinero(123456700) -> '$1.234.567'``; ``dinero(-5000, 'USD') -> '-US$50,00'``."""
    if centavos is None:
        return "—"
    simbolo, decimales = MONEDAS.get(moneda.upper(), (moneda.upper() + " ", 2))
    signo = "-" if centavos < 0 else ("+" if con_signo and centavos > 0 else "")
    valor = Decimal(abs(int(centavos))) / 100
    valor = valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    entero = int(valor)
    texto = f"{signo}{simbolo}{_miles(entero)}"
    if decimales:
        fraccion = int((valor - entero) * (10**decimales))
        texto += f",{fraccion:0{decimales}d}"
    return texto


def a_centavos(valor: float | int | str | Decimal) -> int:
    """Convierte un monto en unidades (p. ej. 25000.5) a centavos enteros."""
    return int((Decimal(str(valor)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def a_unidades(centavos: int) -> float:
    return centavos / 100


def unidad_redondeo(moneda: str) -> int:
    """Unidad (en centavos) a la que se redondean recortes sugeridos."""
    return 100_000 if moneda.upper() == "COP" else 100  # $1.000 COP o 1 unidad


def mes_largo(d: date) -> str:
    return f"{MESES[d.month - 1]} de {d.year}"


def mes_corto(d: date) -> str:
    return f"{MESES_CORTOS[d.month - 1]} {d.year}"


def fecha_corta(d: date) -> str:
    return f"{d.day} {MESES_CORTOS[d.month - 1]} {d.year}"


def duracion(meses: int) -> str:
    if meses < 12:
        return f"{meses} {'mes' if meses == 1 else 'meses'}"
    anios, resto = divmod(meses, 12)
    texto = f"{anios} {'año' if anios == 1 else 'años'}"
    return texto + (f" y {resto} {'mes' if resto == 1 else 'meses'}" if resto else "")


def porcentaje(fraccion: float, decimales: int = 0) -> str:
    return f"{fraccion * 100:.{decimales}f} %".replace(".", ",")
