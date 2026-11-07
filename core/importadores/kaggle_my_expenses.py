"""Importador del dataset de Kaggle "My expenses data" (tharunprabu).

https://www.kaggle.com/datasets/tharunprabu/my-expenses-data  (licencia CC0)

Archivo ``expense_data_1.csv``. Columnas útiles: Date ("3/2/2022 10:11",
mes primero), Account, Category, Note, Amount, Income/Expense. Moneda: INR.
Es de un estudiante durante unos 3 meses.

Decisiones (el dataset mezcla conceptos dentro de "Other"):
- "Food" es en su mayoría comer fuera (Lunch, KFC, Pizza): va a
  "Restaurantes y domicilios", salvo notas de mercado (eggs, milk...), que
  van a "Alimentación".
- Giros de familiares ("From dad") son "Apoyos y giros familiares".
- "From <nombre>" en Other es un préstamo que le devuelven, y
  "To <nombre>" o "lended" es un préstamo que hizo: tipo PRÉSTAMO.
- "Took from ..." es sacar plata de otra cuenta propia: TRANSFERENCIA.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from core.monedas import Tasa, a_menores
from pathlib import Path

import pandas as pd

from core import categorias
from core.dominio import Fuente, Movimiento, Naturaleza, TipoMovimiento
from core.formato import a_centavos
from core.importadores.base import ResultadoImportacion, desplazar, meses_para_alinear

MONEDA = "INR"
COLUMNAS = ["Date", "Category", "Amount", "Income/Expense"]

MAPEO_GASTOS = {
    "food": "restaurantes", "transportation": "transporte", "household": "compras",
    "apparel": "ropa", "beauty": "ropa", "social life": "entretenimiento",
    "health": "salud", "education": "educacion", "self-development": "educacion",
    "gift": "compras", "culture": "entretenimiento",
}
MAPEO_INGRESOS = {"salary": "salario", "allowance": "apoyos", "petty cash": "otros_ingresos"}
PALABRAS_MERCADO = re.compile(r"\b(eggs?|milk|vegetables?|groceries|rice|bread|fruits?)\b", re.I)
PALABRAS_FAMILIA = re.compile(r"\b(dad|mom|amma|appa|father|mother)\b", re.I)


def leer(ruta: str | Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Al archivo le faltan las columnas: {', '.join(faltan)}")
    return df


def _clasificar(categoria: str, nota: str, es_ingreso: bool) -> tuple[TipoMovimiento, str | None, bool]:
    """Devuelve (tipo, categoría de la app, se_mapeo)."""
    clave, nota_l = categoria.lower(), nota.lower()
    if nota_l.startswith("took from"):
        return TipoMovimiento.TRANSFERENCIA, None, True
    if es_ingreso:
        if PALABRAS_FAMILIA.search(nota):
            return TipoMovimiento.INGRESO, "apoyos", True
        if clave == "other" and nota_l.startswith("from "):
            return TipoMovimiento.PRESTAMO, None, True
        if clave in MAPEO_INGRESOS:
            return TipoMovimiento.INGRESO, MAPEO_INGRESOS[clave], True
        return TipoMovimiento.INGRESO, "otros_ingresos", clave == "other"
    if clave == "other" and (nota_l.startswith("to ") or "lend" in nota_l):
        return TipoMovimiento.PRESTAMO, None, True
    if clave == "food" and PALABRAS_MERCADO.search(nota):
        return TipoMovimiento.GASTO, "alimentacion", True
    if clave in MAPEO_GASTOS:
        return TipoMovimiento.GASTO, MAPEO_GASTOS[clave], True
    return TipoMovimiento.GASTO, "otros_gastos", clave == "other"


def convertir(df: pd.DataFrame, usuario_id: int, mes_destino: date | None = None) -> ResultadoImportacion:
    res = ResultadoImportacion(moneda=MONEDA)
    nota = df["Note"] if "Note" in df.columns else pd.Series("", index=df.index)
    d = pd.DataFrame(
        {
            "fecha": pd.to_datetime(df["Date"], format="%m/%d/%Y %H:%M", errors="coerce").dt.date,
            "monto": pd.to_numeric(df["Amount"], errors="coerce"),
            "monto_texto": df["Amount"].astype(str),
            "moneda": (df["Currency"] if "Currency" in df.columns else pd.Series(MONEDA,index=df.index)).fillna(MONEDA).astype(str).str.upper(),
            "equivalente_inr": (df["INR"] if "INR" in df.columns else pd.Series("",index=df.index)).astype(str),
            "sentido": df["Income/Expense"].astype("string").fillna("").str.strip().str.lower(),
            "categoria": df["Category"].astype("string").fillna("").str.strip(),
            "nota": nota.astype("string").fillna("").str.strip(),
            "cuenta": (df["Account"] if "Account" in df.columns else pd.Series("", index=df.index))
            .astype("string").fillna("").str.strip(),
        }
    )
    validas = d["fecha"].notna() & (d["monto"] > 0) & d["sentido"].isin(["income", "expense"])
    res.descartadas = int((~validas).sum())
    d = d[validas]
    if d.empty:
        return res
    if mes_destino is not None:
        res.desplazamiento_meses = meses_para_alinear(max(d["fecha"]), mes_destino)

    for fila in d.to_dict("records"):
        moneda_original = fila["moneda"]
        monto_original = a_menores(fila["monto_texto"],moneda_original)
        tasa_documentada = None
        if moneda_original != MONEDA:
            try:
                equivalente = Decimal(fila["equivalente_inr"])
                original = Decimal(fila["monto_texto"])
                if not equivalente.is_finite() or equivalente <= 0:
                    raise ValueError("Equivalente inválido")
                tasa_documentada = Tasa(moneda_original,MONEDA,fila["fecha"],equivalente/original,
                    "Tipo implícito documentado en columnas INR/Amount del dataset", "no disponible en origen")
            except Exception as exc:
                raise ValueError("Fila extranjera sin equivalente INR documentado; no se puede importar.") from exc
        tipo, categoria, mapeado = _clasificar(fila["categoria"], fila["nota"], fila["sentido"] == "income")
        if not mapeado:
            res.sin_mapear[fila["categoria"]] += 1
        res.movimientos.append(
            Movimiento(
                id=None,
                usuario_id=usuario_id,
                fecha=desplazar(fila["fecha"], res.desplazamiento_meses),
                descripcion=fila["nota"] or fila["categoria"],
                monto=monto_original,
                tipo=tipo,
                categoria_id=categoria,
                naturaleza=(
                    categorias.por_id(categoria).naturaleza_sugerida if categoria else Naturaleza.VARIABLE
                ),
                cuenta=fila["cuenta"],
                fuente=Fuente.IMPORTADO,
                fecha_original=fila["fecha"],
                moneda_original=moneda_original,
                monto_original=monto_original,
                tasa_documentada=tasa_documentada,
            )
        )
    return res
