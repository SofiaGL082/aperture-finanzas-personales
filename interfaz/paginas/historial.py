"""Historial: buscar, corregir y borrar movimientos."""

from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from core import categorias, formato, reportes
from core.dominio import Movimiento, Naturaleza, TipoMovimiento
from interfaz import estado, ui, cambio
from core.monedas import MONEDAS_INICIALES, a_menores

usuario = estado.requerir_usuario()
repo, hoy = estado.repo(), estado.hoy()
movimientos = repo.listar_movimientos(usuario.id)

ui.encabezado("Historial", "Selecciona una fila para corregirla o borrarla.")
if aviso := st.session_state.pop("_historial_aviso", None):
    st.toast(aviso, icon=":material/check_circle:")

if not movimientos:
    ui.estado_vacio("Todavía no hay movimientos", "Cuando registres ingresos y gastos aparecerán aquí.",
                    ui.PAGINAS["registrar"], "Registrar el primero", ":material/add_circle:")
    st.stop()

# --- Filtros ------------------------------------------------------------------
meses = sorted({date(m.fecha.year, m.fecha.month, 1) for m in movimientos}, reverse=True)
f1, f2, f3 = st.columns([1, 1, 2])
mes_sel = f1.selectbox("Mes", [None, *meses], index=1,
                       format_func=lambda d: "Todos" if d is None else formato.mes_largo(d).capitalize())
tipos_sel = f2.multiselect("Tipo", [t.value for t in TipoMovimiento],
                           format_func=lambda v: TipoMovimiento(v).etiqueta, placeholder="Todos")
buscar = f3.text_input("Buscar", placeholder="Descripción, categoría o cuenta")

filtrados = [
    m for m in movimientos
    if (mes_sel is None or (m.fecha.year, m.fecha.month) == (mes_sel.year, mes_sel.month))
    and (not tipos_sel or m.tipo.value in tipos_sel)
    and (not buscar or buscar.lower() in f"{m.descripcion} {categorias.nombre(m.categoria_id)} {m.cuenta}".lower())
]

ingresos = sum(m.monto for m in filtrados if m.tipo is TipoMovimiento.INGRESO)
gastos = sum(m.monto for m in filtrados if m.tipo is TipoMovimiento.GASTO)
k1, k2, k3 = st.columns(3)
k1.metric("Ingresos", ui.dinero(ingresos, usuario))
k2.metric("Gastos", ui.dinero(gastos, usuario))
k3.metric("Movimientos", f"{len(filtrados):,}".replace(",", "."))

# Meses sin ningún registro entre el primero y el último: casi siempre es un olvido
resumen = reportes.resumen_mensual(reportes.tabla(movimientos))
vacios = [p for p, vacio in resumen["sin_registros"].items() if vacio]
if vacios:
    st.warning(
        "No hay registros en " + ", ".join(formato.mes_largo(p.to_timestamp().date()) for p in vacios)
        + ". Esos meses se excluyen de la estimación de metas; falta información.", icon=":material/event_busy:",
    )

if not filtrados:
    st.info("Ningún movimiento coincide con los filtros.")
    st.stop()

tabla = pd.DataFrame(
    {
        "Fecha": [m.fecha for m in filtrados],
        "Descripción": [m.descripcion for m in filtrados],
        "Categoría": [categorias.nombre(m.categoria_id) if m.categoria_id else m.tipo.etiqueta for m in filtrados],
        "Monto": [ui.monto_con_signo(m.monto, m.tipo, usuario) for m in filtrados],
        "Original": [formato.dinero(m.monto_original,m.moneda_original)+" "+m.moneda_original for m in filtrados],
        "Fecha original": [m.fecha_original for m in filtrados],
        "Fijo/variable": [m.naturaleza.etiqueta for m in filtrados],
        "Cuenta": [m.cuenta for m in filtrados],
        "Origen": ["Importado" if m.fuente.value == "importado" else "Manual" for m in filtrados],
    }
)
evento = st.dataframe(
    tabla,
    hide_index=True,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
    key="historial_tabla",
    column_config={
        "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY", width="small"),
        "Monto": st.column_config.TextColumn(width="small"),
        "Descripción": st.column_config.TextColumn(width="large"),
    },
)

