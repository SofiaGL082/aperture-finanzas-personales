"""Metas de ahorro: en cuánto tiempo llegas y qué cambiar para llegar antes."""

from decimal import Decimal
import pandas as pd
import streamlit as st

from core import categorias, formato, reportes
from core.dominio import Meta
from core.metas import EstadoMeta, MESES_MINIMOS, estimar
from core.recomendaciones import TOPE_RECORTE, EstadoPlan, planear
from interfaz import estado, graficos, ui, cambio
from core.monedas import MONEDAS_INICIALES, a_menores

usuario = estado.requerir_usuario()
repo, hoy = estado.repo(), estado.hoy()
df = reportes.tabla(repo.listar_movimientos(usuario.id))
metas = repo.listar_metas(usuario.id)

ui.encabezado("Metas de ahorro", "Estimación basada en los movimientos registrados, no en un saldo bancario verificado.")
st.caption("Tener registros en un mes no garantiza que esté completo. Revisa ingresos y gastos omitidos. "
           "Cada meta se evalúa por separado: no se reparte automáticamente el ahorro entre varias metas.")
if aviso := st.session_state.pop("_metas_aviso", None):
    st.toast(aviso, icon=":material/check_circle:")


def formulario_meta(meta: Meta | None = None) -> None:
    """Crear una meta nueva o editar una existente."""
    # Cada formulario (nueva meta y editar meta) puede estar en la misma página:
    # las claves llevan un sufijo para que Streamlit no los confunda.
    sufijo = meta.id if meta else "nueva"
    moneda = st.selectbox("Moneda de la meta", MONEDAS_INICIALES,
                          index=MONEDAS_INICIALES.index(meta.moneda_original if meta else usuario.moneda),
                          key=f"meta_moneda_{sufijo}")
    datos_tasa = cambio.campos(moneda,usuario.moneda,hoy,f"meta_fx_{sufijo}")
    st.caption(f"El plan se calcula en {usuario.moneda}; una meta extranjera fija su equivalente al guardarse. "
               "No garantiza conservar su poder de compra si cambia la tasa.")
    with st.form(f"meta_{sufijo}", clear_on_submit=meta is None, border=False):
        nombre = st.text_input("¿Para qué ahorras?", value=meta.nombre if meta else "",
                               placeholder="Ej.: Viaje a Cartagena", key=f"meta_nombre_{sufijo}")
        c1, c2 = st.columns(2)
        objetivo = c1.text_input(f"¿Cuánto necesitas? ({moneda})",
            value=str(Decimal(meta.monto_objetivo_original)/100) if meta else "",
            placeholder="2600000.00", key=f"meta_objetivo_{sufijo}")
        ahorrado = c2.text_input(f"¿Cuánto tienes ya? ({moneda})",
            value=str(Decimal(meta.ahorrado_original)/100) if meta else "0",
            key=f"meta_ahorrado_{sufijo}")
        limite_actual = meta.fecha_limite if meta else None
        limite = st.date_input("Fecha límite (opcional)", value=limite_actual,
                               min_value=min(hoy, limite_actual) if limite_actual else hoy, format="DD/MM/YYYY",
                               help="Con fecha límite te sugerimos qué recortar para llegar a tiempo.",
                               key=f"meta_limite_{sufijo}")
        if st.form_submit_button("Guardar meta", type="primary", use_container_width=True):
            if not nombre.strip() or not objetivo:
                st.error("Escribe el nombre y el monto de la meta.")
                return
            try:
                repo.guardar_meta(Meta(meta.id if meta else None, usuario.id, nombre.strip(),
                    a_menores(str(objetivo),moneda),a_menores(str(ahorrado or 0),moneda),limite,
                    moneda_original=moneda,tasa_id=cambio.guardar(repo,datos_tasa),fecha_valoracion=hoy))
            except ValueError as exc:
                st.error(str(exc))
                return
            st.session_state["_metas_aviso"] = "Meta guardada."
            st.rerun()


@st.dialog("¿Borrar esta meta?")
def confirmar_borrado(meta: Meta) -> None:
    st.write(f"Se borrará «{meta.nombre}». Tus movimientos no cambian.")
    a, b = st.columns(2)
    if a.button("Sí, borrar", type="primary", use_container_width=True):
        repo.eliminar_meta(meta.id, usuario.id)
        st.session_state["_metas_aviso"] = "Meta borrada."
        st.rerun()
    if b.button("Cancelar", use_container_width=True):
        st.rerun()


