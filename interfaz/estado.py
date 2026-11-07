"""Estado compartido de la interfaz: conexión a la base y usuario activo.

Las páginas piden aquí el repositorio y el usuario; nunca abren la base
por su cuenta.
"""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from core.config import ruta_base_datos
from core.dominio import Usuario
from core.monedas import MONEDAS_INICIALES
from core.importadores import demo
from core.repositorio import Repositorio

CLAVE_USUARIO = "usuario_id"


@st.cache_resource
def repo() -> Repositorio:
    return Repositorio(ruta_base_datos())


def hoy() -> date:
    """Fecha de referencia. FINTWIN_HOY=AAAA-MM-DD la fija para ensayar la demo."""
    valor = os.environ.get("FINTWIN_HOY")
    return date.fromisoformat(valor) if valor else date.today()


def usuario_actual() -> Usuario | None:
    usuarios = repo().listar_usuarios()
    if not usuarios:
        return None
    ids = [u.id for u in usuarios]
    if st.session_state.get(CLAVE_USUARIO) not in ids:
        st.session_state[CLAVE_USUARIO] = ids[0]
    return next(u for u in usuarios if u.id == st.session_state[CLAVE_USUARIO])


def _crear_usuario() -> None:
    nombre = st.session_state.get("nuevo_usuario_nombre", "").strip()
    if not nombre:
        st.session_state["_aviso_usuario"] = "Escribe un nombre para crear el usuario."
        return
    u = repo().crear_usuario(nombre, st.session_state.get("nuevo_usuario_moneda", "COP"))
    st.session_state[CLAVE_USUARIO] = u.id
    st.session_state["nuevo_usuario_nombre"] = ""
    st.session_state.pop("_aviso_usuario", None)


def formulario_nuevo_usuario() -> None:
    st.text_input("Nombre", key="nuevo_usuario_nombre", placeholder="Ej.: Sofía")
    st.selectbox("Moneda", MONEDAS_INICIALES, key="nuevo_usuario_moneda",
                 help="Los usuarios de demostración usan la moneda de su dataset.")
    st.button("Crear usuario", type="primary", on_click=_crear_usuario, use_container_width=True)
    if aviso := st.session_state.get("_aviso_usuario"):
        st.caption(f":red[{aviso}]")


def cargar_demo() -> None:
    resumenes = demo.cargar(repo(), hoy())
    if resumenes:
        st.session_state[CLAVE_USUARIO] = repo().listar_usuarios()[0].id
        total = sum(r.resultado.total for r in resumenes)
        st.toast(f"Datos de demostración cargados: {total} movimientos.", icon=":material/check_circle:")


def selector_usuario() -> None:
    """Barra lateral: elegir usuario o crear uno nuevo."""
    usuarios = repo().listar_usuarios()
    if not usuarios:  # la bienvenida de requerir_usuario() ya ofrece crear o cargar
        return
    with st.sidebar:
        st.html('<div class="ft-brand">FinTwin<span> AI</span></div>')
        st.caption("TU ESPACIO FINANCIERO")
        if usuarios:
            usuario_actual()  # asegura que la sesión tenga un usuario válido
            st.selectbox(
                "Usuario",
                options=[u.id for u in usuarios],
                format_func=lambda i: next(
                    f"{u.nombre} · {u.moneda}" for u in usuarios if u.id == i
                ),
                key=CLAVE_USUARIO,
            )
        with st.popover("Nuevo usuario", use_container_width=True):
            formulario_nuevo_usuario()
        if demo.archivos_disponibles() and not any(u.es_demo for u in usuarios):
            st.button("Cargar datos de demostración", icon=":material/dataset:",
                      on_click=cargar_demo, use_container_width=True)
        if demo.archivos_disponibles():
            st.caption("El Excel de Personal Finance espera moneda verificada y se conserva para EDA; no se carga como USD.")
        st.caption("Datos guardados en la base local configurada. Los perfiles no son cuentas autenticadas.")


def requerir_usuario() -> Usuario:
    """Devuelve el usuario activo o muestra la bienvenida y detiene la página."""
    u = usuario_actual()
    if u is not None:
        return u
    st.title("Bienvenida a FinTwin")
    st.write(
        "Registra tus ingresos y gastos, mira cómo cambian mes a mes y descubre "
        "en cuánto tiempo llegas a tus metas de ahorro."
    )
    col_nuevo, col_demo = st.columns(2, gap="large")
    with col_nuevo, st.container(border=True):
        st.subheader("Empezar con mis datos")
        formulario_nuevo_usuario()
    with col_demo, st.container(border=True):
        st.subheader("Explorar con datos de ejemplo")
        if demo.archivos_disponibles():
            st.write("Carga los datasets de Kaggle como usuarios de demostración.")
            st.button("Cargar datos de demostración", on_click=cargar_demo, use_container_width=True)
        else:
            st.write("Pon los archivos de Kaggle en `data/demo/` para activar esta opción.")
    st.stop()
