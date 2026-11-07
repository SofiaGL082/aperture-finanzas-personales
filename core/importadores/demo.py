"""Carga los usuarios de demostración desde los datasets de Kaggle.

Busca en ``data/demo/``:
- ``personal_transactions*.xlsx`` (o .csv)  -> "Demo · Hogar con salario"
- ``expense_data*.csv``                     -> "Demo · Estudiante"

Mueve las fechas de cada dataset para que su último mes sea el mes anterior
al actual. Así los reportes "frente al mes anterior" tienen sentido junto a
los registros nuevos. Cargar dos veces reemplaza los usuarios demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from core.importadores import kaggle_my_expenses, kaggle_personal_finance
from core.importadores.base import ResultadoImportacion, mes_anterior
from core.repositorio import Repositorio

CARPETA_DEMO = Path(__file__).resolve().parents[2] / "data" / "demo"

_FUENTES = (
    ("Demo · Hogar con salario", ("personal_transactions*.xlsx", "personal_transactions*.csv"),
     kaggle_personal_finance),
    ("Demo · Estudiante", ("expense_data*.csv",), kaggle_my_expenses),
)


@dataclass(frozen=True)
class ResumenCarga:
    usuario: str
    archivo: str
    resultado: ResultadoImportacion


def archivos_disponibles(carpeta: Path | None = None) -> dict[str, Path]:
    carpeta = carpeta or CARPETA_DEMO
    encontrados: dict[str, Path] = {}
    for nombre, patrones, _ in _FUENTES:
        for patron in patrones:
            coincidencias = sorted(carpeta.rglob(patron))
            if coincidencias:
                encontrados[nombre] = coincidencias[0]
                break
    return encontrados


def cargar(repo: Repositorio, hoy: date, carpeta: Path | None = None,
           monedas_verificadas: dict[str, tuple[str, str]] | None = None) -> list[ResumenCarga]:
    disponibles = archivos_disponibles(carpeta)
    destino = mes_anterior(hoy)
    resumenes: list[ResumenCarga] = []
    existentes = {u.nombre: u for u in repo.listar_usuarios() if u.es_demo}

    for nombre, _, modulo in _FUENTES:
        ruta = disponibles.get(nombre)
        if ruta is None:
            continue
        confirmacion = (monedas_verificadas or {}).get(nombre)
        if modulo.MONEDA is None and confirmacion is None:
            # El original permanece disponible para EDA/staging, sin asumir USD.
            continue
        moneda = confirmacion[0] if confirmacion else modulo.MONEDA
        opciones = ({"moneda_verificada":moneda,"fuente_moneda":confirmacion[1]}
                    if modulo.MONEDA is None else {})
        df = modulo.leer(ruta)  # valida columnas antes de tocar la base
        # Cada perfil se reemplaza como una unidad; un error conserva el anterior.
        from dataclasses import replace
        resultado = modulo.convertir(df, 0, mes_destino=destino, **opciones)
        with repo.unidad_trabajo():
            if nombre in existentes:
                repo.eliminar_usuario(existentes[nombre].id)
            usuario = repo.crear_usuario(nombre, moneda=moneda, es_demo=True)
            resultado.movimientos = [replace(m,usuario_id=usuario.id) for m in resultado.movimientos]
            repo.agregar_movimientos(resultado.movimientos)
        resumenes.append(ResumenCarga(nombre, ruta.name, resultado))
    return resumenes
