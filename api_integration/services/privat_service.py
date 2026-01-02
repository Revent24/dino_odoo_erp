# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import _, fields
from odoo.exceptions import UserError
from .privat_client import PrivatClient
from .nbu_service import import_rates_to_dino

_logger = logging.getLogger(__name__)

def _parse_privat_date(date_str, time_str=None):
    """Парсит дату формата dd.mm.yyyy [HH:MM:SS]"""
    if not date_str:
        return False
    try:
        if time_str:
            full_str = f"{date_str} {time_str}"
            return datetime.strptime(full_str, '%d.%m.%Y %H:%M') # Иногда секунды не приходят, или формат разный
        return datetime.strptime(date_str, '%d.%m.%Y').date()
    except ValueError:
        # Fallback если формат чуть другой
        try:
            return datetime.strptime(date_str, '%d.%m.%Y').date()
        except:
            return False

def get_client(endpoint):
    """Фабрика для создания клиента"""
    if not endpoint.auth_token:
        raise UserError(_("Not specified API token for endpoint %s") % endpoint.name)
    return PrivatClient(api_key=endpoint.auth_token, client_id=endpoint.auth_api_key)


def import_accounts(endpoint, startDate=None, endDate=None):
    """Импорт и обновление балансов."""
    bank = endpoint.bank_id
    if not bank:
        raise UserError(_("Bank not specified for endpoint %s") % endpoint.name)
    client = get_client(endpoint)
    
    # Дата по умолчанию - сегодня
    target_date = startDate or fields.Date.today().strftime('%d-%m-%Y')
    
    try:
        raw_balances = client.fetch_balances(date_str=target_date)
    except Exception as e:
        raise UserError(_("Ошибка получения балансов: %s") % e)

    BankAccount = bank.env['dino.bank.account']
    Currency = bank.env['res.currency']
    
    # Кэш валют, чтобы не делать search в цикле
    currency_map = {c.name: c.id for c in Currency.search([('active', '=', True)])}
    
    stats = {'created': 0, 'updated': 0, 'skipped': 0}
    processed_ids = []

    for data in raw_balances:
        # Приват может отдавать и acc, и iban. IBAN приоритетнее для уникальности
        acc_num = data.get('iban') or data.get('acc')
        currency_code = data.get('currency')
        
        if not acc_num:
            continue
            
        curr_id = currency_map.get(currency_code)
        if not curr_id:
            # Если UAH не найден - это критично, но пропускаем тихо
            stats['skipped'] += 1
            continue

        # Парсим дату обновления баланса
        balance_date = _parse_privat_date(data.get('dpd', '').split(' ')[0])

        vals = {
            'name': data.get('nameACC') or acc_num,
            'bank_id': bank.id,
            'currency_id': curr_id,
            'account_number': acc_num,
            'balance': float(data.get('balanceOut', 0)),
            'balance_start': float(data.get('balanceIn', 0)),
            'external_id': data.get('acc'), # Внутренний ID привата, полезен для транзакций
            'active': True
        }

        # Ищем существующий (Upsert logic)
        existing = BankAccount.search([
            ('account_number', '=', acc_num), 
            ('bank_id', '=', bank.id)
        ], limit=1)

        if existing:
            existing.write(vals)
            stats['updated'] += 1
            processed_ids.append(existing.id)
        else:
            new_acc = BankAccount.create(vals)
            stats['created'] += 1
            processed_ids.append(new_acc.id)

    return {'stats': stats, 'accounts': BankAccount.browse(processed_ids)}


