"""Piezas visuales reutilizables. Mantienen el mismo tono y aspecto en todas
las páginas: títulos con una línea de contexto, estados vacíos que dicen qué
hacer, y montos siempre con el formato de la moneda del usuario."""

from __future__ import annotations

from html import escape

import streamlit as st

from core import formato
from core.dominio import TipoMovimiento, Usuario

_CSS = """
<style>
:root { --ft-ink:#14213D; --ft-muted:#526079; --ft-accent:#4F46E5; --ft-border:#E2E8F0; }
.stApp { background:#F6F8FC; }
[data-testid="stMainBlockContainer"] { max-width:1440px; padding:2.4rem 2.5rem 4rem; }
[data-testid="stSidebar"] { background:#FFFFFF; border-right:1px solid var(--ft-border); }
[data-testid="stSidebarNav"] a { border-radius:10px; margin:3px 0; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background:#EEF2FF; color:#3730A3; }
h1,h2,h3,h4 { color:var(--ft-ink); letter-spacing:-.025em; }
h1 { font-size:2.15rem !important; font-weight:750 !important; }
[data-testid="stMetric"] { background:white; border:1px solid var(--ft-border); border-radius:16px;
 padding:1.15rem 1.25rem; box-shadow:0 3px 14px rgba(20,33,61,.035); min-height:132px; }
[data-testid="stMetricDelta"] > div { white-space:normal; overflow:visible; text-overflow:clip; font-size:.78rem; }
[data-testid="stMetricLabel"] { color:var(--ft-muted); font-weight:600; }
[data-testid="stMetricValue"] { font-size:1.8rem; font-weight:700; color:var(--ft-ink); font-variant-numeric:tabular-nums; }
[data-testid="stVerticalBlockBorderWrapper"] > div { border-radius:16px; }
.stButton > button, .stFormSubmitButton > button { border-radius:10px; min-height:42px; font-weight:600; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input { font-variant-numeric:tabular-nums; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:#526079 !important; opacity:1 !important; }
.ft-eyebrow { font-size:.72rem; font-weight:750; letter-spacing:.13em; color:#4F46E5; margin-bottom:.3rem; }
.ft-brand { padding:.25rem 0 1rem; color:#14213D; font-weight:800; font-size:1.3rem; letter-spacing:-.04em; }
.ft-brand span { color:#4F46E5; }
.ft-resultado { color:#14213D; font-size:2rem; font-weight:750; line-height:1.2; margin:.5rem 0; }
.ft-sub { color:#526079; line-height:1.6; margin:.5rem 0 1rem; }
.ft-note { background:#EEF2FF; border:1px solid #C7D2FE; border-radius:12px; color:#3730A3;
 padding:.8rem 1rem; margin:.5rem 0 1.25rem; font-size:.88rem; }
button:focus-visible, a:focus-visible, input:focus-visible { outline:3px solid #4F46E5 !important; outline-offset:3px; }
@media(max-width:768px) {
 [data-testid="stMainBlockContainer"] { padding:1.25rem 1rem 3rem; }
 h1 { font-size:1.8rem !important; }
 [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:1rem; }
 [data-testid="stColumn"] { min-width:min(100%,260px); flex:1 1 260px; }
 [data-testid="stMetricValue"] { font-size:1.55rem; }
}
@media(prefers-reduced-motion:reduce) { * { scroll-behavior:auto !important; transition:none !important; } }
</style>
"""


def estilos() -> None:
    st.html(_CSS)


def encabezado(titulo: str, contexto: str | None = None) -> None:
    st.html('<div class="ft-eyebrow">FINTWIN AI · APERTURE 2026-2</div>')
    st.title(titulo)
    if contexto:
        st.caption(contexto)


def estado_vacio(titulo: str, texto: str, pagina: str | None = None, accion: str | None = None,
                 icono: str = ":material/inbox:") -> None:
    with st.container(border=True):
        st.markdown(f"#### {titulo}")
        st.write(texto)
        if pagina and accion:
            st.page_link(pagina, label=accion, icon=icono)


def dinero(centavos: int | None, usuario: Usuario, con_signo: bool = False) -> str:
    return formato.dinero(centavos, usuario.moneda, con_signo=con_signo)


def monto_con_signo(centavos: int, tipo: TipoMovimiento, usuario: Usuario) -> str:
    """'+$50.000' para ingresos, '−$20.000' para gastos y el monto solo para el resto."""
    if tipo is TipoMovimiento.INGRESO:
        return "+" + dinero(centavos, usuario)
    if tipo is TipoMovimiento.GASTO:
        return "−" + dinero(centavos, usuario)
    return dinero(centavos, usuario)


def delta(actual: int, anterior: int | None, usuario: Usuario) -> str | None:
    """Texto para st.metric: diferencia frente al mes anterior."""
    if anterior is None:
        return None
    return f"{dinero(actual - anterior, usuario, con_signo=True)} vs. mes anterior"


def resultado(texto: str, detalle: str | None = None) -> None:
    """Cifra protagonista de una pantalla (p. ej. 'Llegas en 12 meses')."""
    st.html(f'<div class="ft-resultado">{escape(texto)}</div>')
    if detalle:
        st.html(f'<div class="ft-sub">{escape(detalle)}</div>')


PAGINAS = {
    "inicio": "interfaz/paginas/inicio.py",
    "registrar": "interfaz/paginas/registrar.py",
    "historial": "interfaz/paginas/historial.py",
    "reporte": "interfaz/paginas/reporte.py",
    "metas": "interfaz/paginas/metas.py",
}


def nota(texto: str) -> None:
    st.html(f'<div class="ft-note">{escape(texto)}</div>')
