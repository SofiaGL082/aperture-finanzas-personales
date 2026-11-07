"""Preparación trazable sin sobrescribir originales ni la base operativa."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
import hashlib
import re
import pandas as pd
from core.monedas import a_menores, convertir


def seleccionar_tasa(tasas, origen, destino, fecha):
    candidatas=[t for t in tasas if t['base']==origen and t['quote']==destino
                and 0 <= (fecha-date.fromisoformat(t['date'])).days <= 7]
    if not candidatas:
        return None
    return max(candidatas,key=lambda t:t['date'])


def preparar(path, dataset_id, tasas=(), provenance=None):
    """Una salida por fila. Tipos dudosos se marcan; no se borran ni se adivinan."""
    indian=dataset_id=='my_expenses'
    raw=pd.read_csv(path,dtype=str) if indian else pd.read_excel(path,dtype=object)
    dates=pd.to_datetime(raw.Date,format='%m/%d/%Y %H:%M',errors='coerce') if indian else pd.to_datetime(raw.Date,errors='coerce')
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    provenance=provenance or {}
    account_col='Account' if indian else 'Account Name'
    kinds=raw['Income/Expense' if indian else 'Transaction Type'].astype(str).str.strip().str.lower()
    nums=raw.Amount.map(lambda v:str(v).strip())
    coarse=pd.DataFrame(dict(day=dates.dt.normalize(),amount=nums,type=kinds,account=raw[account_col])).duplicated(keep=False)
    exact=raw.duplicated(keep=False)
    rows=[]
    for i,row in raw.iterrows():
        reasons=[]
        original_date=dates.loc[i].date().isoformat() if pd.notna(dates.loc[i]) else None
        if original_date is None: reasons.append('invalid_date')
        currency=str(row.get('Currency','')).strip().upper() if indian else None
        category=str(row.Category).strip() if pd.notna(row.Category) else ''
        description=str(row.get('Note' if indian else 'Description','')).strip()
        if description.lower()=='nan':description=''
        kind=kinds.loc[i]
        mapped={'income':'income','expense':'expense','credit':'income','debit':'expense'}.get(kind,'unknown')
        special=None
        if not category:reasons.append('missing_category')
        if mapped=='unknown':reasons.append('unknown_type')
        if category.lower() in {'credit card payment','transfer'}:
            special='internal_transfer_candidate'
            reasons.append('reconcile_internal_transfer')
        elif indian and re.search(r'^(?:from |to |took from)|lend',description,re.I):
            special='ambiguous_cashflow'
            reasons.append('review_description_without_inferring_loan')
        if coarse.loc[i]:reasons.append('possible_duplicate_coarse_key')
        if exact.loc[i]:reasons.append('exact_duplicate_candidate')
        original_minor=None;original_text=None;cop=None;rate=None;ref=None;source=None;retrieved=None;response_hash=None
        try:
            value=Decimal(str(row.Amount).strip())
            if not value.is_finite() or value<=0:raise ValueError('amount')
            original_text=str(value)
        except Exception:
            reasons.append('invalid_amount');value=None
        status='unidentified_currency' if not currency else 'missing_rate'
        if not currency:reasons.append('currency_not_verified')
        if currency and value is not None:
            try:
                original_minor=a_menores(original_text,currency)
            except ValueError:
                reasons.append('unsupported_currency');status='unsupported_currency'
            else:
                if currency=='COP':
                    cop=original_minor;rate='1';ref=original_date;source='identity';status='converted'
                elif original_date:
                    t=seleccionar_tasa(tasas,currency,'COP',date.fromisoformat(original_date))
                    if t:
                        rate=str(t['rate']);cop=convertir(original_minor,currency,'COP',rate)
                        ref=t['date'];info=provenance.get(currency,{})
                        source=info.get('source','UNSPECIFIED: test data')
                        retrieved=info.get('retrieved_at');response_hash=info.get('response_sha256');status='converted'
                    else:reasons.append('historical_rate_missing')
        if value is None:status='invalid_amount'
        if original_date is None:status='invalid_date'
        account=str(row[account_col]).strip()
        record=dict(transaction_uid=hashlib.sha256(f'{sha}:Sheet1:{i+2}'.encode()).hexdigest(),
            dataset_id=dataset_id,profile_ref=f'dataset:{dataset_id}',source_file=path.name,source_sha256=sha,source_row=int(i+2),
            original_date=original_date,demo_date=None,original_type=kind,movement_type=mapped,special_movement=special,
            category_original=category,category_normalized=category.casefold(),description=description,
            account_ref=hashlib.sha256(f'{dataset_id}:{account}'.encode()).hexdigest()[:16],
            original_amount_decimal=original_text,original_amount_minor=original_minor,original_currency=currency,
            amount_cop_minor=cop,fx_rate_decimal=rate,fx_reference_date=ref,fx_requested_date=original_date,
            fx_source=source,fx_retrieved_at=retrieved,fx_response_sha256=response_hash,conversion_status=status,
            source_equivalent_inr_decimal=str(row.get('INR','')) if indian else None,
            include_in_consumption=int(mapped=='expense' and special!='internal_transfer_candidate'),
            needs_review=int(bool(reasons)),review_reasons=';'.join(reasons))
        rows.append(record)
    return rows
