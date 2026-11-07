"""Todas las tasas son FICTICIAS, no referencias de mercado."""
from datetime import date
from decimal import Decimal
from dataclasses import replace
import sqlite3
import pandas as pd
import pytest
from core.monedas import Tasa, a_menores, convertir
from core.dominio import Movimiento,Meta,Naturaleza,TipoMovimiento
from core.repositorio import Repositorio,_MIGRACIONES
from core import reportes
from core.importadores import kaggle_my_expenses,kaggle_personal_finance,demo

D=date(2026,10,5)

def tasa(repo,origen,destino,valor,fecha=D):
    return repo.guardar_tasa(Tasa(origen,destino,fecha,Decimal(valor),"FICTICIA: prueba automatizada","2026-11-06T00:00:00+00:00"))


def gasto(uid,moneda="USD",valor=1234,tid=None,fecha=D):
    return Movimiento(None,uid,fecha,"Prueba ficticia",valor,TipoMovimiento.GASTO,
                      "restaurantes",Naturaleza.VARIABLE,moneda_original=moneda,tasa_id=tid)


@pytest.mark.parametrize("origen,destino,valor,t,esperado",[
 ("COP","USD",400000,"0.00025",100),
 ("USD","COP",100,"4000",400000),
 ("EUR","COP",100,"4500",450000),
 ("INR","COP",100,"50",5000),
 ("COP","COP",12345,None,12345),
 ("JPY","USD",100,"0.01",100),
 ("KWD","USD",1000,"3",300),
])
def test_conversion_exacta(origen,destino,valor,t,esperado):
    assert convertir(valor,origen,destino,t)==esperado


def test_precision_y_redondeo():
    assert a_menores("0.105","USD")==11
    assert a_menores("123.456","KWD")==123456
    assert convertir(1,"USD","COP","0.5")==1
    assert a_menores("90071992547409.93","COP")==9007199254740993


@pytest.mark.parametrize("t",[None,"0","-1","NaN","Infinity",0.1])
def test_tasas_invalidas(t):
    with pytest.raises(ValueError):
        convertir(100,"USD","COP",t)


def test_movimiento_conserva_original_y_equivalente(repo):
    u=repo.crear_usuario("Prueba")
    tid=tasa(repo,"USD","COP","4000")
    repo.agregar_movimiento(gasto(u.id,tid=tid))
    m=repo.listar_movimientos(u.id)[0]
    assert (m.monto,m.monto_original,m.moneda_original,m.tasa_id)==(4936000,1234,"USD",tid)
    assert repo.obtener_tasa(tid).fuente.startswith("FICTICIA")
    repo.actualizar_movimiento(replace(m,descripcion="Corregida"))
    assert repo.listar_movimientos(u.id)[0].monto==4936000


def test_sin_tasa_no_inserta(repo):
    u=repo.crear_usuario("Prueba")
    with pytest.raises(ValueError,match="tasa"):
        repo.agregar_movimiento(gasto(u.id))
    assert repo.listar_movimientos(u.id)==[]


def test_no_usa_tasa_de_otro_par_o_futuro(repo):
    u=repo.crear_usuario("Prueba")
    for tid in (tasa(repo,"EUR","COP","4500"),tasa(repo,"USD","COP","4000",date(2026,10,6))):
        with pytest.raises(ValueError):
            repo.agregar_movimiento(gasto(u.id,tid=tid))


def test_reportes_en_moneda_comun_y_transferencias_excluidas(repo):
    u=repo.crear_usuario("Prueba")
    tid=tasa(repo,"USD","COP","4000")
    repo.agregar_movimiento(gasto(u.id,tid=tid))
    repo.agregar_movimiento(replace(gasto(u.id,tid=tid),tipo=TipoMovimiento.TRANSFERENCIA,categoria_id=None))
    sep=date(2026,9,5)
    repo.agregar_movimiento(gasto(u.id,"COP",100000,fecha=sep))
    df=reportes.tabla(repo.listar_movimientos(u.id))
    res=reportes.resumen_mensual(df)
    assert res.loc[pd.Period("2026-10"),"gastos"]==4936000
    assert res.loc[pd.Period("2026-09"),"gastos"]==100000


def test_meta_extranjera_equivalente_fijo(repo):
    u=repo.crear_usuario("Prueba")
    tid=tasa(repo,"USD","COP","4000")
    repo.guardar_meta(Meta(None,u.id,"Viaje",10000,1000,moneda_original="USD",tasa_id=tid,fecha_valoracion=D))
    m=repo.listar_metas(u.id)[0]
    assert (m.monto_objetivo,m.ahorrado,m.monto_objetivo_original)==(40000000,4000000,10000)
    tasa(repo,"USD","COP","5000")
    assert repo.listar_metas(u.id)[0].faltante==36000000


def test_migracion_v1_preserva_importes_y_perfiles(tmp_path):
    path=tmp_path/"v1.db"
    c=sqlite3.connect(path)
    c.executescript(_MIGRACIONES[0])
    c.execute("INSERT INTO usuarios(id,nombre,moneda) VALUES(1,'Prueba','INR')")
    c.execute("INSERT INTO movimientos(usuario_id,fecha,monto,tipo,naturaleza,fuente) VALUES(1,'2022-03-02',1234,'transferencia','variable','manual')")
    c.execute("PRAGMA user_version=1")
    c.commit();c.close()
    r=Repositorio(path)
    m=r.listar_movimientos(1)[0]
    assert (m.monto,m.monto_original,m.moneda_original)==(1234,1234,"INR")
    assert r.version_esquema==2
    r.cerrar()
    r=Repositorio(path)
    assert len(r.listar_movimientos(1))==1
    r.cerrar()


def test_importacion_usd_en_dataset_inr_y_fecha_original(repo):
    df=pd.DataFrame([{"Date":"3/2/2022 10:11","Category":"Food","Note":"Prueba", "Amount":"15","INR":"1120.72","Currency":"USD","Income/Expense":"Expense"}])
    u=repo.crear_usuario("Prueba",moneda="INR")
    res=kaggle_my_expenses.convertir(df,u.id,mes_destino=date(2026,10,1))
    repo.agregar_movimientos(res.movimientos)
    m=repo.listar_movimientos(u.id)[0]
    assert (m.monto,m.monto_original,m.moneda_original)==(112072,1500,"USD")
    assert m.fecha_original==date(2022,3,2) and m.fecha==date(2026,10,2)


def test_importador_rechaza_tipo_desconocido():
    df=pd.DataFrame([{"Date":"2019-01-01","Description":"Prueba","Amount":"10","Transaction Type":"unknown","Category":"Groceries","Account Name":"Test"}])
    res=kaggle_personal_finance.convertir(df,1,moneda_verificada="USD",fuente_moneda="FICTICIA: fixture")
    assert res.total==0 and res.descartadas==1


def test_unidad_trabajo_revierte_cambios(repo):
    u=repo.crear_usuario("Original")
    with pytest.raises(ValueError):
        with repo.unidad_trabajo():
            repo.eliminar_usuario(u.id)
            repo.crear_usuario("Reemplazo")
            raise ValueError("Fallo simulado")
    assert [x.nombre for x in repo.listar_usuarios()]==["Original"]
