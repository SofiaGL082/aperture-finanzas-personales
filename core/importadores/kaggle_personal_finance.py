"""Importador del dataset de Kaggle "Personal Finance" (entrepreneurlife).

https://www.kaggle.com/datasets/entrepreneurlife/personal-finance  (licencia MIT)

Columnas esperadas: Date, Description, Amount, Transaction Type, Category,
Account Name, Month. ``Amount`` siempre es positivo; ``Transaction Type``
dice si es debit (gasto) o credit (ingreso o reembolso).

Decisiones:
- "Credit Card Payment" es una TRANSFERENCIA: es pagar desde la cuenta
  corriente compras que ya se registraron con la tarjeta.
- Un crédito en una categoría de gasto (p. ej. una devolución en Shopping)
  se registra como "Otros ingresos" con la palabra "Reembolso".
- Categorías desconocidas van a "Otros gastos" y se listan en el resultado,
  para que el equipo complete el mapeo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from core.monedas import Tasa, a_menores
from pathlib import Path

import pandas as pd

from core import categorias
from core.dominio import Fuente, Movimiento, Naturaleza, TipoMovimiento
from core.formato import a_centavos
from core.importadores.base import ResultadoImportacion, desplazar, meses_para_alinear

MONEDA = None  # La fuente no declara moneda; nunca asumir USD.
COLUMNAS = ["Date", "Description", "Amount", "Transaction Type", "Category", "Account Name"]

# categoría del dataset (en minúsculas) -> categoría de la app
MAPEO_GASTOS: dict[str, str] = {
    "mortgage & rent": "vivienda", "rent": "vivienda", "utilities": "vivienda",
    "internet": "vivienda", "mobile phone": "vivienda",
    "groceries": "alimentacion",
    "restaurants": "restaurantes", "fast food": "restaurantes", "coffee shops": "restaurantes",
    "food & dining": "restaurantes", "dining out": "restaurantes", "alcohol & bars": "restaurantes",
    "gas & fuel": "transporte", "auto insurance": "transporte", "auto & transport": "transporte",
    "public transportation": "transporte", "parking": "transporte",
    "entertainment": "entretenimiento", "amusement": "entretenimiento",
    "movies & dvds": "entretenimiento",
    "music": "suscripciones", "television": "suscripciones", "streaming": "suscripciones",
    "subscriptions": "suscripciones", "gym": "suscripciones",
    "shopping": "compras", "home improvement": "compras", "electronics & software": "compras",
    "gifts": "compras",
    "clothing": "ropa", "haircut": "ropa", "personal care": "ropa",
    "doctor": "salud", "pharmacy": "salud", "health & fitness": "salud", "health": "salud",
    "education": "educacion", "tuition": "educacion",
    "loan": "deudas", "student loan": "deudas", "credit card fees": "deudas",
}
MAPEO_INGRESOS: dict[str, str] = {
    "paycheck": "salario", "salary": "salario", "income": "salario",
    "bonus": "ingresos_variables", "freelance": "ingresos_variables",
    "interest income": "otros_ingresos", "reimbursement": "otros_ingresos",
}
TRANSFERENCIAS = {"credit card payment", "transfer"}


def leer(ruta: str | Path) -> pd.DataFrame:
    ruta = Path(ruta)
    df = pd.read_excel(ruta) if ruta.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(ruta, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Al archivo le faltan las columnas: {', '.join(faltan)}")
    return df


def convertir(df: pd.DataFrame, usuario_id: int, mes_destino: date | None = None,
              *, moneda_verificada: str | None = None, fuente_moneda: str | None = None) -> ResultadoImportacion:
    if not moneda_verificada or not fuente_moneda or not fuente_moneda.strip():
        raise ValueError("La moneda del Excel no está verificada. Indica moneda y fuente antes de importarlo.")
    res = ResultadoImportacion(moneda=moneda_verificada, fuente_moneda=fuente_moneda)
    d = pd.DataFrame(
        {
            "fecha": pd.to_datetime(df["Date"], errors="coerce").dt.date,
            "monto": pd.to_numeric(df["Amount"], errors="coerce"),
            "monto_texto": df["Amount"].astype(str),
            "tipo": df["Transaction Type"].astype("string").fillna("").str.strip().str.lower(),
            "categoria": df["Category"].astype("string").fillna("").str.strip(),
            "descripcion": df["Description"].astype("string").fillna("").str.strip(),
            "cuenta": df["Account Name"].astype("string").fillna("").str.strip(),
        }
    )
    validas = d["fecha"].notna() & (d["monto"] > 0) & d["tipo"].isin(["credit", "debit"])
    res.descartadas = int((~validas).sum())
    d = d[validas]
    if d.empty:
        return res

    if mes_destino is not None:
        res.desplazamiento_meses = meses_para_alinear(max(d["fecha"]), mes_destino)

    for fila in d.to_dict("records"):
        moneda_original = moneda_verificada
        monto_original = a_menores(fila["monto_texto"],moneda_verificada)
        tasa_documentada = None
        cat_original = str(fila["categoria"])
        clave = cat_original.lower()
        es_credito = fila["tipo"] == "credit"
        descripcion = str(fila["descripcion"])

        if clave in TRANSFERENCIAS:
            tipo, categoria = TipoMovimiento.TRANSFERENCIA, None
        elif es_credito:
            tipo = TipoMovimiento.INGRESO
            categoria = MAPEO_INGRESOS.get(clave)
            if categoria is None:
                categoria = "otros_ingresos"
                if clave in MAPEO_GASTOS:
                    descripcion = f"Reembolso: {descripcion}"
                else:
                    res.sin_mapear[cat_original] += 1
        else:
            tipo = TipoMovimiento.GASTO
            categoria = MAPEO_GASTOS.get(clave)
            if categoria is None:
                categoria = "otros_gastos"
                res.sin_mapear[cat_original] += 1

        naturaleza = (
            categorias.por_id(categoria).naturaleza_sugerida if categoria else Naturaleza.VARIABLE
        )
        res.movimientos.append(
            Movimiento(
                id=None,
                usuario_id=usuario_id,
                fecha=desplazar(fila["fecha"], res.desplazamiento_meses),
                descripcion=descripcion,
                monto=monto_original,
                tipo=tipo,
                categoria_id=categoria,
                naturaleza=naturaleza,
                cuenta=str(fila["cuenta"]),
                fuente=Fuente.IMPORTADO,
                fecha_original=fila["fecha"],
                moneda_original=moneda_original,
                monto_original=monto_original,
                tasa_documentada=tasa_documentada,
            )
        )
    return res
