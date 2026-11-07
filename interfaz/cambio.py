"""Captura explícita de tasas; ninguna consulta de red ocurre al abrir la pantalla."""
from datetime import datetime, timezone
import streamlit as st
from core.monedas import Tasa, decimal_exacto, consultar_frankfurter


def campos(origen, destino, fecha, prefijo, consultar=True):
    if origen == destino:
        return None
    st.caption(f"Conversión: 1 {origen} en {destino}. Sin tasa no se puede guardar el equivalente.")
    if consultar and st.button("Consultar tasa histórica de referencia", key=prefijo+"_buscar"):
        try:
            tasa = consultar_frankfurter(origen,destino,fecha)
            st.session_state[prefijo+"_valor"] = str(tasa.valor)
            st.session_state[prefijo+"_fuente"] = tasa.fuente
            st.session_state[prefijo+"_fecha"] = tasa.fecha
        except ValueError as exc:
            st.error(str(exc))
    valor = st.text_input("Tasa (usa punto decimal)",key=prefijo+"_valor")
    fuente = st.text_input("Fuente de la tasa",key=prefijo+"_fuente",
                           help="Ej.: comprobante bancario. Las tasas ficticias deben identificarse como tales.")
    referencia = st.date_input("Fecha de referencia de la tasa", value=fecha, max_value=fecha,
                               key=prefijo+"_fecha")
    return (origen,destino,referencia,valor,fuente)


def guardar(repo, datos):
    if datos is None:
        return None
    origen,destino,fecha,valor,fuente = datos
    return repo.guardar_tasa(Tasa(origen,destino,fecha,decimal_exacto(valor),fuente,
                                 datetime.now(timezone.utc).isoformat()))
