"""Carga los datasets de Kaggle como usuarios de demostración.

Uso, desde la carpeta del proyecto:
    python -m scripts.cargar_demo
    python -m scripts.cargar_demo --db data/fintwin.db --hoy 2026-11-16

Pongan antes los archivos en data/demo/ (ver data/demo/README.md).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from core.config import ruta_base_datos
from core.importadores import demo
from core.repositorio import Repositorio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ruta_base_datos()), help="ruta de la base SQLite")
    parser.add_argument("--hoy", type=date.fromisoformat, default=date.today(),
                        help="fecha de referencia AAAA-MM-DD (por defecto, hoy)")
    parser.add_argument("--carpeta", type=Path, default=demo.CARPETA_DEMO,
                        help="carpeta con los archivos de Kaggle (por defecto, data/demo)")
    args = parser.parse_args(argv)

    if not demo.archivos_disponibles(args.carpeta):
        print(f"No encontré datasets en {args.carpeta}. Lean data/demo/README.md.")
        return 1

    print("Personal Finance: carga suspendida hasta verificar su moneda; el archivo permanece para EDA.")
    repo = Repositorio(args.db)
    for r in demo.cargar(repo, args.hoy, args.carpeta):
        res = r.resultado
        print(f"\n{r.usuario}  <-  {r.archivo}")
        print(f"  {res.total} movimientos en {res.moneda}; fechas movidas {res.desplazamiento_meses} meses")
        if res.descartadas:
            print(f"  {res.descartadas} filas descartadas (sin fecha o sin monto)")
        if res.sin_mapear:
            print("  Categorías sin mapear (quedaron en 'Otros'); agréguenlas al importador:")
            for categoria, n in res.sin_mapear.most_common():
                print(f"    - {categoria or '(vacía)'}: {n}")
    print(f"\nListo. Base de datos: {args.db}")
    repo.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
