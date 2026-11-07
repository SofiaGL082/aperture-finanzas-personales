"""Resumen visual; todos los indicadores se derivan de movimientos guardados."""
import statistics
import pandas as pd
import streamlit as st
from core import categorias, formato, reportes
from core.metas import EstadoMeta, estimar
from interfaz import estado, ui, graficos

usuario = estado.requerir_usuario()
repo, hoy = estado.repo(), estado.hoy()
movimientos = repo.listar_movimientos(usuario.id)
df = reportes.tabla(movimientos)
ui.encabezado(f"Tu dinero, con claridad", f"{usuario.nombre} · Moneda principal: {usuario.moneda} · {formato.fecha_corta(hoy)}")
if usuario.es_demo:
    ui.nota("Perfil de demostración: los registros son históricos y sus fechas pueden haberse desplazado. Consulta la fecha original en el historial; los meses de borde pueden ser parciales.")
if usuario.es_demo and usuario.moneda == "USD":
    st.caption("USD es la moneda asumida para esta demo. El Excel no la declara; falta confirmarla con su fuente.")
if df.empty:
    st.subheader("Tu punto de partida")
    st.write("Registra un ingreso o gasto para comenzar. Puedes crear una meta incluso si todavía no tienes historial.")
    cols=st.columns(3)
    with cols[0]:
        ui.estado_vacio("1. Registra", "Monto, fecha y categoría: lo esencial para empezar.",ui.PAGINAS["registrar"],"Registrar movimiento")
    with cols[1]:
        ui.estado_vacio("2. Comprende", "Consulta tus movimientos y compara periodos.",ui.PAGINAS["historial"],"Ver historial")
    with cols[2]:
        ui.estado_vacio("3. Planea", "Define cuánto quieres ahorrar y para cuándo.",ui.PAGINAS["metas"],"Crear una meta")
    st.stop()

observados=sorted(df.loc[df["fecha"].dt.date <= hoy,"mes"].unique(),reverse=True)
preferido=reportes.ultimo_mes_completo(hoy)
mes=preferido if preferido in observados else (observados[0] if observados else preferido)
c=reportes.comparar_mes(df,mes)
ahorros=reportes.ahorros_mensuales(df,hoy)
tipico=int(statistics.median(ahorros[-12:])) if ahorros else None
st.subheader(formato.mes_largo(mes.to_timestamp().date()).capitalize())
k1,k2,k3,k4=st.columns(4)
k1.metric("Ingresos del periodo",ui.dinero(c.ingresos,usuario),ui.delta(c.ingresos,c.ingresos_anterior,usuario))
k2.metric("Gastos del periodo",ui.dinero(c.gastos,usuario),ui.delta(c.gastos,c.gastos_anterior,usuario),delta_color="inverse")
k3.metric("Balance del periodo",ui.dinero(c.ahorro,usuario),help="Ingresos menos gastos registrados; no es el saldo de una cuenta bancaria.")
k4.metric("Ahorro mensual típico",ui.dinero(tipico,usuario),help="Mediana de hasta 12 meses anteriores con registros. No garantiza que esos meses estén completos.")
st.caption(f"Todos los indicadores están expresados en {usuario.moneda}. Los movimientos extranjeros usan la tasa documentada al registrarse.")
if mes==reportes.mes_actual(hoy):
    st.info("Este periodo está en curso. Sus totales todavía son parciales.")

izq,der=st.columns([1.6,1],gap="large")
with izq,st.container(border=True):
    st.subheader("Cómo se mueve tu dinero")
    resumen=reportes.resumen_mensual(df,hasta=mes).tail(12)
    st.plotly_chart(graficos.tendencia(resumen,usuario.moneda),use_container_width=True,config={"displayModeBar":False})
    st.page_link(ui.PAGINAS["reporte"],label="Explorar reporte mensual",icon=":material/arrow_forward:")
with der,st.container(border=True):
    st.subheader("Dónde gastaste")
    if c.por_categoria.empty:
        st.caption("No hay gastos registrados en este periodo.")
    else:
        st.plotly_chart(graficos.distribucion(c.por_categoria,usuario.moneda),use_container_width=True,config={"displayModeBar":False})

st.subheader("Metas que te mueven")
metas=repo.listar_metas(usuario.id)
if not metas:
    ui.estado_vacio("Dale un destino a tu ahorro", "Crea tu primera meta y explora un plazo orientativo.",ui.PAGINAS["metas"],"Crear meta",":material/savings:")
else:
    columnas=st.columns(min(len(metas),3))
    for i,meta in enumerate(metas):
        e=estimar(meta,ahorros,hoy)
        with columnas[i%len(columnas)],st.container(border=True):
            st.markdown(f"**{meta.nombre}**")
            st.progress(min(meta.ahorrado/meta.monto_objetivo,1.0),text=(f"{ui.dinero(meta.ahorrado,usuario)} de {ui.dinero(meta.monto_objetivo,usuario)}").replace("$",r"\$"))
            if e.estado is EstadoMeta.ESTIMADA:
                st.write(f"Plazo orientativo: **{formato.duracion(e.meses)}**.")
            elif e.estado is EstadoMeta.CUMPLIDA:
                st.success("Meta alcanzada")
            else:
                st.caption("Abre la meta para revisar los datos necesarios y las alternativas.")
    st.page_link(ui.PAGINAS["metas"],label="Gestionar metas",icon=":material/savings:")

with st.container(border=True):
    st.subheader("Actividad reciente")
    recientes=movimientos[:6]
    st.dataframe(pd.DataFrame({
        "Fecha":[m.fecha for m in recientes],
        "Concepto":[m.descripcion or categorias.nombre(m.categoria_id) for m in recientes],
        "Tipo":[m.tipo.etiqueta for m in recientes],
        f"Equivalente ({usuario.moneda})":[ui.dinero(m.monto,usuario) for m in recientes],
        "Moneda original":[m.moneda_original for m in recientes],
    }),hide_index=True,use_container_width=True)
    st.page_link(ui.PAGINAS["historial"],label="Ver todos los movimientos",icon=":material/receipt_long:")
