"""Punto de entrada de FinTwin.

    streamlit run app.py

Define la navegación y la barra lateral; cada pantalla vive en interfaz/paginas/.
"""

import streamlit as st

from interfaz import estado, ui

st.set_page_config(page_title="FinTwin AI | Aperture", page_icon="💰", layout="wide")
ui.estilos()

navegacion = st.navigation(
    {
        "": [
            st.Page(ui.PAGINAS["inicio"], title="Inicio", icon=":material/home:", default=True),
        ],
        "Mis movimientos": [
            st.Page(ui.PAGINAS["registrar"], title="Registrar", icon=":material/add_circle:"),
            st.Page(ui.PAGINAS["historial"], title="Historial", icon=":material/receipt_long:"),
        ],
        "Análisis": [
            st.Page(ui.PAGINAS["reporte"], title="Reporte mensual", icon=":material/bar_chart:"),
            st.Page(ui.PAGINAS["metas"], title="Metas de ahorro", icon=":material/savings:"),
        ],
    }
)
estado.selector_usuario()
navegacion.run()