filas = evento.selection.rows if evento else []
if not filas:
    st.stop()

# --- Edición del movimiento seleccionado -------------------------------------------
m = filtrados[filas[0]]


@st.dialog("¿Borrar este movimiento?")
def confirmar_borrado(mov: Movimiento) -> None:
    st.write(f"{mov.descripcion or mov.tipo.etiqueta} · {formato.fecha_corta(mov.fecha)} · "
             f"{ui.dinero(mov.monto, usuario)}")
    st.caption("Esta acción no se puede deshacer.")
    a, b = st.columns(2)
    if a.button("Sí, borrar", type="primary", use_container_width=True):
        repo.eliminar_movimiento(mov.id, usuario.id)
        st.session_state["_historial_aviso"] = "Movimiento borrado."
        st.session_state.pop("historial_tabla", None)
        st.rerun()
    if b.button("Cancelar", use_container_width=True):
        st.rerun()


with st.container(border=True):
    st.markdown("#### Corregir movimiento")
    moneda = st.selectbox("Moneda original", MONEDAS_INICIALES,
                          index=MONEDAS_INICIALES.index(m.moneda_original), key=f"hist_moneda_{m.id}")
    datos_tasa = cambio.campos(moneda,usuario.moneda,m.fecha_original or m.fecha,f"hist_fx_{m.id}")
    if m.tasa_id:
        t = repo.obtener_tasa(m.tasa_id)
        st.caption(f"Tasa guardada: {t.valor}; {t.fecha}; {t.fuente}. "
                   "Al editar una operación extranjera confirma o proporciona la tasa nuevamente.")
    with st.form(f"editar_{m.id}"):
        c1, c2, c3 = st.columns(3)
        tipo = TipoMovimiento(c1.selectbox(
            "Tipo", [t.value for t in TipoMovimiento], index=list(TipoMovimiento).index(m.tipo),
            format_func=lambda v: TipoMovimiento(v).etiqueta,
        ))
        monto = c2.text_input(f"Monto original ({moneda})", value=str(Decimal(m.monto_original)/100))
        fecha = c3.date_input("Fecha", value=m.fecha, format="DD/MM/YYYY")
        c4, c5 = st.columns(2)
        todas = [c.id for c in categorias.CATEGORIAS]
        categoria = c4.selectbox(
            "Categoría (solo ingresos y gastos)", todas,
            index=todas.index(m.categoria_id) if m.categoria_id in todas else 0,
            format_func=categorias.nombre,
        )
        naturaleza = c5.radio("Fijo o variable", [n.value for n in Naturaleza], horizontal=True,
                              index=list(Naturaleza).index(m.naturaleza),
                              format_func=lambda v: Naturaleza(v).etiqueta)
        descripcion = st.text_input("Descripción", value=m.descripcion)
        cuenta = st.text_input("Cuenta", value=m.cuenta)
        guardar = st.form_submit_button("Guardar cambios", type="primary")

    if guardar:
        if tipo.afecta_ahorro and categorias.por_id(categoria).tipo is not tipo:
            st.error(f"La categoría «{categorias.nombre(categoria)}» no corresponde a un {tipo.etiqueta.lower()}.")
        else:
            try:
                repo.actualizar_movimiento(Movimiento(
                    m.id, usuario.id, fecha, descripcion, a_menores(str(monto),moneda), tipo,
                    categoria if tipo.afecta_ahorro else None, Naturaleza(naturaleza), cuenta, m.fuente,
                    moneda_original=moneda,tasa_id=cambio.guardar(repo,datos_tasa),
                    fecha_original=fecha if m.fecha_original == m.fecha else m.fecha_original,
                ))
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["_historial_aviso"] = "Cambios guardados."
                st.session_state.pop("historial_tabla", None)
                st.rerun()

    if st.button("Borrar movimiento", icon=":material/delete:"):
        confirmar_borrado(m)
