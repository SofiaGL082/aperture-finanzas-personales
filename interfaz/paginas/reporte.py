"""Reporte mensual: el mes frente al anterior y frente a lo habitual."""

import pandas as pd
import streamlit as st

from core import categorias, formato, reportes
from interfaz import estado, graficos, ui

usuario = estado.requerir_usuario()
repo, hoy = estado.repo(), estado.hoy()
df = reportes.tabla(repo.listar_movimientos(usuario.id))

ui.encabezado("Reporte mensual", "Compara tus registros por periodo y categoría. Los cambios no implican por sí solos un problema financiero.")

resumen = reportes.resumen_mensual(df, hasta=reportes.mes_actual(hoy))
if resumen.empty:
    ui.estado_vacio("Sin datos para el reporte", "Registra ingresos y gastos para ver tu primer reporte.",
                    ui.PAGINAS["registrar"], "Registrar un movimiento", ":material/add_circle:")
    st.stop()

meses = list(resumen.index[::-1])
en_curso = reportes.mes_actual(hoy)


def _etiqueta(p: pd.Period) -> str:
    texto = formato.mes_largo(p.to_timestamp().date()).capitalize()
    return texto + " (en curso)" if p == en_curso else texto


por_defecto = meses.index(en_curso - 1) if (en_curso - 1) in meses else 0
mes = st.selectbox("Mes", meses, index=por_defecto, format_func=_etiqueta)
c = reportes.comparar_mes(df, mes)
if mes == en_curso:
    st.info("El mes todavía no termina. Sus totales son parciales y no son directamente comparables con un mes completo.")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Ingresos", ui.dinero(c.ingresos, usuario), ui.delta(c.ingresos, c.ingresos_anterior, usuario))
k2.metric("Gastos", ui.dinero(c.gastos, usuario), ui.delta(c.gastos, c.gastos_anterior, usuario),
          delta_color="inverse")
k3.metric("Balance del periodo", ui.dinero(c.ahorro, usuario), ui.delta(c.ahorro, c.ahorro_anterior, usuario))
k4.metric("Tasa de ahorro", "—" if c.tasa_ahorro is None else formato.porcentaje(c.tasa_ahorro),
          help="De cada $100 que entraron este mes, cuánto quedó sin gastar.")

# --- Alertas en lenguaje claro --------------------------------------------------------
if c.alertas:
    with st.container(border=True):
        st.markdown("#### Para revisar")
        for cat in c.alertas:
            fila = c.por_categoria.loc[cat]
            st.markdown(
                f"- **{categorias.nombre(cat)}**: gastaste {ui.dinero(int(fila['actual']), usuario)}, "
                f"cuando lo habitual es {ui.dinero(int(fila['mediana_3m']), usuario)} "
                f"({ui.dinero(int(fila['diferencia']), usuario, con_signo=True)})."
            )

# --- Gasto por categoría ----------------------------------------------------------
izq, der = st.columns([3, 2], gap="large")
with izq:
    st.markdown("#### Gasto por categoría")
    if c.por_categoria.empty:
        st.caption("No hay gastos en este mes.")
    else:
        st.plotly_chart(graficos.categorias_vs_habitual(c.por_categoria, usuario.moneda),
                        use_container_width=True, config={"displayModeBar": False})
with der:
    st.markdown("#### Detalle")
    if not c.por_categoria.empty:
        detalle = pd.DataFrame(
            {
                "Categoría": [categorias.nombre(i) for i in c.por_categoria.index],
                "Este mes": [ui.dinero(int(v), usuario) for v in c.por_categoria["actual"]],
                "Habitual": [ui.dinero(None if pd.isna(v) else int(v), usuario)
                             for v in c.por_categoria["mediana_3m"]],
                "Diferencia": [ui.dinero(None if pd.isna(v) else int(v), usuario, con_signo=True)
                               for v in c.por_categoria["diferencia"]],
            }
        )
        st.dataframe(detalle, hide_index=True, use_container_width=True)

# --- Tendencia --------------------------------------------------------------------
st.markdown("#### Últimos 12 meses")
ultimos = resumen[resumen.index <= mes].tail(12)
st.plotly_chart(graficos.tendencia(ultimos, usuario.moneda), use_container_width=True,
                config={"displayModeBar": False})
