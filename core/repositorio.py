"""Acceso a la base de datos SQLite.

Toda la lectura y escritura en la base pasa por ``Repositorio``. La interfaz
nunca escribe SQL. Si más adelante migran a PostgreSQL, solo cambia este
archivo.

El esquema se versiona con ``PRAGMA user_version``: cada cambio de esquema
se agrega al final de ``_MIGRACIONES`` y se aplica solo una vez en cada base.
Nunca editen una migración que ya se aplicó; agreguen una nueva.
"""

from __future__ import annotations

import sqlite3
from threading import RLock
from dataclasses import replace
from decimal import Decimal
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from core.monedas import Tasa, convertir, exponente
from core.categorias import CATEGORIAS, por_id
from core.dominio import Fuente, Meta, Movimiento, Naturaleza, TipoMovimiento, Usuario

_MIGRACIONES: tuple[str, ...] = (
    # v1: esquema inicial
    """
    CREATE TABLE usuarios (
        id          INTEGER PRIMARY KEY,
        nombre      TEXT NOT NULL,
        moneda      TEXT NOT NULL DEFAULT 'COP',
        es_demo     INTEGER NOT NULL DEFAULT 0 CHECK (es_demo IN (0, 1)),
        creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE categorias (
        id          TEXT PRIMARY KEY,
        nombre      TEXT NOT NULL,
        tipo        TEXT NOT NULL CHECK (tipo IN ('ingreso', 'gasto')),
        recortable  INTEGER NOT NULL CHECK (recortable IN (0, 1))
    );

    CREATE TABLE movimientos (
        id            INTEGER PRIMARY KEY,
        usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        fecha         TEXT NOT NULL,                      -- AAAA-MM-DD
        descripcion   TEXT NOT NULL DEFAULT '',
        monto         INTEGER NOT NULL CHECK (monto > 0),  -- centavos
        tipo          TEXT NOT NULL
                      CHECK (tipo IN ('ingreso', 'gasto', 'transferencia', 'prestamo')),
        categoria_id  TEXT REFERENCES categorias(id),
        naturaleza    TEXT NOT NULL CHECK (naturaleza IN ('fijo', 'variable')),
        cuenta        TEXT NOT NULL DEFAULT '',
        fuente        TEXT NOT NULL CHECK (fuente IN ('manual', 'importado')),
        creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
        CHECK (tipo NOT IN ('ingreso', 'gasto') OR categoria_id IS NOT NULL)
    );
    CREATE INDEX ix_movimientos_usuario_fecha ON movimientos (usuario_id, fecha);

    CREATE TABLE metas (
        id              INTEGER PRIMARY KEY,
        usuario_id      INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        nombre          TEXT NOT NULL,
        monto_objetivo  INTEGER NOT NULL CHECK (monto_objetivo > 0),
        ahorrado        INTEGER NOT NULL DEFAULT 0 CHECK (ahorrado >= 0),
        fecha_limite    TEXT,
        creada_en       TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    # v2: preservar originales y tasas; v1 permanece intacta.
    """
    CREATE TABLE tasas_cambio (
        id INTEGER PRIMARY KEY,
        origen TEXT NOT NULL,
        destino TEXT NOT NULL,
        fecha TEXT NOT NULL,
        valor TEXT NOT NULL,
        fuente TEXT NOT NULL,
        consultada_en TEXT NOT NULL
    );
    ALTER TABLE movimientos ADD COLUMN moneda_original TEXT;
    ALTER TABLE movimientos ADD COLUMN monto_original INTEGER;
    ALTER TABLE movimientos ADD COLUMN tasa_id INTEGER REFERENCES tasas_cambio(id);
    ALTER TABLE movimientos ADD COLUMN fecha_original TEXT;
    UPDATE movimientos SET monto_original=monto,
      moneda_original=(SELECT moneda FROM usuarios WHERE usuarios.id=movimientos.usuario_id),
      fecha_original=fecha;
    ALTER TABLE metas ADD COLUMN moneda_original TEXT;
    ALTER TABLE metas ADD COLUMN monto_objetivo_original INTEGER;
    ALTER TABLE metas ADD COLUMN ahorrado_original INTEGER;
    ALTER TABLE metas ADD COLUMN tasa_id INTEGER REFERENCES tasas_cambio(id);
    ALTER TABLE metas ADD COLUMN fecha_valoracion TEXT;
    UPDATE metas SET monto_objetivo_original=monto_objetivo, ahorrado_original=ahorrado,
      moneda_original=(SELECT moneda FROM usuarios WHERE usuarios.id=metas.usuario_id);
    """,
)


class Repositorio:
    def __init__(self, ruta: str | Path = ":memory:") -> None:
        if ruta != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: Streamlit atiende cada interacción en un hilo
        # distinto; las escrituras van dentro de transacciones cortas.
        self._bloqueo = RLock()
        self._profundidad_transaccion = 0
        self._con = sqlite3.connect(str(ruta), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._migrar()
        self._sembrar_categorias()

    # ------------------------------------------------------------------ infra
    @contextmanager
    def _transaccion(self) -> Iterator[sqlite3.Connection]:
        with self._bloqueo:
            if self._profundidad_transaccion:
                yield self._con
            else:
                with self._con:
                    self._profundidad_transaccion += 1
                    try:
                        yield self._con
                    finally:
                        self._profundidad_transaccion -= 1

    @contextmanager
    def unidad_trabajo(self):
        """Agrupa cambios relacionados; un fallo revierte todo el bloque."""
        with self._transaccion():
            yield self

    def _migrar(self) -> None:
        version = self._con.execute("PRAGMA user_version").fetchone()[0]
        for numero, sql in enumerate(_MIGRACIONES[version:], start=version + 1):
            try:
                self._con.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {numero};\nCOMMIT;")
            except Exception:
                self._con.rollback()
                raise

    def _sembrar_categorias(self) -> None:
        with self._transaccion() as con:
            con.executemany(
                """INSERT INTO categorias (id, nombre, tipo, recortable)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     nombre = excluded.nombre, recortable = excluded.recortable""",
                [(c.id, c.nombre, c.tipo.value, int(c.recortable)) for c in CATEGORIAS],
            )

    @property
    def version_esquema(self) -> int:
        return self._con.execute("PRAGMA user_version").fetchone()[0]

    def cerrar(self) -> None:
        self._con.close()

    # --------------------------------------------------------------- usuarios
    def crear_usuario(self, nombre: str, moneda: str = "COP", es_demo: bool = False) -> Usuario:
        exponente(moneda.upper())
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío.")
        with self._transaccion() as con:
            cur = con.execute(
                "INSERT INTO usuarios (nombre, moneda, es_demo) VALUES (?, ?, ?)",
                (nombre, moneda.upper(), int(es_demo)),
            )
        return Usuario(cur.lastrowid, nombre, moneda.upper(), es_demo)

    def listar_usuarios(self) -> list[Usuario]:
        filas = self._con.execute(
            "SELECT id, nombre, moneda, es_demo FROM usuarios ORDER BY es_demo, nombre"
        ).fetchall()
        return [Usuario(f["id"], f["nombre"], f["moneda"], bool(f["es_demo"])) for f in filas]

    def obtener_usuario(self, usuario_id: int) -> Usuario | None:
        f = self._con.execute(
            "SELECT id, nombre, moneda, es_demo FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        return Usuario(f["id"], f["nombre"], f["moneda"], bool(f["es_demo"])) if f else None

    def eliminar_usuario(self, usuario_id: int) -> None:
        with self._transaccion() as con:
            con.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))

    # ------------------------------------------------------------ movimientos
    @staticmethod
    def _validar_movimiento(m: Movimiento) -> None:
        if m.tipo.afecta_ahorro:
            try:
                categoria = por_id(m.categoria_id)
            except KeyError as exc:
                raise ValueError("La categoría no existe.") from exc
            if categoria.tipo != m.tipo:
                raise ValueError("La categoría no corresponde al tipo de movimiento.")
        elif m.categoria_id is not None:
            raise ValueError("Transferencias y préstamos no deben tener categoría de ingreso o gasto.")

    def guardar_tasa(self, tasa: Tasa) -> int:
        with self._transaccion() as con:
            cur = con.execute(
                "INSERT INTO tasas_cambio (origen,destino,fecha,valor,fuente,consultada_en) VALUES (?,?,?,?,?,?)",
                (tasa.origen,tasa.destino,tasa.fecha.isoformat(),str(tasa.valor),tasa.fuente,tasa.consultada_en))
        return cur.lastrowid

    def obtener_tasa(self, tasa_id: int) -> Tasa:
        f = self._con.execute("SELECT * FROM tasas_cambio WHERE id=?", (tasa_id,)).fetchone()
        if f is None:
            raise ValueError("La tasa no existe.")
        return Tasa(f["origen"],f["destino"],date.fromisoformat(f["fecha"]),Decimal(f["valor"]),
                    f["fuente"],f["consultada_en"])

    def _convertir_original(self, usuario_id, monto, moneda, tasa_id, fecha):
        usuario = self.obtener_usuario(usuario_id)
        if usuario is None:
            raise ValueError("El usuario no existe.")
        moneda = moneda or usuario.moneda
        if moneda == usuario.moneda:
            return convertir(monto, moneda, usuario.moneda)
        if tasa_id is None or fecha is None:
            raise ValueError("Falta una tasa histórica documentada.")
        tasa = self.obtener_tasa(tasa_id)
        if (tasa.origen,tasa.destino) != (moneda,usuario.moneda):
            raise ValueError("La tasa no corresponde al par de monedas.")
        if not 0 <= (fecha-tasa.fecha).days <= 7:
            raise ValueError("La tasa debe corresponder a la fecha o a los siete días anteriores.")
        return convertir(monto,moneda,usuario.moneda,tasa.valor)

    def normalizar_movimiento(self, m: Movimiento) -> Movimiento:
        self._validar_movimiento(m)
        usuario = self.obtener_usuario(m.usuario_id)
        if usuario is None:
            raise ValueError("El usuario no existe.")
        if m.tasa_documentada is not None and m.tasa_id is None:
            m = replace(m,tasa_id=self.guardar_tasa(m.tasa_documentada),tasa_documentada=None)
        original = m.monto_original if m.monto_original is not None else m.monto
        moneda = m.moneda_original or usuario.moneda
        monto = self._convertir_original(m.usuario_id,original,moneda,m.tasa_id,m.fecha_original or m.fecha)
        return replace(m,monto=monto,monto_original=original,moneda_original=moneda,
                       fecha_original=m.fecha_original or m.fecha)

    def _fila_movimiento(self, m: Movimiento) -> tuple:
        m = self.normalizar_movimiento(m)
        Repositorio._validar_movimiento(m)
        return (
            m.usuario_id, m.fecha.isoformat(), m.descripcion.strip(), m.monto,
            m.tipo.value, m.categoria_id, m.naturaleza.value, m.cuenta.strip(), m.fuente.value,
            m.moneda_original, m.monto_original, m.tasa_id, m.fecha_original.isoformat(),
        )

    def agregar_movimiento(self, m: Movimiento) -> int:
        with self._transaccion() as con:
            cur = con.execute(
                """INSERT INTO movimientos
                   (usuario_id, fecha, descripcion, monto, tipo, categoria_id,
                    naturaleza, cuenta, fuente, moneda_original, monto_original, tasa_id, fecha_original)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._fila_movimiento(m),
            )
        return cur.lastrowid

    def agregar_movimientos(self, movimientos: Iterable[Movimiento]) -> int:
        with self._transaccion() as con:
            filas = [self._fila_movimiento(m) for m in movimientos]
            con.executemany(
                """INSERT INTO movimientos
                   (usuario_id, fecha, descripcion, monto, tipo, categoria_id,
                    naturaleza, cuenta, fuente, moneda_original, monto_original, tasa_id, fecha_original)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                filas,
            )
        return len(filas)

    def actualizar_movimiento(self, m: Movimiento) -> None:
        m = self.normalizar_movimiento(m)
        if m.id is None:
            raise ValueError("Para actualizar un movimiento se necesita su id.")
        with self._transaccion() as con:
            cur = con.execute(
                """UPDATE movimientos SET
                     fecha = ?, descripcion = ?, monto = ?, tipo = ?, categoria_id = ?,
                     naturaleza = ?, cuenta = ?, moneda_original = ?, monto_original = ?, tasa_id = ?, fecha_original = ?
                   WHERE id = ? AND usuario_id = ?""",
                (m.fecha.isoformat(), m.descripcion.strip(), m.monto, m.tipo.value,
                 m.categoria_id, m.naturaleza.value, m.cuenta.strip(), m.moneda_original, m.monto_original,
                 m.tasa_id, m.fecha_original.isoformat(), m.id, m.usuario_id),
            )
            if cur.rowcount == 0:
                raise LookupError("El movimiento no existe o pertenece a otro usuario.")

    def eliminar_movimiento(self, movimiento_id: int, usuario_id: int) -> None:
        with self._transaccion() as con:
            con.execute(
                "DELETE FROM movimientos WHERE id = ? AND usuario_id = ?",
                (movimiento_id, usuario_id),
            )

    def eliminar_importados(self, usuario_id: int) -> int:
        with self._transaccion() as con:
            cur = con.execute(
                "DELETE FROM movimientos WHERE usuario_id = ? AND fuente = 'importado'",
                (usuario_id,),
            )
        return cur.rowcount

    def listar_movimientos(
        self, usuario_id: int, desde: date | None = None, hasta: date | None = None
    ) -> list[Movimiento]:
        sql = "SELECT * FROM movimientos WHERE usuario_id = ?"
        params: list = [usuario_id]
        if desde:
            sql += " AND fecha >= ?"
            params.append(desde.isoformat())
        if hasta:
            sql += " AND fecha <= ?"
            params.append(hasta.isoformat())
        sql += " ORDER BY fecha DESC, id DESC"
        return [
            Movimiento(
                id=f["id"], usuario_id=f["usuario_id"], fecha=date.fromisoformat(f["fecha"]),
                descripcion=f["descripcion"], monto=f["monto"], tipo=TipoMovimiento(f["tipo"]),
                categoria_id=f["categoria_id"], naturaleza=Naturaleza(f["naturaleza"]),
                cuenta=f["cuenta"], fuente=Fuente(f["fuente"]),
                moneda_original=f["moneda_original"], monto_original=f["monto_original"], tasa_id=f["tasa_id"],
                fecha_original=date.fromisoformat(f["fecha_original"]) if f["fecha_original"] else None,
            )
            for f in self._con.execute(sql, params).fetchall()
        ]

    # ------------------------------------------------------------------ metas
    def guardar_meta(self, meta: Meta) -> int:
        usuario = self.obtener_usuario(meta.usuario_id)
        if usuario is None:
            raise ValueError("El usuario no existe.")
        moneda = meta.moneda_original or usuario.moneda
        objetivo = meta.monto_objetivo_original if meta.monto_objetivo_original is not None else meta.monto_objetivo
        ahorrado = meta.ahorrado_original if meta.ahorrado_original is not None else meta.ahorrado
        objetivo_base = self._convertir_original(meta.usuario_id,objetivo,moneda,meta.tasa_id,meta.fecha_valoracion)
        ahorrado_base = self._convertir_original(meta.usuario_id,ahorrado,moneda,meta.tasa_id,meta.fecha_valoracion)
        valores = (
            meta.nombre.strip(), objetivo_base, ahorrado_base,
            meta.fecha_limite.isoformat() if meta.fecha_limite else None,
            moneda, objetivo, ahorrado, meta.tasa_id,
            meta.fecha_valoracion.isoformat() if meta.fecha_valoracion else None,
        )
        with self._transaccion() as con:
            if meta.id is None:
                cur = con.execute(
                    """INSERT INTO metas (nombre, monto_objetivo, ahorrado, fecha_limite, moneda_original,
                       monto_objetivo_original, ahorrado_original, tasa_id, fecha_valoracion, usuario_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (*valores, meta.usuario_id),
                )
                return cur.lastrowid
            con.execute(
                """UPDATE metas SET nombre = ?, monto_objetivo = ?, ahorrado = ?, fecha_limite = ?, moneda_original = ?, monto_objetivo_original = ?,
                   ahorrado_original = ?, tasa_id = ?, fecha_valoracion = ?
                   WHERE id = ? AND usuario_id = ?""",
                (*valores, meta.id, meta.usuario_id),
            )
            return meta.id

    def listar_metas(self, usuario_id: int) -> list[Meta]:
        filas = self._con.execute(
            "SELECT * FROM metas WHERE usuario_id = ? ORDER BY creada_en, id", (usuario_id,)
        ).fetchall()
        return [
            Meta(
                id=f["id"], usuario_id=f["usuario_id"], nombre=f["nombre"],
                monto_objetivo=f["monto_objetivo"], ahorrado=f["ahorrado"],
                fecha_limite=date.fromisoformat(f["fecha_limite"]) if f["fecha_limite"] else None,
                moneda_original=f["moneda_original"], monto_objetivo_original=f["monto_objetivo_original"],
                ahorrado_original=f["ahorrado_original"], tasa_id=f["tasa_id"],
                fecha_valoracion=date.fromisoformat(f["fecha_valoracion"]) if f["fecha_valoracion"] else None,
            )
            for f in filas
        ]

    def eliminar_meta(self, meta_id: int, usuario_id: int) -> None:
        with self._transaccion() as con:
            con.execute("DELETE FROM metas WHERE id = ? AND usuario_id = ?", (meta_id, usuario_id))


def crear_base_preparacion(ruta, filas):
    """Base separada de staging; creación exclusiva, nunca reemplaza la operativa."""
    ruta=Path(ruta)
    ruta.parent.mkdir(parents=True,exist_ok=True)
    with ruta.open('xb'):
        pass
    con=sqlite3.connect(ruta)
    try:
        con.execute('''CREATE TABLE transacciones_preparadas (
          transaction_uid TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, profile_ref TEXT NOT NULL,
          source_file TEXT NOT NULL, source_sha256 TEXT NOT NULL, source_row INTEGER NOT NULL,
          original_date TEXT, demo_date TEXT, original_type TEXT, movement_type TEXT,
          special_movement TEXT, category_original TEXT, category_normalized TEXT, description TEXT,
          account_ref TEXT, original_amount_decimal TEXT, original_amount_minor INTEGER, original_currency TEXT,
          amount_cop_minor INTEGER, fx_rate_decimal TEXT, fx_reference_date TEXT, fx_requested_date TEXT,
          fx_source TEXT, fx_retrieved_at TEXT, fx_response_sha256 TEXT, conversion_status TEXT,
          source_equivalent_inr_decimal TEXT, include_in_consumption INTEGER, needs_review INTEGER, review_reasons TEXT
        )''')
        columns=list(filas[0]) if filas else []
        if columns:
            placeholders=','.join('?' for _ in columns)
            # Nombres de columna proceden del esquema interno, no del archivo importado.
            con.executemany('INSERT INTO transacciones_preparadas ('+','.join(columns)+') VALUES ('+placeholders+')',
                            [tuple(row[c] for c in columns) for row in filas])
        con.commit()
        count=con.execute('SELECT COUNT(*) FROM transacciones_preparadas').fetchone()[0]
        if count!=len(filas):raise ValueError('No se conservaron todas las filas.')
    finally:
        con.close()
    return count
