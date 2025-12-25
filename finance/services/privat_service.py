# -*- coding: utf-8 -*-
"""High-level Privatbank service.
Implement mapping from Privat responses to models here.
"""
import logging
import requests
from odoo import _
from odoo.exceptions import UserError

from .privat_client import PrivatClient
from odoo import fields
from odoo import fields

_logger = logging.getLogger(__name__)


def import_accounts(bank):
    """
    Fetches all accounts from PrivatBank and creates/updates them in Odoo.
    :param bank: A `dino.bank` record for PrivatBank.
    :return: A dictionary with stats (created, updated, skipped).
    """
    if not bank.api_key:
        raise UserError(_("API Key (Token) is not set for PrivatBank."))

    client = PrivatClient(api_key=bank.api_key)
    try:
        account_data_list = client.fetch_balances_for_all_accounts()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if getattr(e, 'response', None) else 'HTTP_ERROR'
        resp_text = ''
        try:
            resp_text = (e.response.text or '')[:500]
        except Exception:
            resp_text = ''
        if status in (401, 403):
            # Explicit user-friendly message for invalid/unauthorized token
            raise UserError(_('Неверный API-ключ/токен для ПриватБанка (HTTP %s). Проверьте настройки.') % status)
        if status == 400:
            # Common case: API reports bad request / 'Недопустимая операция'
            raise UserError(_('Запрос к PrivatBank вернул HTTP 400 (Недопустимая операция). Ответ сервера: %s') % resp_text)
        raise UserError(_("Failed to fetch accounts from PrivatBank API. Error: %s") % e)
    except Exception as e:
        raise UserError(_("Failed to fetch accounts from PrivatBank API. Error: %s") % e)

    BankAccount = bank.env['dino.bank.account']
    Currency = bank.env['res.currency']
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for data in account_data_list:
        iban = data.get('iban')
        if not iban:
            _logger.warning("Skipping account data without IBAN: %s", data)
            skipped_count += 1
            continue

        currency_code = data.get('currency')
        currency = Currency.search([('name', '=', currency_code)], limit=1)
        if not currency:
            _logger.warning("Skipping account %s, currency '%s' not found in Odoo.", iban, currency_code)
            skipped_count += 1
            continue

        vals = {
            'name': data.get('nameACC', iban),
            'account_number': iban,
            'bank_id': bank.id,
            'currency_id': currency.id,
            'balance': float(data.get('balanceOut', 0.0)),
            'external_id': data.get('acc'), # PrivatBank uses 'acc' as a unique ID
        }

        existing_account = BankAccount.search([('account_number', '=', iban)], limit=1)
        if existing_account:
            existing_account.write(vals)
            updated_count += 1
        else:
            BankAccount.create(vals)
            created_count += 1
            
    _logger.info(
        "PrivatBank account import finished for bank %s. Created: %d, Updated: %d, Skipped: %d",
        bank.name, created_count, updated_count, skipped_count
    )
    
    return {
        'created': created_count,
        'updated': updated_count,
        'skipped': skipped_count,
    }


