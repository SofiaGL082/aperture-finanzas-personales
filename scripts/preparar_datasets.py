"""Normaliza y convierte solo monedas verificadas; conserva cada fila en staging."""
import argparse
import csv
from collections import Counter
from datetime import datetime,timezone,date,timedelta
from decimal import Decimal
import hashlib,json
from pathlib import Path
from urllib.request import urlopen
import pandas as pd
from core.preparacion import preparar
from core.repositorio import crear_base_preparacion


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path('data/demo'))
    parser.add_argument('--output-dir',type=Path,default=Path('data/processed'))
    parser.add_argument('--offline',action='store_true',help='Usar únicamente respuestas históricas guardadas')
    args=parser.parse_args()
    paths={}
    for key,pattern in [('personal_finance','personal_transactions*.xlsx'),('my_expenses','expense_data_1.csv')]:
        files=sorted(args.data_dir.rglob(pattern))
        if len(files)!=1:raise ValueError(f'Archivo ausente o ambiguo: {pattern}')
        paths[key]=files[0]
    original_hash={str(p):digest(p) for p in paths.values()}
    operational=Path('data/fintwin.db')
    original_db_hash=digest(operational) if operational.exists() else None
    args.output_dir.mkdir(parents=True,exist_ok=True)
    run=args.output_dir/datetime.now(timezone.utc).strftime('eda_%Y%m%dT%H%M%S%fZ')
    run.mkdir(exist_ok=False)
    cache=args.output_dir/'fx_cache';cache.mkdir(exist_ok=True)
    raw=pd.read_csv(paths['my_expenses'],dtype=str)
    dates=pd.to_datetime(raw.Date,format='%m/%d/%Y %H:%M').dt.date
    rates=[];provenance={};fetch_errors=[]
    for currency in sorted(raw.Currency.unique()):
        mask=raw.Currency.eq(currency)
        start=min(dates[mask])-timedelta(days=7);end=max(dates[mask])
        url=f'https://api.frankfurter.dev/v2/rates?from={start.isoformat()}&to={end.isoformat()}&base={currency}&quotes=COP&expand=providers'
        key=hashlib.sha256(url.encode()).hexdigest()
        data_path=cache/(key+'.json');meta_path=cache/(key+'.meta.json')
        if not data_path.exists():
            if args.offline:
                fetch_errors.append(f'{currency}: sin caché histórica; importes COP quedarán nulos')
                continue
            try:
                with urlopen(url,timeout=25) as response:body=response.read()
                parsed=json.loads(body,parse_float=Decimal)
                if not isinstance(parsed,list) or not parsed:raise ValueError('Respuesta histórica vacía')
                metadata=dict(url=url,retrieved_at=datetime.now(timezone.utc).isoformat(),response_sha256=hashlib.sha256(body).hexdigest(),source='Frankfurter v2: referencia blended, no tasa bancaria ni TRM certificada')
                data_path.write_bytes(body)
                meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception as exc:
                fetch_errors.append(f'{currency}: {type(exc).__name__}; sin conversión inventada')
                continue
        metadata=json.loads(meta_path.read_text(encoding='utf-8'))
        if digest(data_path)!=metadata['response_sha256'] or metadata['url']!=url:
            raise ValueError('La respuesta guardada no supera la verificación de procedencia.')
        data=json.loads(data_path.read_text(encoding='utf-8'),parse_float=Decimal)
        for t in data:
            if t['base']!=currency or t['quote']!='COP':raise ValueError('Par incorrecto en respuesta')
            if Decimal(str(t['rate']))<=0:raise ValueError('Tasa no positiva')
        rates.extend(data);provenance[currency]=metadata
    all_rows=[];summaries=[]
    for dataset_id,path in paths.items():
        rows=preparar(path,dataset_id,rates,provenance)
        all_rows.extend(rows)
        csv_path=run/(dataset_id+'_preparado.csv')
        with csv_path.open('w',encoding='utf-8',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        converted=[r for r in rows if r['conversion_status']=='converted']
        report=dict(dataset_id=dataset_id,source_file=path.name,source_sha256=digest(path),rows=len(rows),
                    conversion_status=dict(Counter(r['conversion_status'] for r in rows)),review_rows=sum(r['needs_review'] for r in rows),
                    converted_cop_minor_all_movement_types=sum(r['amount_cop_minor'] for r in converted) if converted else None,
                    distinct_rates_used=len({(r['original_currency'],r['fx_reference_date'],r['fx_rate_decimal']) for r in converted}),
                    output_file=str(csv_path),output_sha256=digest(csv_path))
        summaries.append(report)
    db=run/'preparacion.sqlite'
    count=crear_base_preparacion(db,all_rows)
    manifest=dict(generated_utc=datetime.now(timezone.utc).isoformat(),datasets=summaries,staging_sqlite=str(db),sqlite_rows=count,
                  fx_provenance=provenance,fetch_errors=fetch_errors,
                  rules=['Una fila de salida por fila original; sin borrados ni imputaciones.',
                         'Fechas originales para FX. demo_date queda vacío en preparación.',
                         'Moneda del Excel no verificada: COP nulo, no se asume USD.',
                         'Tasa de la fecha o última anterior hasta siete días. Nunca tasa futura.',
                         'Redondeo HALF_UP una vez a centavos COP mediante Decimal.',
                         'Perfiles separados; los tipos ambiguos requieren revisión.',
                         'Staging separado: no se carga en la base operativa.'],
                  totals_note='La suma de todos los tipos no representa gasto, ingreso ni ahorro; sirve solo para conciliación de importes.')
    (run/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    dest=Path('reports/eda');dest.mkdir(parents=True,exist_ok=True)
    (dest/'preparacion_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    if original_hash!={str(p):digest(p) for p in paths.values()}:raise RuntimeError('Cambió un original')
    if original_db_hash!=(digest(operational) if operational.exists() else None):raise RuntimeError('Cambió la base operativa')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    print('Originales y base operativa sin modificaciones.')

if __name__=='__main__':main()
