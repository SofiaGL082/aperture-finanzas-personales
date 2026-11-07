"""EDA reproducible de solo lectura. Ejecutar: python -m scripts.eda_datasets"""
import argparse, hashlib, html, json, platform
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import statistics
from pathlib import Path
import pandas as pd
import plotly
import plotly.express as px

def minor(v):
    try:
        d=Decimal(str(v))
        return int((d*100).quantize(Decimal(1),rounding=ROUND_HALF_UP)) if d.is_finite() else None
    except Exception:
        return None

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def audit(path):
    indian=path.suffix=='.csv'
    raw=pd.read_csv(path,dtype=str) if indian else pd.read_excel(path)
    missing=raw.isna() | raw.map(lambda v:isinstance(v,str) and not v.strip())
    dates=pd.to_datetime(raw.Date,format='%m/%d/%Y %H:%M',errors='coerce') if indian else pd.to_datetime(raw.Date,errors='coerce')
    amounts=raw.Amount.map(minor)
    values=raw.INR.map(minor) if indian else amounts
    types=raw['Income/Expense' if indian else 'Transaction Type'].astype(str).str.strip().str.lower()
    categories=raw.Category.astype('string').str.strip()
    transfer=categories.str.lower().isin(['credit card payment','transfer']) if not indian else pd.Series(False,index=raw.index)
    expense=types.eq('expense' if indian else 'debit') & ~transfer
    currencies=raw.Currency.astype(str).str.upper() if indian else pd.Series('NO_DECLARADA',index=raw.index)
    accounts=raw['Account' if indian else 'Account Name']
    valid=dates.notna() & values.notna() & values.gt(0)
    d=pd.DataFrame(dict(date=dates,value=values,category=categories,expense=expense,transfer=transfer,income=types.eq('income' if indian else 'credit') & ~transfer))[valid].copy()
    d['month']=d.date.dt.to_period('M');d['week']=d.date.dt.to_period('W-SUN')
    first,last=d.date.min().normalize(),d.date.max().normalize()
    weeks=pd.period_range(first.to_period('W-SUN'),last.to_period('W-SUN'),freq='W-SUN')
    months=pd.period_range(first.to_period('M'),last.to_period('M'),freq='M')
    monthly=pd.DataFrame(index=months)
    monthly['transactions']=d.groupby('month').size().reindex(months,fill_value=0)
    monthly['days_with_records']=d.groupby('month').date.apply(lambda x:x.dt.normalize().nunique()).reindex(months,fill_value=0)
    monthly['expense_minor']=d[d.expense].groupby('month').value.sum().reindex(months,fill_value=0).astype('int64')
    monthly['inflow_minor']=d[d.income].groupby('month').value.sum().reindex(months,fill_value=0).astype('int64')
    monthly['recorded_cashflow_minor']=monthly.inflow_minor-monthly.expense_minor
    monthly['inside_date_bounds']=[m.start_time.normalize()>=first and m.end_time.normalize()<=last for m in months]
    weekly=pd.DataFrame(index=weeks)
    weekly['transactions']=d.groupby('week').size().reindex(weeks,fill_value=0)
    weekly['expense_minor']=d[d.expense].groupby('week').value.sum().reindex(weeks,fill_value=0).astype('int64')
    weekly['inside_date_bounds']=[w.start_time.normalize()>=first and w.end_time.normalize()<=last for w in weeks]
    matrix=d[d.expense].pivot_table(index='week',columns='category',values='value',aggfunc='sum',fill_value=0).reindex(weeks,fill_value=0)
    cs=[]
    for cat,g in d[d.expense].groupby('category'):
        w=matrix.loc[weekly.inside_date_bounds,cat]
        q1,q3=g.value.astype(float).quantile([.25,.75])
        cs.append(dict(category=cat,transactions=len(g),total_minor=int(g.value.sum()),median_transaction_minor=str((Decimal(sorted(int(v) for v in g.value)[(len(g)-1)//2])+Decimal(sorted(int(v) for v in g.value)[len(g)//2]))/2),mean_transaction_decimal=str(Decimal(int(g.value.sum()))/Decimal(100*len(g))),active_bounded_weeks=int(w.gt(0).sum()),
                       fraction_zero_weeks=float(w.eq(0).mean()),iqr_upper_flags=int(g.value.gt(q3+1.5*(q3-q1)).sum()) if len(g)>=8 else None))
    cs=pd.DataFrame(cs).sort_values('total_minor',ascending=False)
    keys=pd.DataFrame(dict(day=dates.dt.normalize(),amount=amounts,type=types,account=accounts))
    pairs=pd.DataFrame(dict(day=dates[transfer].dt.normalize(),amount=amounts[transfer],type=types[transfer]))
    unmatched=0
    if len(pairs):
        g=pairs.groupby(['day','amount','type']).size().unstack(fill_value=0)
        unmatched=int((g.get('credit',pd.Series(0,index=g.index))-g.get('debit',pd.Series(0,index=g.index))).abs().sum())
    note=raw['Note' if indian else 'Description'].fillna('').astype(str)
    summary=dict(file=path.name,sha256=sha(path),rows=len(raw),columns=len(raw.columns),column_names=list(raw.columns),dtypes=raw.dtypes.astype(str).to_dict(),memory_bytes=int(raw.memory_usage(deep=True).sum()),unique_values={k:int(v) for k,v in raw.nunique().items()},category_counts=categories.value_counts().to_dict(),account_labels_count=int(accounts.nunique()),explicit_person_id_present=False,category_whitespace_rows=int((raw.Category.astype(str)!=raw.Category.astype(str).str.strip()).sum()),
        missing={k:int(v) for k,v in missing.sum().items()},all_null_columns=missing.columns[missing.all()].tolist(),
        exact_duplicate_rows=int(raw.duplicated(keep=False).sum()),additional_exact_duplicates=int(raw.duplicated().sum()),
        coarse_duplicate_candidates=int(keys.duplicated(keep=False).sum()),
        invalid_dates=int(dates.isna().sum()),invalid_amounts=int(amounts.isna().sum()),nonpositive_amounts=int(amounts.le(0).sum()),
        accepted_for_eda=len(d),type_counts=types.value_counts().to_dict(),currency_counts=currencies.value_counts().to_dict(),
        amount_account1_equal=bool(raw['Account.1'].map(minor).equals(amounts)) if 'Account.1' in raw else None,
        analysis_unit='INR: columna de equivalente documentada' if indian else 'Unidad original; moneda no declarada en el Excel',
        original_vs_inr_differences=int((amounts!=values).sum()) if indian else None,
        date_min=str(first.date()),date_max=str(last.date()),calendar_days_span=int((last-first).days+1),
        days_with_records=int(d.date.dt.normalize().nunique()),months_spanned=len(months),months_without_records=int(monthly.transactions.eq(0).sum()),
        weeks_spanned=len(weeks),calendar_bounded_weeks=int(weekly.inside_date_bounds.sum()),
        bounded_weeks_without_records=int((weekly.inside_date_bounds & weekly.transactions.eq(0)).sum()),
        card_payment_rows=int(transfer.sum()),unpaired_card_legs_coarse_match=unmatched,
        ambiguous_note_candidates=int(note.str.contains(r'^(?:from |to |took from)|lend',case=False,regex=True).sum()) if indian else 0,
        month_column_mismatches=int((raw.Month.astype(str)!=dates.dt.strftime('%Y-%m')).sum()) if 'Month' in raw else None)
    missing_table=pd.DataFrame(dict(column=raw.columns,missing=missing.sum().values,fraction=missing.mean().values))
    return summary,missing_table,monthly,weekly,cs,matrix

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path('data/demo'))
    parser.add_argument('--output-dir',type=Path,default=Path('reports/eda'))
    args=parser.parse_args();sources=[]
    for pattern in ('expense_data_1.csv','personal_transactions*.xlsx'):
        found=sorted(args.data_dir.rglob(pattern))
        if len(found)!=1:raise ValueError(f'Archivo ambiguo o ausente: {pattern}; encontrados {len(found)}')
        sources.append(found[0])
    args.output_dir.mkdir(parents=True,exist_ok=True)
    before={str(p):sha(p) for p in sources}
    results=[audit(p) for p in sources]
    summary=dict(generated_utc=datetime.now(timezone.utc).isoformat(),versions=dict(python=platform.python_version(),pandas=pd.__version__,plotly=plotly.__version__),datasets=[r[0] for r in results])
    (args.output_dir/'quality_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    blocks=[]
    for i,(s,missing,monthly,weekly,cats,matrix) in enumerate(results):
        slug='my_expenses' if i==0 else 'personal_finance'
        for name,frame in [('missing',missing),('monthly',monthly),('weekly',weekly),('categories',cats),('weekly_by_category',matrix)]:
            frame.to_csv(args.output_dir/f'{slug}_{name}.csv',index=name not in ('missing','categories'))
        mm=monthly.reset_index(names='month');mm['month']=mm.month.astype(str)
        ww=weekly.reset_index(names='week');ww['week']=ww.week.map(lambda w:str(w.start_time.date()));ww['expense']=ww.expense_minor/100
        cat=cats.head(10).copy();cat['amount']=cat.total_minor/100
        week_fig=px.line(ww[ww.inside_date_bounds],x='week',y='expense',markers=True,
                         title='Gastos semanales registrados',labels={'week':'Inicio de semana','expense':'Importe en unidad de análisis'})
        edge=ww[~ww.inside_date_bounds]
        week_fig.add_scatter(x=edge.week,y=edge.expense,mode='markers',name='Borde parcial',marker=dict(color='#D97706',size=9))
        figs=[px.bar(missing,x='column',y='fraction',title='Valores vacíos por campo',labels={'column':'Campo','fraction':'Fracción faltante'}),
              px.bar(mm,x='month',y='transactions',title='Movimientos por mes',labels={'month':'Mes','transactions':'Movimientos'}),
              week_fig,
              px.bar(cat,x='amount',y='category',orientation='h',title='Categorías de gasto: exploración de todo el historial',labels={'amount':'Importe en unidad de análisis','category':'Categoría'})]
        figs[0].update_yaxes(range=[0,1],tickformat='.0%')
        figs[1].update_xaxes(type='category',tickangle=-35)
        blocks.append('<section><h2>'+html.escape(s['file'])+'</h2><p>'+str(s['rows'])+' filas · '+s['date_min']+' a '+s['date_max']+'</p><p>Unidad: '+html.escape(s['analysis_unit'])+'</p>')
        for j,fig in enumerate(figs):
            fig.update_layout(template='plotly_white',colorway=['#4F46E5','#0F766E'],font=dict(family='Arial',color='#14213D'))
            blocks.append(fig.to_html(full_html=False,include_plotlyjs='inline' if i==0 and j==0 else False,config=dict(responsive=True,displaylogo=False)))
        table=cats.copy()
        table['total_minor']=table.total_minor.map(lambda v:str((Decimal(int(v))/100).quantize(Decimal('.01'))))
        table['median_transaction_minor']=table.median_transaction_minor.map(lambda v:str((Decimal(v)/100).quantize(Decimal('.01'))))
        table['mean_transaction_decimal']=table.mean_transaction_decimal.map(lambda v:str(Decimal(v).quantize(Decimal('.01'))))
        table['fraction_zero_weeks']=table.fraction_zero_weeks.map(lambda v:f'{v:.1%}')
        table['iqr_upper_flags']=table.iqr_upper_flags.map(lambda v:'No aplica (<8 registros)' if pd.isna(v) else str(int(v)))
        table.columns=['Categoría','Movimientos','Total (unidad de análisis)','Mediana','Media','Semanas con gasto','Semanas sin gasto registrado','Banderas IQR']
        blocks.append('<h3>Actividad y valores extremos por categoría</h3><p>Importes en la unidad indicada; tablas CSV conservan precisión adicional.</p>'+table.to_html(index=False,border=0)+'</section>')
    intro='<aside><strong>Interpretación</strong><ul><li>Ausencia de registros no significa gasto cero. Los límites de fechas no certifican completitud.</li><li>La moneda del Excel no está declarada. No combinar sus importes con INR.</li><li>Pagos de tarjeta identificados se excluyen del gasto; no se borran atípicos ni candidatos a duplicado.</li><li>La selección de categorías usa todo el historial solo para EDA. En experimentos se debe hacer con entrenamiento.</li><li>Sin imputación, entrenamiento ni resultados predictivos. No se infiere representatividad colombiana.</li></ul></aside>'
    head='<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EDA Aperture</title><style>body{font-family:Arial;background:#F6F8FC;color:#14213D;padding:28px;line-height:1.55}main{max-width:1180px;margin:auto}section,aside{background:white;padding:24px;margin:24px 0;border:1px solid #E2E8F0;border-radius:16px;overflow:auto}aside{border-left:5px solid #4F46E5}table{width:100%;font-size:13px;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #E2E8F0}@media(max-width:600px){body{padding:8px}section{padding:12px}}</style><main><h1>EDA · APERTURE — Finanzas Personales</h1><p>Auditoría reproducible de los originales. No se entrenaron modelos.</p>'
    (args.output_dir/'informe_interactivo.html').write_text(head+intro+''.join(blocks)+'</main></html>',encoding='utf-8')
    if before!={str(p):sha(p) for p in sources}:raise RuntimeError('Los originales cambiaron durante el EDA.')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('SHA-256: originales sin cambios.')

if __name__=='__main__':
    main()