def import_transactions(endpoint, startDate=None, endDate=None):
    """
    Массовый импорт транзакций по всем счетам сразу (без параметра acc).
    """
    bank = endpoint.bank_id
    if not bank:
        raise UserError(_("Bank not specified for endpoint %s") % endpoint.name)
    
    client = get_client(endpoint)
    TransModel = bank.env['dino.bank.transaction']
    AccountModel = bank.env['dino.bank.account']

    # 1. Даты
    if startDate:
        s_date_val = fields.Date.to_date(startDate)
    elif endpoint.start_date:
        s_date_val = endpoint.start_date
    else:
        raise UserError(_("Start Date not specified for endpoint '%s'.") % endpoint.name)

    s_date_api = s_date_val.strftime('%d-%m-%Y')
    e_date_api = fields.Date.to_date(endDate).strftime('%d-%m-%Y') if endDate else None

    # 2. Подготовка карты счетов (Mapping)
    # Нам нужно быстро находить ID счета в Odoo по номеру из JSON (AUT_MY_ACC)
    # Приват может прислать в AUT_MY_ACC как IBAN, так и внутренний номер.
    local_accounts = AccountModel.search([('bank_id', '=', bank.id)])
    acc_map = {}
    
    for acc in local_accounts:
        # Ключом может быть IBAN
        if acc.account_number:
            acc_map[acc.account_number] = acc
        # ИЛИ внутренний ID (acc), если он есть
        if acc.external_id:
            acc_map[acc.external_id] = acc

    if not acc_map:
         raise UserError(_("Не найдено ни одного счета для банка %s") % bank.name)

    _logger.info(f"Запуск массового импорта транзакций с {s_date_api}")

    # 3. Запрос к API без указания конкретного счета (account_num=None)
    # Клиент будет листать страницы, пока они не закончатся
    pages_iter = client.get_transactions_generator(
        account_num=None, 
        start_date=s_date_api,
        end_date=e_date_api
    )

    total_created = 0
    total_skipped = 0
    unknown_acc_count = 0
    total_processed = 0

    page_count = 0
    for trans_batch in pages_iter:
        page_count += 1
        batch_size = len(trans_batch) if trans_batch else 0
        _logger.info(f"Обработка страницы {page_count}: получено {batch_size} транзакций из API")
        total_processed += batch_size

        if not trans_batch:
            _logger.debug("Пустая страница, пропускаем")
            continue

        # --- BATCH OPTIMIZATION ---
        
        # Сбор ID для проверки дублей
        batch_ext_ids = [str(t.get('ID')) for t in trans_batch if t.get('ID')]
        if not batch_ext_ids:
            _logger.warning("В пачке нет транзакций с ID, пропускаем")
            continue

        existing_recs = TransModel.search([
            ('bank_account_id', 'in', [a.id for a in local_accounts]), # Проверяем по всем счетам банка
            ('external_id', 'in', batch_ext_ids)
        ])
        existing_ids = {r.external_id for r in existing_recs}
        _logger.info(f"Найдено {len(existing_ids)} дубликатов в базе из {len(batch_ext_ids)} ID")

        vals_list = []
        batch_created = 0
        batch_skipped = 0
        batch_unknown = 0

        for t in trans_batch:
            # Проверка на дубликат
            ext_id = str(t.get('ID'))
            if ext_id in existing_ids:
                batch_skipped += 1
                continue

            # Определение счета Odoo
            # Приват возвращает AUT_MY_ACC - номер нашего счета в этой транзакции
            my_acc_num = t.get('AUT_MY_ACC')
            account = acc_map.get(my_acc_num)

            if not account:
                # Попробуем найти по IBAN из AUT_MY_IBAN (иногда бывает такое поле)
                alt_acc_num = t.get('AUT_MY_IBAN')
                if alt_acc_num:
                    account = acc_map.get(alt_acc_num)
                if not account:
                    _logger.warning(f"Не найден счет для транзакции {ext_id}: AUT_MY_ACC={my_acc_num}, AUT_MY_IBAN={alt_acc_num}")
                    batch_unknown += 1
                    unknown_acc_count += 1
                    continue

            # Логика знака (D - расход, C - приход)
            amount = float(t.get('SUM', 0))
            if t.get('TRANTYPE') == 'D':
                amount = -abs(amount)
            else:
                amount = abs(amount)

            # Парсинг даты
            date_val = _parse_privat_date(t.get('DAT_OD'), t.get('TIM_P'))
            if not date_val:
                date_val = _parse_privat_date(t.get('DAT_KL'))

            vals_list.append({
                'bank_account_id': account.id,
                'external_id': ext_id,
                'datetime': date_val,
                'amount': amount,
                'counterparty_name': t.get('AUT_CNTR_NAM'),
                'counterparty_edrpou': t.get('AUT_CNTR_CRF'),
                'counterparty_iban': t.get('AUT_CNTR_ACC'),
                'counterparty_bank_name': t.get('AUT_CNTR_MFO_NAME'),
                'counterparty_bank_city': t.get('AUT_CNTR_MFO_CITY'),
                'description': t.get('OSND') or t.get('REF'),  # Объединяем описание и реф
                'raw_data': str(t),  # Сохраняем сырой JSON для отладки
            })
            batch_created += 1

        if vals_list:
            TransModel.create(vals_list)
            total_created += batch_created
            _logger.info(f"   + Импортировано {batch_created} новых транзакций из пачки")
        else:
            _logger.info("   Нет новых транзакций для импорта в этой пачке")

        total_skipped += batch_skipped
        _logger.info(f"   Статистика пачки: создано {batch_created}, дубли {batch_skipped}, неизвестные счета {batch_unknown}")

    _logger.info(f"Итог импорта: обработано страниц {page_count}, транзакций из API {total_processed}, создано {total_created}, дубли {total_skipped}, неизвестные счета {unknown_acc_count}")

    return {
        'stats': {'created': total_created, 'skipped': total_skipped, 'unknown_accounts': unknown_acc_count}
    }


