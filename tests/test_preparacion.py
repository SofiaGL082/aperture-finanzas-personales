from datetime import date
from decimal import Decimal
import sqlite3
import pandas as pd
import pytest
from core.preparacion import seleccionar_tasa, preparar
from core.repositorio import crear_base_preparacion


def test_tasa_no_futura_y_maximo_siete_dias():
    tasas=[dict(base="INR",quote="COP",date="2022-01-01",rate=Decimal("50")),
           dict(base="INR",quote="COP",date="2022-01-04",rate=Decimal("60"))]
    assert seleccionar_tasa(tasas,"INR","COP",date(2022,1,3))["rate"]==50
    assert seleccionar_tasa(tasas,"INR","COP",date(2022,1,20)) is None


def test_moneda_desconocida_no_se_inventa(monkeypatch,tmp_path):
    frame=pd.DataFrame({"Date":pd.to_datetime(["2018-01-01"]),"Description":["Test"],"Amount":[10.25],
        "Transaction Type":["debit"],"Category":["Groceries"],"Account Name":["Test"]})
    p=tmp_path/"input.xlsx";p.write_bytes(b"reader stub")
    monkeypatch.setattr(pd,"read_excel",lambda *a,**k:frame.copy())
    rows=preparar(p,"personal_finance")
    assert len(rows)==1 and rows[0]["original_amount_decimal"]=="10.25"
    assert rows[0]["original_currency"] is None and rows[0]["amount_cop_minor"] is None
    assert rows[0]["conversion_status"]=="unidentified_currency"


def test_conversion_usa_fecha_original_y_mantiene_ambiguos(tmp_path):
    p=tmp_path/"expense.csv"
    p.write_text("Date,Account,Category,Note,Amount,INR,Currency,Income/Expense\n"
                 "1/3/2022 10:00,Test,Other,From friend,10,10,INR,Income\n",encoding="utf-8")
    before=p.read_bytes()
    rates=[dict(base="INR",quote="COP",date="2022-01-03",rate=Decimal("50.123"))]
    row=preparar(p,"my_expenses",rates)[0]
    assert row["original_date"]=="2022-01-03" and row["demo_date"] is None
    assert row["amount_cop_minor"]==50123 and row["fx_rate_decimal"]=="50.123"
    assert row["movement_type"]=="income" and row["special_movement"]=="ambiguous_cashflow"
    assert row["needs_review"]==1 and p.read_bytes()==before


def test_staging_preserva_filas_y_no_sobrescribe(tmp_path):
    p=tmp_path/"expense.csv"
    p.write_text("Date,Account,Category,Note,Amount,INR,Currency,Income/Expense\n"
                 "1/3/2022 10:00,Test,Food,Test,10,10,INR,Expense\n",encoding="utf-8")
    rows=preparar(p,"my_expenses")
    dest=tmp_path/"staging.sqlite"
    assert crear_base_preparacion(dest,rows)==1
    before=dest.read_bytes()
    with pytest.raises(FileExistsError):crear_base_preparacion(dest,rows)
    assert dest.read_bytes()==before
    with sqlite3.connect(dest) as con:
        assert con.execute("SELECT amount_cop_minor FROM transacciones_preparadas").fetchone()[0] is None


def test_importador_excel_bloquea_moneda_no_verificada():
    from core.importadores import kaggle_personal_finance
    with pytest.raises(ValueError, match="moneda"):
        kaggle_personal_finance.convertir(pd.DataFrame(),1)


def test_demo_no_asume_moneda_del_excel(repo,tmp_path):
    from core.importadores import demo
    from pathlib import Path
    fixture=Path(__file__).parent/"datos/personal_transactions_muestra.csv"
    (tmp_path/"personal_transactions.csv").write_bytes(fixture.read_bytes())
    assert demo.cargar(repo,date(2026,11,6),carpeta=tmp_path)==[]
    assert repo.listar_usuarios()==[]
