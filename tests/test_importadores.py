from collections import Counter
from datetime import date
from pathlib import Path

from core.dominio import Fuente, TipoMovimiento
from core.formato import a_centavos, dinero, duracion
from core.importadores import demo, kaggle_my_expenses, kaggle_personal_finance
from core.importadores.base import desplazar

DATOS = Path(__file__).parent / "datos"


def test_personal_finance():
    df = kaggle_personal_finance.leer(DATOS / "personal_transactions_muestra.csv")
    res = kaggle_personal_finance.convertir(df, usuario_id=1, mes_destino=date(2026, 10, 1),
        moneda_verificada="USD", fuente_moneda="FICTICIA: fixture de prueba, no dataset real")
    assert res.descartadas == 1  # la fila sin fecha
    assert res.desplazamiento_meses == 82  # dic-2019 -> oct-2026
    tipos = Counter(m.tipo for m in res.movimientos)
    assert tipos[TipoMovimiento.TRANSFERENCIA] == 2  # pagos de tarjeta, en ambas cuentas
    por_desc = {m.descripcion: m for m in res.movimientos}
    assert por_desc["Biweekly Paycheck"].categoria_id == "salario"
    assert por_desc["Netflix"].categoria_id == "suscripciones"
    assert por_desc["Reembolso: Amazon"].tipo is TipoMovimiento.INGRESO
    assert por_desc["Grocery Store"].monto == 8_540
    assert res.sin_mapear == Counter({"Weird Category": 1})
    assert max(m.fecha for m in res.movimientos) == date(2026, 10, 31)
    assert all(m.fuente is Fuente.IMPORTADO for m in res.movimientos)


def test_my_expenses():
    df = kaggle_my_expenses.leer(DATOS / "my_expenses_muestra.csv")
    res = kaggle_my_expenses.convertir(df, usuario_id=1)
    por_desc = {m.descripcion: m for m in res.movimientos}
    assert por_desc["From dad"].categoria_id == "apoyos"
    assert por_desc["From vicky"].tipo is TipoMovimiento.PRESTAMO
    assert por_desc["To lended people"].tipo is TipoMovimiento.PRESTAMO
    assert por_desc["Took from sbi"].tipo is TipoMovimiento.TRANSFERENCIA
    assert por_desc["Eggs"].categoria_id == "alimentacion"
    assert por_desc["Brownie"].categoria_id == "restaurantes"
    assert res.sin_mapear == Counter({"Pets": 1})


def test_carga_demo_reemplaza_sin_duplicar(repo, tmp_path):
    for nombre in ("personal_transactions_muestra.csv", "my_expenses_muestra.csv"):
        destino = nombre.replace("_muestra", "").replace("my_expenses", "expense_data_1")
        (tmp_path / destino).write_bytes((DATOS / nombre).read_bytes())
    demo.cargar(repo, date(2026, 11, 6), carpeta=tmp_path,
        monedas_verificadas={"Demo · Hogar con salario":("USD","FICTICIA: fixture de prueba")})
    demo.cargar(repo, date(2026, 11, 6), carpeta=tmp_path,
        monedas_verificadas={"Demo · Hogar con salario":("USD","FICTICIA: fixture de prueba")})
    usuarios = repo.listar_usuarios()
    assert sorted(u.nombre for u in usuarios) == ["Demo · Estudiante", "Demo · Hogar con salario"]
    hogar = next(u for u in usuarios if u.moneda == "USD")
    assert len(repo.listar_movimientos(hogar.id)) == 9


def test_desplazar_ajusta_fin_de_mes():
    assert desplazar(date(2019, 1, 31), 1) == date(2019, 2, 28)


def test_formato():
    assert dinero(a_centavos(1_234_567)) == "$1.234.567"
    assert dinero(-5_000, "USD") == "-US$50,00"
    assert dinero(150_000_00, con_signo=True) == "+$150.000"
    assert duracion(1) == "1 mes" and duracion(24) == "2 años" and duracion(14) == "1 año y 2 meses"