def import_privat_rates(bank, overwrite=True):
    """
    Импорт курсов покупки и продажи Приватбанка.
    Выполняется 3-4 раза в день с перезаписью курсов на текущую дату.
    """
    _logger.info("import_privat_rates: Starting PrivatBank exchange rates import")

    client = get_client(bank)

    try:
        data = client.fetch_exchange()
        _logger.info(f"import_privat_rates: Received {len(data) if data else 0} exchange rates")
    except Exception as e:
        _logger.error(f"import_privat_rates: Error fetching exchange rates: {e}")
        raise UserError(_("Ошибка получения курсов Приватбанка: %s") % e)

    if not data:
        _logger.warning("import_privat_rates: No exchange data received")
        return {'stats': {'created': 0, 'updated': 0, 'skipped': 0}}

    # Текущая дата для всех курсов (перезапись на текущий день)
    today = fields.Date.today()

    buy_rates_data = []
    sell_rates_data = []

    for item in data:
        ccy = item.get('ccy')  # базовая валюта (USD, EUR)
        base_ccy = item.get('base_ccy')  # валюта котировки (UAH)

        if base_ccy != 'UAH':
            continue  # Только курсы к UAH

        buy_rate = item.get('buy')
        sale_rate = item.get('sale')

        if not ccy or not buy_rate or not sale_rate:
            continue

        try:
            buy_val = float(buy_rate)
            sale_val = float(sale_rate)
        except (ValueError, TypeError):
            continue

        # Добавляем курс покупки
        buy_rates_data.append({
            'currency_code': ccy,
            'rate': buy_val,
            'date': today
        })

        # Добавляем курс продажи
        sell_rates_data.append({
            'currency_code': ccy,
            'rate': sale_val,
            'date': today
        })

    if not buy_rates_data and not sell_rates_data:
        _logger.warning("import_privat_rates: No valid rates to import")
        return {'stats': {'created': 0, 'updated': 0, 'skipped': 0}}

    # Импорт buy курсов
    buy_result = import_rates_to_dino(bank.env, buy_rates_data, 'privat', 'buy', overwrite)

    # Импорт sell курсов
    sell_result = import_rates_to_dino(bank.env, sell_rates_data, 'privat', 'sell', overwrite)

    # Объединяем результаты
    total_stats = {
        'buy_created': buy_result['stats']['created'],
        'buy_updated': buy_result['stats']['updated'],
        'buy_skipped': buy_result['stats']['skipped'],
        'sell_created': sell_result['stats']['created'],
        'sell_updated': sell_result['stats']['updated'],
        'sell_skipped': sell_result['stats']['skipped']
    }

    _logger.info(f"import_privat_rates: Import completed - Buy: {buy_result['stats']}, Sell: {sell_result['stats']}")

    return {'stats': total_stats}