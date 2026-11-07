"""Catálogo de categorías de la app.

Un solo lugar define qué categorías existen y cuáles se pueden recortar.
Las recomendaciones de ahorro solo proponen recortes en categorías con
``recortable=True``; vivienda, alimentación, transporte, salud, educación y
deudas nunca se tocan.
"""

from __future__ import annotations

from core.dominio import Categoria, Naturaleza, TipoMovimiento

_I, _G = TipoMovimiento.INGRESO, TipoMovimiento.GASTO
_F, _V = Naturaleza.FIJO, Naturaleza.VARIABLE

CATEGORIAS: tuple[Categoria, ...] = (
    # Ingresos
    Categoria("salario", "Salario", _I, False, _F, "Pago fijo de un empleo"),
    Categoria("ingresos_variables", "Ingresos variables", _I, False, _V,
              "Honorarios, ventas, monitorías, trabajos ocasionales"),
    Categoria("apoyos", "Apoyos y giros familiares", _I, False, _V,
              "Dinero que envían familiares"),
    Categoria("otros_ingresos", "Otros ingresos", _I, False, _V,
              "Reembolsos, intereses, regalos"),
    # Gastos esenciales: nunca se recortan
    Categoria("vivienda", "Vivienda y servicios", _G, False, _F,
              "Arriendo, administración, agua, luz, gas, internet, celular"),
    Categoria("alimentacion", "Alimentación (mercado)", _G, False, _V,
              "Mercado y comida de la casa"),
    Categoria("transporte", "Transporte", _G, False, _V,
              "Bus, metro, gasolina, parqueadero"),
    Categoria("salud", "Salud", _G, False, _V, "EPS, medicamentos, citas"),
    Categoria("educacion", "Educación", _G, False, _F,
              "Matrícula, materiales, cursos"),
    Categoria("deudas", "Cuotas y deudas", _G, False, _F,
              "Cuotas de créditos y tarjetas"),
    # Gastos recortables
    Categoria("restaurantes", "Restaurantes y domicilios", _G, True, _V,
              "Comer fuera, domicilios, cafés"),
    Categoria("entretenimiento", "Entretenimiento", _G, True, _V,
              "Salidas, cine, conciertos, juegos"),
    Categoria("ropa", "Ropa y cuidado personal", _G, True, _V,
              "Ropa, peluquería, cosméticos"),
    Categoria("suscripciones", "Suscripciones", _G, True, _F,
              "Streaming, música, apps, gimnasio"),
    Categoria("compras", "Compras y tecnología", _G, True, _V,
              "Hogar, tecnología, regalos"),
    Categoria("otros_gastos", "Otros gastos", _G, True, _V,
              "Lo que no encaja en otra categoría"),
)

_POR_ID = {c.id: c for c in CATEGORIAS}


def por_id(categoria_id: str) -> Categoria:
    try:
        return _POR_ID[categoria_id]
    except KeyError as exc:
        raise KeyError(f"Categoría desconocida: {categoria_id!r}") from exc


def de_tipo(tipo: TipoMovimiento) -> list[Categoria]:
    return [c for c in CATEGORIAS if c.tipo == tipo]


def recortables() -> list[Categoria]:
    return [c for c in CATEGORIAS if c.recortable]


def nombre(categoria_id: str | None) -> str:
    if categoria_id is None:
        return "—"
    return _POR_ID[categoria_id].nombre if categoria_id in _POR_ID else categoria_id