if not metas:
    with st.container(border=True):
        st.markdown("#### Crea tu primera meta")
        formulario_meta()
    st.stop()

# --- Selección de meta -----------------------------------------------------------------
sel, nueva = st.columns([3, 1], vertical_alignment="bottom")
meta = sel.selectbox("Meta", metas, format_func=lambda m: m.nombre)
with nueva.popover("Nueva meta", use_container_width=True):
    formulario_meta()

ahorros = reportes.ahorros_mensuales(df, hoy)
declarado = None
if len(ahorros) < MESES_MINIMOS and meta.faltante > 0:
    st.info(
        f"Tienes {len(ahorros)} {'mes anterior con registros' if len(ahorros) == 1 else 'meses anteriores con registros'} "
        f"y se necesitan {MESES_MINIMOS} para estimar el ahorro registrado. Mientras tanto, dinos cuánto "
        "crees que ahorras al mes y te damos una estimación orientativa.",
        icon=":material/info:",
    )
    valor = st.number_input(f"Ahorro mensual aproximado ({usuario.moneda})", min_value=0.0,
                            step=50_000.0, value=None, format="%.0f", placeholder="Ej.: 200000")
    declarado = formato.a_centavos(valor) if valor else None

e = estimar(meta, ahorros, hoy, ahorro_declarado=declarado)

# --- Resultado principal ---------------------------------------------------------------
izq, der = st.columns([3, 2], gap="large")
with izq, st.container(border=True):
    st.progress(min(meta.ahorrado / meta.monto_objetivo, 1.0),
                text=(f"Llevas {ui.dinero(meta.ahorrado, usuario)} de {ui.dinero(meta.monto_objetivo, usuario)}").replace("$", r"\$"))
    if e.estado is EstadoMeta.CUMPLIDA:
        ui.resultado("¡Meta cumplida!", "Ya tienes todo el dinero que necesitabas.")
    elif e.estado is EstadoMeta.SIN_HISTORIAL:
        ui.resultado("Aún no podemos estimarla", "Registra más meses o escribe tu ahorro aproximado arriba.")
    elif e.estado is EstadoMeta.SIN_CAPACIDAD:
        ui.resultado(
            "A este ritmo no llegas",
            f"Normalmente gastas igual o más de lo que ganas (ahorro típico: "
            f"{ui.dinero(e.ahorro_tipico, usuario)} al mes). Revisa las recomendaciones.",
        )
    else:
        ui.resultado(
            f"Llegas en {formato.duracion(e.meses)}",
            f"Hacia {formato.mes_largo(e.fecha_estimada)}, ahorrando {ui.dinero(e.ahorro_tipico, usuario)} "
            f"al mes. " + ("Aporte declarado por ti; no es una predicción." if e.orientativa else "Basado en el historial registrado."),
        )
        if e.rango and e.rango[0] != e.rango[1]:
            bajo, alto = e.rango
            alto_txt = formato.duracion(alto) if alto else "más de 20 años"
            st.caption(f"Si tienes meses buenos o malos como los de tu historial: entre "
                       f"{formato.duracion(bajo)} y {alto_txt}.")
        if e.orientativa:
            st.caption("Estimación orientativa: se basa en el ahorro que escribiste, no en tus registros.")

with der, st.container(border=True):
    st.markdown("#### ¿De dónde sale?")
    if e.ahorro_tipico is not None and not e.orientativa:
        st.write(f"Tu ahorro típico es la mediana de tus últimos {e.meses_usados} meses anteriores con registros: "
                 f"**{ui.dinero(e.ahorro_tipico, usuario)}** al mes.")
    st.write(f"Te faltan **{ui.dinero(e.faltante, usuario)}**.")
    if e.tiene_plazo:
        st.write(f"Tu plazo es {formato.mes_largo(meta.fecha_limite)}: "
                 f"**{formato.duracion(e.meses_disponibles) if e.meses_disponibles else 'ya venció'}**.")
    with st.popover("Editar meta", use_container_width=True):
        formulario_meta(meta)
    if st.button("Borrar meta", icon=":material/delete:", use_container_width=True):
        confirmar_borrado(meta)

