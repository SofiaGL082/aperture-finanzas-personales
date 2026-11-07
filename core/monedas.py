"""Dinero exacto y tasas históricas. Las pruebas no necesitan Internet."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, localcontext
import json
from urllib.request import urlopen

# Extensible: añadir metadatos verificados antes de habilitar otra moneda.
EXPONENTES = {"COP": 2, "USD": 2, "EUR": 2, "INR": 2, "JPY": 0, "KWD": 3}
MONEDAS_INICIALES = ("COP", "USD", "EUR", "INR")


def exponente(moneda: str) -> int:
    try:
        return EXPONENTES[moneda.upper()]
    except KeyError as exc:
        raise ValueError(f"Moneda no habilitada: {moneda}") from exc


def decimal_exacto(valor) -> Decimal:
    if isinstance(valor, (float, bool)):
        raise ValueError("Usa texto o Decimal para importes y tasas exactos.")
    try:
        d = Decimal(str(valor))
    except InvalidOperation as exc:
        raise ValueError("Importe o tasa inválidos.") from exc
    if not d.is_finite():
        raise ValueError("El valor debe ser finito.")
    return d


def a_menores(valor, moneda: str) -> int:
    d = decimal_exacto(valor)
    with localcontext() as ctx:
        ctx.prec = 50
        return int((d * (10 ** exponente(moneda))).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def convertir(monto: int, origen: str, destino: str, tasa=None) -> int:
    if not isinstance(monto, int) or isinstance(monto, bool):
        raise ValueError("El monto debe ser entero en unidades menores.")
    exp_origen, exp_destino = exponente(origen), exponente(destino)
    if origen == destino:
        return monto
    if tasa is None:
        raise ValueError(f"Falta tasa histórica {origen}/{destino}.")
    t = decimal_exacto(tasa)
    if t <= 0:
        raise ValueError("La tasa debe ser positiva.")
    with localcontext() as ctx:
        ctx.prec = 50
        return int((Decimal(monto) * t * Decimal(10) ** (exp_destino-exp_origen))
                   .quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Tasa:
    origen: str
    destino: str
    fecha: date
    valor: Decimal
    fuente: str
    consultada_en: str

    def __post_init__(self):
        exponente(self.origen)
        exponente(self.destino)
        if decimal_exacto(self.valor) <= 0 or not self.fuente.strip():
            raise ValueError("Tasa positiva y fuente obligatorias.")


def consultar_frankfurter(origen: str, destino: str, fecha: date) -> Tasa:
    """Solo envía par y fecha, nunca movimientos ni identidad. Sin tasa actual implícita."""
    exponente(origen)
    exponente(destino)
    url = f"https://api.frankfurter.dev/v2/rate/{origen.lower()}/{destino.lower()}?date={fecha.isoformat()}"
    try:
        with urlopen(url, timeout=12) as response:
            data = json.loads(response.read(), parse_float=Decimal)
        referencia = date.fromisoformat(data["date"])
        if data["base"].upper() != origen or data["quote"].upper() != destino:
            raise ValueError("El proveedor devolvió otro par.")
        if not 0 <= (fecha-referencia).days <= 7:
            raise ValueError("No hay una tasa de referencia válida en los siete días anteriores.")
        return Tasa(origen, destino, referencia, decimal_exacto(data["rate"]),
                    "Frankfurter v2 (referencia, no tasa bancaria)",
                    datetime.now(timezone.utc).isoformat())
    except (OSError, KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("No se pudo obtener una tasa histórica válida. Usa una tasa documentada o reintenta.") from exc
