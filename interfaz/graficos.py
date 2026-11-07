"""Gráficos de la app (Plotly).

Reglas de estilo, iguales en todos los gráficos:
- Un color de acento para lo que importa y gris para el contexto.
- Montos con separador de miles '.' y decimales ',' (formato colombiano).
- Sin leyendas cuando el título o las etiquetas ya dicen qué es cada cosa.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from core import categorias, formato
from core.metas import sumar_meses

ACENTO = "#4F46E5"  # verde azulado: el dato principal
CONTEXTO = "#94A3B8"  # gris: referencias y comparaciones
POSITIVO = "#15803D"
NEGATIVO = "#B91C1C"
META = "#B45309"


def _base(fig: go.Figure, alto: int = 360) -> go.Figure:
    fig.update_layout(
        height=alto,
        margin=dict(l=8, r=8, t=24, b=8),
        separators=",.",  # decimal ',', miles '.'
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white",font_color="#14213D"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        font=dict(size=13,color="#334155"),
        colorway=["#4F46E5","#0F766E","#0284C7","#9333EA","#D97706","#64748B"],
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,.18)", zeroline=False)
    return fig


def _formato(moneda: str) -> str:
    return ",.0f" if moneda == "COP" else ",.2f"


def _prefijo(moneda: str) -> str:
    return formato.MONEDAS.get(moneda, (moneda + " ", 2))[0]


def categorias_vs_habitual(por_categoria: pd.DataFrame, moneda: str) -> go.Figure:
    """Barras horizontales: gasto del mes (acento) y su habitual (marca gris)."""
    datos = por_categoria.sort_values("actual")
    nombres = [categorias.nombre(c) for c in datos.index]
    actual = datos["actual"] / 100
    habitual = datos["mediana_3m"].astype("float") / 100
    fig = go.Figure()
    fig.add_bar(
        y=nombres, x=actual, orientation="h", name="Este mes", marker_color=ACENTO,
        hovertemplate="%{y}<br>Este mes: " + _prefijo(moneda) + "%{x:" + _formato(moneda) + "}<extra></extra>",
    )
    fig.add_scatter(
        y=nombres, x=habitual, mode="markers", name="Lo habitual (mediana de 3 meses)",
        marker=dict(symbol="line-ns", size=22, line=dict(width=3, color="#4B5563")),
        hovertemplate="%{y}<br>Habitual: " + _prefijo(moneda) + "%{x:" + _formato(moneda) + "}<extra></extra>",
    )
    fig.update_xaxes(tickprefix=_prefijo(moneda), tickformat=_formato(moneda))
    return _base(fig, alto=max(260, 44 * len(nombres) + 80))


def tendencia(resumen: pd.DataFrame, moneda: str) -> go.Figure:
    """Ingresos y gastos por mes (barras) y ahorro (línea)."""
    meses = [formato.mes_corto(p.to_timestamp().date()) for p in resumen.index]
    fig = go.Figure()
    fig.add_bar(x=meses, y=resumen["ingresos"] / 100, name="Ingresos", marker_color=CONTEXTO)
    fig.add_bar(x=meses, y=resumen["gastos"] / 100, name="Gastos", marker_color="#64748B")
    fig.add_scatter(
        x=meses, y=resumen["ahorro"] / 100, name="Ahorro", mode="lines+markers",
        line=dict(color=ACENTO, width=3),
    )
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_yaxes(tickprefix=_prefijo(moneda), tickformat=_formato(moneda))
    fig.update_traces(hovertemplate="%{x}: " + _prefijo(moneda) + "%{y:" + _formato(moneda) + "}<extra>%{fullData.name}</extra>")
    return _base(fig)


def proyeccion_meta(
    ahorrado: int,
    objetivo: int,
    ahorro_actual: int,
    meses: int,
    ahorro_con_plan: int | None,
    meses_plazo: int | None,
    moneda: str,
    hoy,
) -> go.Figure:
    """Ahorro acumulado mes a mes: ritmo actual, ritmo con recortes y la meta."""
    horizonte = min(max(meses, meses_plazo or 0) + 1, 240)
    etiquetas = [formato.mes_corto(sumar_meses(hoy, i)) for i in range(horizonte + 1)]

    def serie(por_mes: int) -> list[float]:
        return [min(ahorrado + por_mes * i, objetivo) / 100 for i in range(horizonte + 1)]

    fig = go.Figure()
    fig.add_scatter(
        x=etiquetas, y=serie(ahorro_actual), name="A tu ritmo actual", mode="lines",
        line=dict(color=CONTEXTO if ahorro_con_plan else ACENTO, width=3),
    )
    if ahorro_con_plan:
        fig.add_scatter(
            x=etiquetas, y=serie(ahorro_con_plan), name="Con los recortes sugeridos", mode="lines",
            line=dict(color=ACENTO, width=3),
        )
    fig.add_hline(y=objetivo / 100, line=dict(color=META, dash="dash"),
                  annotation_text="Meta", annotation_position="top left")
    if meses_plazo:
        fig.add_vline(x=min(meses_plazo, horizonte), line=dict(color="#6B7280", dash="dot"),
                      annotation_text="Plazo", annotation_position="top")
    fig.update_yaxes(tickprefix=_prefijo(moneda), tickformat=_formato(moneda), rangemode="tozero")
    fig.update_traces(hovertemplate="%{x}: " + _prefijo(moneda) + "%{y:" + _formato(moneda) + "}<extra>%{fullData.name}</extra>")
    return _base(fig)



def distribucion(por_categoria: pd.DataFrame, moneda: str) -> go.Figure:
    """Distribución del gasto con etiquetas e importes para no depender del color."""
    datos=por_categoria[por_categoria["actual"]>0].sort_values("actual",ascending=False)
    nombres=[categorias.nombre(c) for c in datos.index]
    montos=[int(v) for v in datos["actual"]]
    fig=go.Figure(go.Pie(labels=nombres,values=montos,hole=.68,sort=False,
        textinfo="percent",textposition="inside",
        customdata=[formato.dinero(v,moneda)+" "+moneda for v in montos],
        hovertemplate="%{label}<br>%{customdata}<br>%{percent}<extra></extra>",
        marker=dict(colors=["#4F46E5","#0F766E","#0284C7","#9333EA","#D97706","#64748B"],line=dict(color="white",width=3))))
    fig.update_layout(legend=dict(orientation="h",y=-.15,x=0),
        annotations=[dict(text="GASTOS",x=.5,y=.5,showarrow=False,font=dict(size=13,color="#526079"))])
    return _base(fig,360).update_layout(legend=dict(orientation="h",y=-.12))