def import_transactions(bank, account=None, days_fallback=30):
    """
    Import transactions for a given Privat bank (or for a single account if provided).
    Uses `TECHNICAL_TRANSACTION_ID` as external identifier when present and paginates via followId.

    :param bank: dino.bank record for Privat
    :param account: optional dino.bank.account record to limit import to one account
    :param days_fallback: if neither account.last_import_date nor bank.start_sync_date is set, fallback to this many days
    :return: dict with stats
    """
    if not bank.api_key:
        raise UserError(_('API Key (Token) is not set for PrivatBank.'))

    client = PrivatClient(api_key=bank.api_key)

    # Check API status before heavy calls
    try:
        ok = client.check_api_status()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if getattr(e, 'response', None) else 'HTTP_ERROR'
        if status in (401, 403):
            raise UserError(_('Неверный API-ключ/токен для ПриватБанка (HTTP %s). Проверьте настройки.') % status)
        raise UserError(_('Failed to check Privat API status: %s') % e)
    except Exception as e:
        raise UserError(_('Failed to check Privat API status: %s') % e)
    if not ok:
        raise UserError(_('Privat API is not in a working state (maintenance or restricted). Check /settings endpoint.'))

    BankAccount = bank.env['dino.bank.account']
    TrxModel = bank.env['dino.bank.transaction']

    accounts = account and bank.env['dino.bank.account'].browse(account.id) or BankAccount.search([('bank_id', '=', bank.id), ('active', '=', True)])
    total_created = 0
    total_updated = 0
    total_skipped = 0

    from datetime import datetime, timedelta, date

    for acc in accounts:
        # Determine startDate (DD-MM-YYYY)
        if acc.last_import_date:
            start_dt = acc.last_import_date - timedelta(days=1)
            start_str = start_dt.strftime('%d-%m-%Y')
        elif bank.start_sync_date:
            start_str = bank.start_sync_date.strftime('%d-%m-%Y')
        else:
            d = date.today() - timedelta(days=days_fallback)
            start_str = d.strftime('%d-%m-%Y')

        _logger.info('Starting Privat transactions import for account %s from %s', acc.account_number, start_str)

        created = 0
        updated = 0
        skipped = 0
        latest_txn_dt = None

        try:
            for page in client.fetch_transactions_iter(start_str, acc=acc.external_id or acc.account_number):
                if not page or page.get('status') != 'SUCCESS':
                    _logger.warning('Privat transactions page returned non-success: %s', page)
                    break
                txs = page.get('transactions') or []
                for t in txs:
                    # Determine external id
                    ext = t.get('TECHNICAL_TRANSACTION_ID') or None
                    if not ext:
                        # fallback to REF+REFN or a composite key
                        ref = t.get('REF') or t.get('ref') or ''
                        refn = t.get('REFN') or t.get('refn') or ''
                        if ref or refn:
                            ext = f"{ref}-{refn}"
                        else:
                            ext = t.get('id') or t.get('uniqueId') or None

                    if not ext:
                        _logger.warning('Skipping transaction without identifiable external id: %s', t)
                        skipped += 1
                        continue

                    # Skip if exists
                    existing = TrxModel.search([('bank_account_id', '=', acc.id), ('external_id', '=', str(ext))], limit=1)
                    # Map amount and sign
                    try:
                        amount = float(t.get('amount') or t.get('AMOUNT') or 0.0)
                    except Exception:
                        amount = 0.0
                    # If transaction type suggests debit/outflow, make amount negative
                    tr_type = (t.get('TRANTYPE') or t.get('trantype') or t.get('type') or '')
                    if isinstance(tr_type, str) and tr_type.lower() in ('d', 'debit', 'out'):
                        amount = -abs(amount)

                    # Balance after
                    balance_after = None
                    for k in ('amountRest', 'balanceAfter', 'balance', 'balanceOutOnce'):
                        if k in t:
                            try:
                                balance_after = float(t.get(k) or 0.0)
                                break
                            except Exception:
                                balance_after = None

                    # Date/time parsing: try a few common keys
                    dt_val = None
                    for dk in ('dateTime', 'datetime', 'valueDate', 'date', 'operationDate', 'tranDate'):
                        if dk in t and t.get(dk):
                            dt_val = t.get(dk)
                            break
                    # Try to normalize dt_val to python datetime string — fallback to now
                    from dateutil import parser as _dparser
                    try:
                        if dt_val:
                            # Some APIs return 'DD.MM.YYYY HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS'
                            dt_parsed = _dparser.parse(dt_val, dayfirst=True)
                        else:
                            dt_parsed = datetime.utcnow()
                    except Exception:
                        dt_parsed = datetime.utcnow()

                    if not latest_txn_dt or dt_parsed > latest_txn_dt:
                        latest_txn_dt = dt_parsed

                    desc = t.get('description') or t.get('details') or t.get('PAYMENT') or t.get('purpose') or ''

                    payload = {
                        'external_id': str(ext),
                        'datetime': fields.Datetime.to_string(dt_parsed),
                        'amount': amount,
                        'balance_after': balance_after,
                        'description': desc,
                        'counterparty_name': t.get('AUT_CNTR_NAME') or t.get('AUT_MY_NAME') or t.get('NAME') or None,
                        'counterparty_iban': t.get('AUT_CNTR_ACCOUNT') or t.get('accountTo') or None,
                        'counterparty_edrpou': t.get('AUT_CNTR_EDRPOU') or t.get('cntrEdrpou') or None,
                        'mcc': t.get('MCC') or t.get('mcc') or None,
                        'raw_data': t,
                    }

                    if existing:
                        try:
                            existing.write(payload)
                            updated += 1
                        except Exception:
                            _logger.exception('Failed to update existing transaction %s for account %s', ext, acc.account_number)
                            skipped += 1
                        continue

                    # create
                    try:
                        TrxModel.create_from_api(acc, payload)
                        created += 1
                    except Exception:
                        _logger.exception('Failed to create transaction %s for account %s: %s', ext, acc.account_number, t)
                        skipped += 1

                # loop pages until exist_next_page is falsy
                if not page.get('exist_next_page'):
                    break

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if getattr(e, 'response', None) else 'HTTP_ERROR'
            resp_text = ''
            try:
                resp_text = (e.response.text or '')[:500]
            except Exception:
                resp_text = ''
            if status in (401, 403):
                raise UserError(_('Неверный API-ключ/токен для ПриватБанка (HTTP %s). Проверьте настройки.') % status)
            if status == 400:
                raise UserError(_('Запрос к PrivatBank вернул HTTP 400 (Недопустимая операция). Ответ сервера: %s') % resp_text)
            _logger.exception('HTTP error while importing transactions for account %s: %s', acc.account_number, e)
            continue
        except Exception:
            _logger.exception('Error while importing transactions for account %s', acc.account_number)
            continue

        # update last_import_date to latest_txn_dt if found, otherwise now
        try:
            if latest_txn_dt:
                acc.last_import_date = latest_txn_dt
            else:
                acc.last_import_date = fields.Datetime.now()
        except Exception:
            _logger.exception('Failed to set last_import_date for account %s', acc.account_number)

        _logger.info('Privat transactions import finished for account %s: created=%d updated=%d skipped=%d', acc.account_number, created, updated, skipped)
        total_created += created
        total_updated += updated
        total_skipped += skipped

    return {'created': total_created, 'updated': total_updated, 'skipped': total_skipped}
