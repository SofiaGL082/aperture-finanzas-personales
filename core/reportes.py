"""Reportes mensuales: totales, comparaciones y gasto típico por categoría.

Funciones puras sobre pandas. Reciben movimientos y devuelven tablas o
resultados; no leen la base de datos ni dibujan nada.

Decisión: un mes sin registros entre dos meses con registros cuenta como
cero. Para un usuario que registra a mano, un mes vacío casi siempre
significa que no anotó, así que la interfaz advierte cuando hay meses vacíos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd

from core.dominio import Movimiento, TipoMovimiento

COLUMNAS = [
    "id", "fecha", "mes", "descripcion", "monto", "tipo",
    "categoria_id", "naturaleza", "cuenta", "fuente",
]

# Una categoría se marca como inusual si supera su mediana en este factor...
FACTOR_ALERTA = 1.25
# ...y la diferencia es al menos este porcentaje del gasto mensual típico total.
PESO_MINIMO_ALERTA = 0.03


def tabla(movimientos: Sequence[Movimiento]) -> pd.DataFrame:
    """Convierte movimientos del dominio en un DataFrame con columna ``mes``."""
    if not movimientos:
        df = pd.DataFrame(columns=COLUMNAS)
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["monto"] = df["monto"].astype("int64")
        df["mes"] = df["fecha"].dt.to_period("M")
        return df
    df = pd.DataFrame(
        {
            "id": [m.id for m in movimientos],
            "fecha": pd.to_datetime([m.fecha for m in movimientos]),
            "descripcion": [m.descripcion for m in movimientos],
            "monto": pd.array([m.monto for m in movimientos], dtype="int64"),
            "tipo": [m.tipo.value for m in movimientos],
            "categoria_id": [m.categoria_id for m in movimientos],
            "naturaleza": [m.naturaleza.value for m in movimientos],
            "cuenta": [m.cuenta for m in movimientos],
            "fuente": [m.fuente.value for m in movimientos],
        }
    )
    df["mes"] = df["fecha"].dt.to_period("M")
    return df[COLUMNAS]


def mes_actual(hoy: date) -> pd.Period:
    return pd.Period(hoy, freq="M")


def ultimo_mes_completo(hoy: date) -> pd.Period:
    return mes_actual(hoy) - 1


def resumen_mensual(df: pd.DataFrame, hasta: pd.Period | None = None) -> pd.DataFrame:
    """Ingresos, gastos y ahorro por mes, desde el primer mes con datos hasta ``hasta``.

    Devuelve un DataFrame indexado por mes (Period) con columnas enteras
    ``ingresos``, ``gastos``, ``ahorro`` y la columna booleana ``sin_registros``.
    """
    columnas = ["ingresos", "gastos", "ahorro", "sin_registros"]
    flujo = df[df["tipo"].isin([TipoMovimiento.INGRESO.value, TipoMovimiento.GASTO.value])]
    if hasta is not None:
        flujo = flujo[flujo["mes"] <= hasta]
    if flujo.empty:
        return pd.DataFrame(columns=columnas, index=pd.PeriodIndex([], freq="M", name="mes"))

    tot = flujo.pivot_table(index="mes", columns="tipo", values="monto", aggfunc="sum", fill_value=0)
    fin = hasta if hasta is not None else tot.index.max()
    meses = pd.period_range(tot.index.min(), fin, freq="M", name="mes")
    tot = tot.reindex(meses, fill_value=0)

    def _col(tipo: TipoMovimiento) -> pd.Series:
        if tipo.value in tot.columns:
            return tot[tipo.value].astype("int64")
        return pd.Series(0, index=meses, dtype="int64")

    res = pd.DataFrame(index=meses)
    res["ingresos"] = _col(TipoMovimiento.INGRESO)
    res["gastos"] = _col(TipoMovimiento.GASTO)
    res["ahorro"] = res["ingresos"] - res["gastos"]
    con_registros = set(flujo["mes"].unique())
    res["sin_registros"] = [m not in con_registros for m in meses]
    return res


def ahorros_mensuales(df: pd.DataFrame, hoy: date) -> list[int]:
    """Ahorro de meses anteriores con registros; no garantiza cobertura completa.

    Excluye el mes en curso y los meses sin registros: desconocido no es cero.
    """
    res = resumen_mensual(df, hasta=ultimo_mes_completo(hoy))
    return [int(v) for v in res.loc[~res["sin_registros"].astype(bool), "ahorro"]]


def gasto_por_categoria(df: pd.DataFrame, hasta: pd.Period | None = None) -> pd.DataFrame:
    """Matriz mes × categoría con el gasto total (ceros donde no hubo gasto)."""
    gastos = df[df["tipo"] == TipoMovimiento.GASTO.value]
    if hasta is not None:
        gastos = gastos[gastos["mes"] <= hasta]
    if gastos.empty:
        return pd.DataFrame(index=pd.PeriodIndex([], freq="M", name="mes"))
    mat = gastos.pivot_table(
        index="mes", columns="categoria_id", values="monto", aggfunc="sum", fill_value=0
    )
    fin = hasta if hasta is not None else mat.index.max()
    meses = pd.period_range(mat.index.min(), fin, freq="M", name="mes")
    return mat.reindex(meses, fill_value=0).astype("int64")


def gasto_tipico_por_categoria(df: pd.DataFrame, hoy: date, ventana: int = 6) -> dict[str, int]:
    """Mediana del gasto mensual de cada categoría en los últimos meses completos."""
    hasta = ultimo_mes_completo(hoy)
    resumen = resumen_mensual(df, hasta=hasta)
    observados = resumen.index[~resumen["sin_registros"].astype(bool)]
    mat = gasto_por_categoria(df, hasta=hasta)
    mat = mat.loc[mat.index.intersection(observados)].tail(ventana)
    if mat.empty:
        return {}
    return {cat: int(round(v)) for cat, v in mat.median().items() if v > 0}


@dataclass(frozen=True)
class ComparacionMes:
    mes: pd.Period
    ingresos: int
    gastos: int
    ahorro: int
    ingresos_anterior: int | None
    gastos_anterior: int | None
    ahorro_anterior: int | None
    por_categoria: pd.DataFrame  # columnas: actual, anterior, mediana_3m, diferencia
    alertas: list[str]  # ids de categoría con gasto inusual

    @property
    def tasa_ahorro(self) -> float | None:
        return self.ahorro / self.ingresos if self.ingresos > 0 else None


def comparar_mes(df: pd.DataFrame, mes: pd.Period) -> ComparacionMes:
    """Compara un mes con el anterior y con la mediana de los 3 meses previos."""
    res = resumen_mensual(df, hasta=mes)
    fila = res.loc[mes] if mes in res.index else None
    anterior = res.loc[mes - 1] if (mes - 1) in res.index else None

    mat = gasto_por_categoria(df, hasta=mes)
    if mat.empty or mes not in mat.index:
        actual = pd.Series(dtype="int64")
    else:
        actual = mat.loc[mes]
    previos = mat.loc[[m for m in mat.index if mes - 3 <= m <= mes - 1]] if not mat.empty else mat
    ant = mat.loc[mes - 1] if (not mat.empty and (mes - 1) in mat.index) else None

    cats = sorted(set(actual[actual > 0].index) | (set(previos.columns) if not previos.empty else set()))
    tabla_cat = pd.DataFrame(index=pd.Index(cats, name="categoria_id"))
    tabla_cat["actual"] = [int(actual.get(c, 0)) for c in cats]
    tabla_cat["anterior"] = [int(ant.get(c, 0)) if ant is not None else None for c in cats]
    tabla_cat["mediana_3m"] = [
        int(round(previos[c].median())) if (not previos.empty and c in previos) else None for c in cats
    ]
    tabla_cat["diferencia"] = [
        a - m if m is not None else None for a, m in zip(tabla_cat["actual"], tabla_cat["mediana_3m"])
    ]
    tabla_cat = tabla_cat[tabla_cat[["actual", "mediana_3m"]].fillna(0).sum(axis=1) > 0]
    tabla_cat = tabla_cat.sort_values("actual", ascending=False)

    alertas: list[str] = []
    if len(previos) >= 2:
        gasto_tipico_total = float(previos.sum(axis=1).median())
        umbral = PESO_MINIMO_ALERTA * gasto_tipico_total
        for cat, r in tabla_cat.iterrows():
            m = r["mediana_3m"]
            if m is not None and r["actual"] > m * FACTOR_ALERTA and r["actual"] - m >= umbral:
                alertas.append(str(cat))

    def _v(serie, col):
        return int(serie[col]) if serie is not None else None

    return ComparacionMes(
        mes=mes,
        ingresos=_v(fila, "ingresos") or 0,
        gastos=_v(fila, "gastos") or 0,
        ahorro=_v(fila, "ahorro") or 0,
        ingresos_anterior=_v(anterior, "ingresos"),
        gastos_anterior=_v(anterior, "gastos"),
        ahorro_anterior=_v(anterior, "ahorro"),
        por_categoria=tabla_cat,
        alertas=alertas,
    )
