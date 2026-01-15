#
#  -*- File: api_integration/services/privat_balance_history.py -*-
#
# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import _, fields
from odoo.exceptions import UserError
from .privat_client import PrivatClient

_logger = logging.getLogger(__name__)


def _parse_privat_date(date_str, time_str=None):
    """Парсит дату формата dd.mm.yyyy [HH:MM:SS]"""
    if not date_str:
        return False
    try:
        if time_str:
            full_str = f"{date_str} {time_str}"
            return datetime.strptime(full_str, '%d.%m.%Y %H:%M')
        return datetime.strptime(date_str, '%d.%m.%Y').date()
    except ValueError:
        try:
            return datetime.strptime(date_str, '%d.%m.%Y').date()
        except:
            return False


def get_client(endpoint):
    """Фабрика для создания клиента"""
    if not endpoint.auth_token:
        raise UserError(_("Not specified API token for endpoint %s") % endpoint.name)
    return PrivatClient(api_key=endpoint.auth_token, client_id=endpoint.auth_api_key)


def import_balance_history(endpoint, startDate=None, endDate=None):
    """
    Импорт истории ежедневных балансов из PrivatBank API.
    Работает только с активными счетами.
    """
    bank = endpoint.bank_id
    if not bank:
        raise UserError(_("Bank not specified for endpoint %s") % endpoint.name)
    
    client = get_client(endpoint)
    BankAccount = bank.env['dino.bank.account']
    BalanceHistory = bank.env['dino.bank.balance.history']
    
    # Получаем только активные счета
    active_accounts = BankAccount.search([
        ('bank_id', '=', bank.id),
        ('active', '=', True)
    ])
    
    if not active_accounts:
        _logger.warning("No active bank accounts found for balance history import")
        return {'stats': {'created': 0, 'updated': 0, 'skipped': 0, 'inactive_accounts': 0}}
    
    # Парсим и форматируем дату для API
    if startDate:
        # Если это строка - парсим, если date объект - используем как есть
        if isinstance(startDate, str):
            try:
                start_date_obj = datetime.strptime(startDate, '%Y-%m-%d').date()
            except ValueError:
                _logger.error(f"Invalid start_date format: {startDate}, expected YYYY-MM-DD")
                start_date_obj = fields.Date.today()
        else:
            start_date_obj = startDate
    elif endpoint.start_date:
        start_date_obj = endpoint.start_date
    else:
        raise UserError(_("Start Date not specified for endpoint '%s'.") % endpoint.name)
    
    # Логика Force Full Sync
    if not endpoint.force_full_sync:
        # Без полной синхронизации - импортируем только новые данные
        # Находим максимальную дату в истории для любого активного счета
        max_date = BalanceHistory.search([
            ('bank_account_id', 'in', active_accounts.ids)
        ], order='date desc', limit=1).date
        
        if max_date:
            # Начинаем с найденной максимальной даты (включительно, чтобы обновить текущий день)
            start_date_obj = max_date
            _logger.info(f"Incremental sync: starting from last known date {max_date}")
        else:
            # Если истории нет - используем configured start_date
            _logger.info(f"No history found, using configured start_date {start_date_obj}")
    else:
        _logger.info(f"Full sync: starting from configured start_date {start_date_obj}")
    
    start_date_str = start_date_obj.strftime('%d-%m-%Y')
    
    _logger.info(f"Starting balance history import from {start_date_str} (no end date)")
    
    total_created = 0
    total_updated = 0
    total_skipped = 0
    inactive_acc_count = 0
    page_count = 0
    
    # Кэш активных счетов по external_id
    active_accounts_map = {acc.external_id: acc for acc in active_accounts if acc.external_id}
    
    _logger.info(f"=== BALANCE HISTORY IMPORT START ===")
    _logger.info(f"Active accounts in Odoo: {len(active_accounts)} ({list(active_accounts_map.keys())})")
    _logger.info(f"Fetching from API: startDate={start_date_str}, endDate=None, acc=None, limit=100")
    
    try:
        # Получаем балансы БЕЗ указания конкретного счета - получим все активные счета
        # API вернет все балансы от startDate и далее через пагинацию (followId)
        for page_balances in client.get_balance_history_generator(
            account_num=None,  # НЕ указываем acc - получим все активные счета
            start_date=start_date_str,
            end_date=None,  # БЕЗ конечной даты - API вернет все с пагинацией
            limit=100
        ):
            page_count += 1
            _logger.info(f"Processing page {page_count}, received {len(page_balances)} balance records")
            
            for balance_data in page_balances:
                # Проверяем что это активный счет
                acc_num = balance_data.get('acc')
                if acc_num not in active_accounts_map:
                    inactive_acc_count += 1
                    continue
                
                current_account = active_accounts_map[acc_num]
                
                # Парсим дату баланса из dpd
                dpd_str = balance_data.get('dpd', '')
                if dpd_str and ' ' in dpd_str:
                    balance_date = _parse_privat_date(dpd_str.split(' ')[0])
                else:
                    _logger.debug(f"No valid dpd date in balance data, skipping")
                    total_skipped += 1
                    continue
                
                if not balance_date:
                    total_skipped += 1
                    continue
                
                # Подготовка данных
                vals = {
                    'date': balance_date,
                    'bank_account_id': current_account.id,
                    'balance_start': float(balance_data.get('balanceIn', 0)),
                    'balance_end': float(balance_data.get('balanceOut', 0)),
                    'turnover_debit': float(balance_data.get('turnoverDebt', 0)),
                    'turnover_credit': float(balance_data.get('turnoverCred', 0)),
                    'is_final': balance_data.get('is_final_bal', False),
                    'last_movement_date': balance_date,
                    'external_id': balance_data.get('acc'),
                    'import_date': fields.Datetime.now()
                }
                
                # Upsert: проверяем существует ли запись
                existing = BalanceHistory.search([
                    ('date', '=', balance_date),
                    ('bank_account_id', '=', current_account.id)
                ], limit=1)
                
                if existing:
                    existing.write(vals)
                    total_updated += 1
                else:
                    BalanceHistory.create(vals)
                    total_created += 1
    
    except Exception as e:
        _logger.error(f"Error importing balance history: {e}", exc_info=True)
        raise
    
    _logger.info(f"=== BALANCE HISTORY IMPORT COMPLETED ===")
    _logger.info(f"Total pages: {page_count}, Created: {total_created}, Updated: {total_updated}, Skipped: {total_skipped}, Inactive: {inactive_acc_count}")
    
    return {
        'stats': {
            'created': total_created,
            'updated': total_updated,
            'skipped': total_skipped,
            'inactive_accounts': inactive_acc_count,
            'errors': 0
        }
    }
# End of file api_integration/services/privat_balance_history.py