# --- Plan para llegar a tiempo -----------------------------------------------------------
gasto_tipico = reportes.gasto_tipico_por_categoria(df, hoy)
plan = None
if e.tiene_plazo and e.estado is not EstadoMeta.CUMPLIDA:
    st.subheader("Cómo llegar a tiempo")
    if e.cumple_plazo:
        st.success(f"Vas bien: a tu ritmo actual llegas antes de {formato.mes_largo(meta.fecha_limite)}. "
                   "No necesitas recortar nada.", icon=":material/check_circle:")
    elif e.estado is EstadoMeta.SIN_HISTORIAL:
        st.caption("Cuando tengamos tu ahorro mensual te diremos qué ajustar.")
    else:
        candidatas = [c.id for c in categorias.recortables() if gasto_tipico.get(c.id, 0) > 0]
        permitidas = st.multiselect(
            "¿Dónde estarías dispuesta o dispuesto a recortar?",
            candidatas,
            default=candidatas,
            format_func=categorias.nombre,
            help="Solo aparecen gastos que se pueden reducir. Vivienda, mercado, transporte, salud, "
                 "educación y deudas nunca se proponen.",
        )
        plan = planear(e, gasto_tipico, permitidas, redondeo=formato.unidad_redondeo(usuario.moneda))

        if e.ahorro_necesario:
            st.write(f"Para llegar a tiempo necesitas ahorrar **{ui.dinero(e.ahorro_necesario, usuario)}** al mes; "
                     f"hoy ahorras {ui.dinero(e.ahorro_tipico, usuario)}.")

        if plan.recortes:
            st.dataframe(
                pd.DataFrame(
                    {
                        "Categoría": [categorias.nombre(r.categoria_id) for r in plan.recortes],
                        "Gastas normalmente": [ui.dinero(r.gasto_tipico, usuario) for r in plan.recortes],
                        "Nuevo tope al mes": [ui.dinero(r.gasto_sugerido, usuario) for r in plan.recortes],
                        "Ahorras": [ui.dinero(r.reduccion, usuario) for r in plan.recortes],
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

        if plan.estado is EstadoPlan.ALCANZABLE:
            st.success(
                f"Recortando cerca del {formato.porcentaje(plan.porcentaje_comun)} en estas categorías ahorrarías "
                f"{ui.dinero(plan.ahorro_con_plan, usuario)} al mes y llegarías en "
                f"{formato.duracion(plan.meses_con_plan)}, a tiempo para tu plazo.",
                icon=":material/check_circle:",
            )
        elif plan.estado is EstadoPlan.INSUFICIENTE:
            if plan.meses_con_plan:
                st.warning(
                    f"Ni recortando el {formato.porcentaje(TOPE_RECORTE)} llegas a tiempo: con estos recortes "
                    f"llegarías en {formato.duracion(plan.meses_con_plan)}. Te faltarían "
                    f"{ui.dinero(plan.deficit_mensual, usuario)} al mes: amplía el plazo, reduce la meta "
                    "o busca un ingreso extra.",
                    icon=":material/warning:",
                )
            else:
                st.warning("El plazo ya venció o no deja meses para ahorrar. Elige una fecha más lejana.",
                           icon=":material/warning:")
        elif plan.estado is EstadoPlan.SIN_CANDIDATAS:
            st.warning("No hay gastos recortables seleccionados. Elige al menos una categoría o amplía el plazo.",
                       icon=":material/warning:")

# --- Proyección --------------------------------------------------------------------------
if e.ahorro_tipico and e.ahorro_tipico > 0 and e.meses:
    st.subheader("Tu ahorro mes a mes")
    con_plan = plan.ahorro_con_plan if plan and plan.recortes else None
    st.plotly_chart(
        graficos.proyeccion_meta(meta.ahorrado, meta.monto_objetivo, e.ahorro_tipico, e.meses, con_plan,
                                 e.meses_disponibles, usuario.moneda, hoy),
        use_container_width=True, config={"displayModeBar": False},
    )
    st.caption("Proyección lineal con tu ahorro típico. Los meses reales subirán y bajarán alrededor de esta línea.")
