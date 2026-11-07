from pathlib import Path
import pandas as pd
from scripts.eda_datasets import audit


def test_eda_detecta_faltantes_y_no_suma_monedas_originales(tmp_path):
    p=tmp_path/"expense_data_1.csv"
    p.write_text("Date,Account,Category,Note,Amount,INR,Currency,Income/Expense,Subcategory\n"
                 "3/1/2022 10:00,Cash,Food,,15,1120.72,USD,Expense,\n"
                 "3/2/2022 10:00,Cash,Food,Lunch,50,50,INR,Expense,\n",encoding="utf-8")
    before=p.read_bytes()
    summary,missing,monthly,weekly,cats,matrix=audit(p)
    assert summary["rows"]==2 and summary["missing"]["Note"]==1
    assert summary["all_null_columns"]==["Subcategory"]
    assert weekly.expense_minor.sum()==117072
    assert summary["currency_counts"]=={"USD":1,"INR":1}
    assert p.read_bytes()==before


def test_eda_excluye_pagos_tarjeta_sin_borrar_fuente(monkeypatch,tmp_path):
    frame=pd.DataFrame({"Date":pd.to_datetime(["2019-01-01","2019-01-02","2019-01-03"]),
        "Description":["Income","Purchase","Payment"],"Amount":[1000,100,100],
        "Transaction Type":["credit","debit","debit"],
        "Category":["Paycheck","Groceries","Credit Card Payment"],"Account Name":["Test"]*3,
        "Month":["2019-01"]*3})
    p=tmp_path/"test.xlsx";p.write_bytes(b"placeholder for reader stub")
    monkeypatch.setattr(pd,"read_excel",lambda _:frame.copy())
    summary,missing,monthly,weekly,cats,matrix=audit(p)
    assert summary["rows"]==3 and summary["card_payment_rows"]==1
    assert weekly.expense_minor.sum()==10000
    assert summary["month_column_mismatches"]==0
    assert summary["currency_counts"]=={"NO_DECLARADA":3}
