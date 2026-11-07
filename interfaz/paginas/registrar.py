"""Registrar un ingreso, gasto, transferencia o préstamo.

Los campos no están dentro de un st.form a propósito: la lista de categorías
y la sugerencia de fijo/variable cambian en cuanto se elige el tipo o la
categoría, sin tener que enviar el formulario.
"""

import streamlit as st

from core import categorias, formato
from core.dominio import Fuente, Movimiento, Naturaleza, TipoMovimiento
from interfaz import estado, ui, cambio
from core.monedas import MONEDAS_INICIALES, a_menores

usuario = estado.requerir_usuario()
repo, hoy = estado.repo(), estado.hoy()
COP = usuario.moneda == "COP"

ui.encabezado("Registrar", "Registra el movimiento en su moneda original. Revisa los datos antes de guardar.")

ESTADO_INICIAL = {"reg_monto": "", "reg_descripcion": "", "reg_fecha": hoy}
for clave, valor in ESTADO_INICIAL.items():
    st.session_state.setdefault(clave, valor)


def _sugerir_naturaleza() -> None:
    cat = st.session_state.get("reg_categoria")
    if cat:
        st.session_state["reg_naturaleza"] = categorias.por_id(cat).naturaleza_sugerida.value


def _guardar() -> None:
    s = st.session_state
    tipo = TipoMovimiento(s["reg_tipo"])
    if not s.get("reg_monto"):
        s["_reg_error"] = "Escribe un monto mayor que cero."
        return
    try:
        mov = Movimiento(
            id=None,
            usuario_id=usuario.id,
            fecha=s["reg_fecha"],
            descripcion=s.get("reg_descripcion", ""),
            monto=a_menores(str(s["reg_monto"]), s.get("reg_moneda",usuario.moneda)),
            tipo=tipo,
            categoria_id=s.get("reg_categoria") if tipo.afecta_ahorro else None,
            naturaleza=Naturaleza(s.get("reg_naturaleza", "variable")),
            cuenta=s.get("reg_cuenta", ""),
            fuente=Fuente.MANUAL,
            moneda_original=s.get("reg_moneda",usuario.moneda),
            tasa_id=cambio.guardar(repo, datos_tasa),
        )
        repo.agregar_movimiento(mov)
    except ValueError as exc:
        s["_reg_error"] = str(exc)
        return
    s.pop("_reg_error", None)
    s["_reg_ok"] = f"{tipo.etiqueta} guardado; equivalente documentado en {usuario.moneda}."
    # deja listos los campos para el siguiente registro; conserva tipo, fecha y cuenta
    s["reg_monto"], s["reg_descripcion"] = "", ""


formulario, recientes = st.columns([3, 2], gap="large")

with formulario, st.container(border=True):
    st.subheader("Nuevo movimiento")
    tipo = st.radio(
        "¿Qué quieres registrar?",
        [t.value for t in TipoMovimiento],
        format_func=lambda v: TipoMovimiento(v).etiqueta,
        horizontal=True,
        key="reg_tipo",
    )
    tipo = TipoMovimiento(tipo)

    moneda = st.selectbox("Moneda del movimiento", MONEDAS_INICIALES,
                          index=MONEDAS_INICIALES.index(usuario.moneda), key="reg_moneda")
    c1, c2 = st.columns(2)
    c1.text_input(f"Monto ({moneda})", key="reg_monto", placeholder="0.00",
                  help="Usa punto decimal, sin separadores de miles.")
    c2.date_input("Fecha", key="reg_fecha", max_value=hoy, format="DD/MM/YYYY")

    if tipo.afecta_ahorro:
        opciones = categorias.de_tipo(tipo)
        if st.session_state.get("reg_categoria") not in {c.id for c in opciones}:
            st.session_state["reg_categoria"] = opciones[0].id
            _sugerir_naturaleza()
        c3, c4 = st.columns(2)
        c3.selectbox(
            "Categoría",
            [c.id for c in opciones],
            format_func=categorias.nombre,
            key="reg_categoria",
            on_change=_sugerir_naturaleza,
            help=categorias.por_id(st.session_state["reg_categoria"]).descripcion,
        )
        c4.radio(
            "¿Es fijo o variable?",
            [n.value for n in Naturaleza],
            format_func=lambda v: Naturaleza(v).etiqueta,
            horizontal=True,
            key="reg_naturaleza",
            help="Fijo: se repite igual cada mes (arriendo, salario). Variable: cambia de un mes a otro.",
        )
        if tipo is TipoMovimiento.GASTO and not categorias.por_id(st.session_state["reg_categoria"]).recortable:
            st.caption("Esta categoría es esencial: las recomendaciones de ahorro nunca proponen recortarla.")
    elif tipo is TipoMovimiento.TRANSFERENCIA:
        st.caption("Úsalo al mover dinero entre tus cuentas, por ejemplo al pagar la tarjeta de crédito. "
                   "No cuenta como gasto, para no sumar dos veces lo que ya compraste con la tarjeta.")
    else:
        st.caption("Plata que le prestaste a alguien o que te devolvieron. No cuenta como ingreso ni como gasto.")

    datos_tasa = cambio.campos(moneda, usuario.moneda, st.session_state["reg_fecha"], "reg_fx")

    st.text_input("Descripción (opcional)", key="reg_descripcion", placeholder="Ej.: Almuerzo, Netflix, Arriendo")
    st.text_input("Cuenta o medio de pago (opcional)", key="reg_cuenta", placeholder="Ej.: Nequi, Efectivo, Tarjeta")

    st.button("Guardar", type="primary", icon=":material/check:", on_click=_guardar, use_container_width=True)
    if error := st.session_state.get("_reg_error"):
        st.error(error, icon=":material/error:")
    if ok := st.session_state.pop("_reg_ok", None):
        st.success(ok, icon=":material/check_circle:")

with recientes:
    st.markdown("#### Últimos registros")
    ultimos = repo.listar_movimientos(usuario.id)[:8]
    if not ultimos:
        st.caption("Aquí aparecerán tus movimientos.")
    for m in ultimos:
        with st.container(border=True):
            izq, der = st.columns([3, 2])
            izq.markdown(f"**{m.descripcion or categorias.nombre(m.categoria_id)}**")
            izq.caption(f"{formato.fecha_corta(m.fecha)} · {categorias.nombre(m.categoria_id)}"
                        if m.categoria_id else f"{formato.fecha_corta(m.fecha)} · {m.tipo.etiqueta}")
            color = {"ingreso": "green", "gasto": "red"}.get(m.tipo.value, "gray")
            der.markdown(f":{color}[**{ui.monto_con_signo(m.monto, m.tipo, usuario)}**]")
            if m.moneda_original != usuario.moneda:
                st.caption(f"Original: {formato.dinero(m.monto_original,m.moneda_original)} {m.moneda_original}")
    if ultimos:
        st.page_link(ui.PAGINAS["historial"], label="Ver todo el historial", icon=":material/arrow_forward:")
