# -*- coding: utf-8 -*-
"""High-level NBU service: import and sync NBU rates using NBUClient.

Provides functions that operate on `dino.bank` records and use Odoo env to create `dino.currency.rate` rows.
"""
import logging
from datetime import datetime, timedelta
from odoo import fields

from .nbu_client import NBUClient

_logger = logging.getLogger(__name__)


def import_nbu_rates(env, bank, to_date=None, overwrite=False, start_date=None):
    """Import NBU exchange rates into `dino.currency.rate` for a given bank record.

    Returns stats dict similar to previous implementation: {'created': n, 'updated': m, 'skipped': k, 'skipped_details': [...]}
    """
    if not bank:
        return {'created': 0, 'updated': 0, 'skipped': 0}
    if bank.mfo != '300001':
        raise env['ir.config_parameter'].sudo()._get_archived_record('ValueError') if False else Exception('Import from NBU is supported only for the National Bank (MFO 300001).')

    # determine start
    if start_date:
        start = fields.Date.to_date(start_date)
    elif bank.start_sync_date:
        start = fields.Date.to_date(bank.start_sync_date)
    else:
        raise Exception('Currency rate start date is not set on this bank.')
    end = fields.Date.to_date(to_date or fields.Date.context_today(bank))
    if start > end:
        raise Exception('Start date must be earlier than end date.')

    created = 0
    updated = 0
    skipped = 0
    skipped_details = []
    cur_model = env['res.currency']
    active_currencies = cur_model.search([('active', '=', True)])
    active_map = {c.name.upper(): c for c in active_currencies}
    active_map.pop('UAH', None)
    rate_model = env['dino.currency.rate']
    client = NBUClient()

    # prepare list of all dates in the range
    dates = []
    cur = start
    while cur <= end:
        dates.append(cur)
        cur = cur + timedelta(days=1)

    for code, currency in active_map.items():
        existing = rate_model.search([
            ('currency_id', '=', currency.id), ('source', '=', 'nbu'), ('date', '>=', start), ('date', '<=', end)
        ])
        existing_dates = set([r.date for r in existing])
        missing_dates = [d for d in dates if d not in existing_dates]
        if not missing_dates:
            continue
        # compress missing dates into ranges
        ranges = []
        range_start = missing_dates[0]
        prev = missing_dates[0]
        for d in missing_dates[1:]:
            if d == prev + timedelta(days=1):
                prev = d
                continue
            ranges.append((range_start, prev))
            range_start = d
            prev = d
        ranges.append((range_start, prev))
        for rstart, rend in ranges:
            try:
                data = client.fetch_exchange(rstart, rend, code)
                if not isinstance(data, list):
                    skipped_details.append((f'{rstart}-{rend}', code, 'invalid_response'))
                    continue
                for item in data:
                    ex_date_raw = item.get('exchangedate')
                    try:
                        if ex_date_raw and isinstance(ex_date_raw, str) and '.' in ex_date_raw:
                            ex_date = datetime.strptime(ex_date_raw.strip(), '%d.%m.%Y').date()
                        else:
                            skipped += 1
                            skipped_details.append((str(item), code, 'no_date'))
                            continue
                    except Exception:
                        skipped += 1
                        skipped_details.append((str(item), code, 'date_parse_error'))
                        continue
                    if ex_date not in missing_dates:
                        continue
                    rate_val_raw = item.get('rate_per_unit') or item.get('rate')
                    units = item.get('units') or 1
                    try:
                        rate_val = float(rate_val_raw)
                        if 'rate_per_unit' not in item and units and float(units) != 0:
                            rate_val = rate_val / float(units)
                    except Exception:
                        _logger.warning('Invalid rate value for %s on %s: %s', code, ex_date_raw, rate_val_raw)
                        skipped += 1
                        skipped_details.append((str(ex_date), code, 'invalid_rate'))
                        continue
                    existing_rec = rate_model.search([
                        ('currency_id', '=', currency.id), ('date', '=', ex_date), ('source', '=', 'nbu')
                    ], limit=1)
                    if existing_rec:
                        if overwrite:
                            existing_rec.rate = rate_val
                            updated += 1
                        else:
                            skipped += 1
                            skipped_details.append((str(ex_date), code, 'exists'))
                    else:
                        rate_model.create({'name': f'NBU {code} {ex_date}', 'currency_id': currency.id, 'rate': rate_val, 'date': ex_date, 'source': 'nbu'})
                        created += 1
            except requests.RequestException as e:
                _logger.warning('Failed fetching NBU exchange for %s (%s-%s): %s', code, rstart, rend, e)
                skipped_details.append((f'{rstart}-{rend}', code, f'network_error: {e}'))
                continue

    if skipped_details:
        _logger.info('Sample skipped entries (date, code, reason): %s', skipped_details[:100])

    return {'created': created, 'updated': updated, 'skipped': skipped, 'skipped_details': skipped_details[:500]}


def import_and_sync_nbu(env, bank_record, overwrite=False):
    """Single-pass import + sync using import_nbu_rates() and then syncing into res.currency.rate.

    Returns summary dict.
    """
    stats = import_nbu_rates(env, bank_record, overwrite=overwrite)
    # After import, sync dino.currency.rate -> res.currency.rate
    rate_model = env['dino.currency.rate']
    sys_rate = env['res.currency.rate']
    created_sys = 0
    updated_sys = 0
    skipped_sys = 0
    details = []
    nbu_rates = rate_model.search([('source', '=', 'nbu')], order='date asc')
    active_currencies = env['res.currency'].search([('active', '=', True)])
    active_map = {c.name.upper(): c for c in active_currencies}
    active_map.pop('UAH', None)
    for r in nbu_rates:
        code = r.currency_id.name.upper() if r.currency_id else None
        if not code or code not in active_map:
            skipped_sys += 1
            details.append((str(r.date), code or 'NONE', 'currency_not_active_or_missing'))
            continue
        currency = active_map[code]
        exists = sys_rate.search([('currency_id', '=', currency.id), ('name', '=', r.date)], limit=1)
        if exists:
            if overwrite:
                exists.rate = r.rate
                updated_sys += 1
                details.append((str(r.date), code, 'updated'))
            else:
                skipped_sys += 1
                details.append((str(r.date), code, 'exists'))
        else:
            vals = {'currency_id': currency.id, 'rate': r.rate}
            try:
                vals['name'] = r.date
            except Exception:
                vals['name'] = str(r.date)
            sys_rate.create(vals)
            created_sys += 1
            details.append((str(r.date), code, 'created'))

    result = {'created_dino': stats.get('created', 0), 'created_sys': created_sys, 'updated_sys': updated_sys, 'skipped': stats.get('skipped', 0) + skipped_sys, 'details': details[:200]}
    return result


def run_sync(bank):
    """
    Standardized entry point for the dispatcher.
    For NBU, it triggers the import and sync of currency rates.
    """
    bank.ensure_one()
    _logger.info("Running NBU currency rate sync for bank: %s", bank.name)
    
    # We can call the button method directly, as it contains the required logic and notifications
    return bank.button_import_and_sync()
