# -*- coding: utf-8 -*-
"""finance/services/nbu_service.py

Высокоуровневый сервис НБУ.
Оптимизирован для пакетной обработки данных (Batch Processing) для исключения проблемы N+1.
"""
import logging
from datetime import datetime, timedelta
from odoo import fields, _
from odoo.exceptions import UserError
import requests

from .nbu_client import NBUClient

_logger = logging.getLogger(__name__)


def import_nbu_rates(env, bank=None, start_date=None, end_date=None, overwrite=False):
    """
    Импортирует курсы из API НБУ в промежуточную таблицу `dino.currency.rate`.
    Возвращает список ID созданных/обновленных записей для последующей синхронизации.
    """
    _logger.warning(f"import_nbu_rates: Starting import")
    rate_model = env['dino.currency.rate']
    cur_model = env['res.currency']
    _logger.warning(f"import_nbu_rates: Using rate_model={rate_model._name}, cur_model={cur_model._name}")

    # 1. Определение диапазона дат
    today = fields.Date.context_today(env.user) if env.user else fields.Date.today()
    _logger.warning(f"import_nbu_rates: Today = {today}")
    end = fields.Date.to_date(end_date or today)
    _logger.warning(f"import_nbu_rates: End date = {end}")

    if start_date:
        start = fields.Date.to_date(start_date)
        _logger.warning(f"import_nbu_rates: Start date from param = {start}")
    else:
        # Инкрементальный режим по умолчанию: ищем последнюю запись
        last_rec = rate_model.search([('source', '=', 'nbu')], order='date desc', limit=1)
        _logger.warning(f"import_nbu_rates: Last NBU record = {last_rec.date if last_rec else 'None'}")
        start = last_rec.date + timedelta(days=1) if last_rec else (today - timedelta(days=30))
        _logger.warning(f"import_nbu_rates: Calculated start date = {start}")

    if start > end:
        return {'stats': {}, 'processed_ids': []}

    # 2. Подготовка справочников (Кэширование)
    # Получаем все активные валюты сразу в словарь {code: currency_id}
    active_currencies = cur_model.search([('active', '=', True)])
    currency_map = {c.name.upper(): c.id for c in active_currencies if c.name != 'UAH'}

    # 3. Запрос к API
    _logger.warning(f"import_nbu_rates: Fetching data from NBU API for period {start} to {end}")
    client = NBUClient()
    try:
        data = client.fetch_exchange(start, end)
        _logger.warning(f"import_nbu_rates: Received {len(data) if data else 0} records from NBU API")
        if data:
            _logger.warning(f"import_nbu_rates: Sample data: {data[:2]}")
    except requests.RequestException as e:
        _logger.error("Ошибка API НБУ: %s", e)
        return {'error': str(e)}

    if not data:
        _logger.warning("import_nbu_rates: No data received from NBU API")
        return {'stats': {'skipped': 0}, 'processed_ids': []}

    # 4. Пакетная проверка существования (Batch Existence Check)
    # Вместо search внутри цикла, достаем все записи за этот период сразу
    existing_rates = rate_model.search([
        ('source', '=', 'nbu'),
        ('date', '>=', start),
        ('date', '<=', end)
    ])
    # Создаем карту: {(currency_id, date_str): record_object}
    existing_map = {(r.currency_id.id, str(r.date)): r for r in existing_rates}

    vals_list = []
    stats = {'created': 0, 'updated': 0, 'skipped': 0}
    processed_ids = []

    # 5. Обработка данных
    for item in data:
        code = item.get('cc')
        date_str = item.get('exchangedate')  # Формат API обычно dd.mm.yyyy

        if not code or code not in currency_map:
            continue
            
        # Преобразование даты (dd.mm.yyyy -> yyyy-mm-dd)
        try:
            date_obj = datetime.strptime(date_str, '%d.%m.%Y').date()
            date_iso = fields.Date.to_string(date_obj)
        except (ValueError, TypeError):
            stats['skipped'] += 1
            continue

        curr_id = currency_map[code]
        rate_val = item.get('rate') # НБУ дает курс за единицу (обычно)

        # Проверяем по словарю (в памяти, быстро)
        existing_rec = existing_map.get((curr_id, date_iso))

        if existing_rec:
            if overwrite and existing_rec.rate != rate_val:
                existing_rec.rate = rate_val
                stats['updated'] += 1
                processed_ids.append(existing_rec.id)
            else:
                stats['skipped'] += 1
        else:
            vals_list.append({
                'name': f"NBU {code} {date_iso}",
                'currency_id': curr_id,
                'rate': rate_val,
                'date': date_iso,
                'source': 'nbu'
            })
            stats['created'] += 1

    # 6. Массовое создание
    if vals_list:
        _logger.warning(f"import_nbu_rates: Creating {len(vals_list)} new rate records")
        new_recs = rate_model.create(vals_list)
        processed_ids.extend(new_recs.ids)
        _logger.warning(f"import_nbu_rates: Created {len(new_recs)} records with IDs: {new_recs.ids}")
    else:
        _logger.warning("import_nbu_rates: No new records to create")

    _logger.warning(f"import_nbu_rates: Final stats - Created: {stats['created']}, Updated: {stats['updated']}, Skipped: {stats['skipped']}")
    return {'stats': stats, 'processed_ids': processed_ids}


def sync_rates_to_system(env, domain=None, overwrite=False):
    """
    Универсальная синхронизация курсов из dino.currency.rate в res.currency.rate

    domain: домен для поиска курсов в dino.currency.rate (например, [('source', '=', 'nbu'), ('rate_type', '=', 'official')])
    overwrite: перезаписывать существующие системные курсы

    Возвращает: {'created': N, 'updated': N, 'skipped': N}
    """
    if not domain:
        return {'created': 0, 'updated': 0, 'skipped': 0}

    dino_rate_model = env['dino.currency.rate']
    sys_rate_model = env['res.currency.rate']

    # Находим курсы для синхронизации
    rates_to_sync = dino_rate_model.search(domain)
    if not rates_to_sync:
        return {'created': 0, 'updated': 0, 'skipped': 0}

    _logger.info(f"sync_rates_to_system: Syncing {len(rates_to_sync)} rates from dino to system")

    # Собираем даты и валюты для поиска существующих системных записей
    dates = rates_to_sync.mapped('date')
    currency_ids = rates_to_sync.mapped('currency_id').ids

    # Загружаем существующие системные курсы
    existing_sys_rates = sys_rate_model.search([
        ('currency_id', 'in', currency_ids),
        ('name', 'in', [str(d) for d in dates]),
        ('company_id', '=', env.company.id)
    ])

    # Карта существующих системных курсов: {(currency_id, date_str): sys_record}
    sys_map = {(r.currency_id.id, str(r.name)): r for r in existing_sys_rates}

    create_vals = []
    stats = {'created': 0, 'updated': 0, 'skipped': 0}

    for r in rates_to_sync:
        key = (r.currency_id.id, str(r.date))
        sys_rec = sys_map.get(key)

        # Расчет курса для Odoo (обратный для базовой валюты UAH)
        base_currency = env.company.currency_id
        if base_currency.name == 'UAH':
            final_rate = 1.0 / r.rate if r.rate != 0 else 0
        else:
            final_rate = r.rate

        if sys_rec:
            if overwrite and abs(sys_rec.rate - final_rate) > 0.00001:
                sys_rec.rate = final_rate
                stats['updated'] += 1
                _logger.info(f"sync_rates_to_system: Updated {r.currency_id.name} {r.date}: {final_rate}")
            else:
                stats['skipped'] += 1
        else:
            create_vals.append({
                'currency_id': r.currency_id.id,
                'rate': final_rate,
                'name': r.date,
                'company_id': env.company.id
            })
            stats['created'] += 1

    if create_vals:
        sys_rate_model.create(create_vals)
        _logger.info(f"sync_rates_to_system: Created {len(create_vals)} system rates")

    _logger.info(f"sync_rates_to_system: Final stats - Created: {stats['created']}, Updated: {stats['updated']}, Skipped: {stats['skipped']}")
    return stats


def sync_to_system_rates(env, source_ids=None, overwrite=False):
    """
    Устаревшая функция для совместимости - синхронизирует по ID.
    """
    if not source_ids:
        return {'created': 0, 'updated': 0, 'skipped': 0}

    dino_rate_model = env['dino.currency.rate']
    rates_to_sync = dino_rate_model.browse(source_ids)

    # Создаем домен на основе найденных записей
    if rates_to_sync:
        domain = [('id', 'in', source_ids)]
        return sync_rates_to_system(env, domain, overwrite)

    return {'created': 0, 'updated': 0, 'skipped': 0}


def import_rates_to_dino(env, rates_data, source, rate_type='official', overwrite=False):
    """
    Универсальный импорт курсов в dino.currency.rate

    rates_data: список словарей [{'currency_code': 'USD', 'rate': 36.5, 'date': '2023-01-01'}, ...]
    source: 'nbu', 'privat', 'mono'
    rate_type: 'official', 'buy', 'sell'
    overwrite: перезаписывать существующие записи

    Возвращает: {'stats': {'created': N, 'updated': N, 'skipped': N}, 'processed_ids': [...]}
    """
    if not rates_data:
        return {'stats': {'created': 0, 'updated': 0, 'skipped': 0}, 'processed_ids': []}

    _logger.warning(f"import_rates_to_dino: Starting import {len(rates_data)} rates from {source} type {rate_type}")

    rate_model = env['dino.currency.rate']
    cur_model = env['res.currency']

    # Подготовка валют
    active_currencies = cur_model.search([('active', '=', True)])
    currency_map = {c.name.upper(): c.id for c in active_currencies}

    # Проверка существования (batch check)
    # Собираем уникальные комбинации для поиска
    search_domains = []
    for item in rates_data:
        curr_code = item['currency_code'].upper()
        date_str = item['date']
        if curr_code in currency_map:
            search_domains.append(('currency_id', '=', currency_map[curr_code]))
            search_domains.append(('date', '=', date_str))
            search_domains.append(('source', '=', source))
            search_domains.append(('rate_type', '=', rate_type))

    existing_rates = rate_model.search(search_domains) if search_domains else rate_model.browse()
    existing_map = {(r.currency_id.name.upper(), str(r.date), r.source, r.rate_type): r for r in existing_rates}

    vals_list = []
    stats = {'created': 0, 'updated': 0, 'skipped': 0}
    processed_ids = []

    for item in rates_data:
        curr_code = item['currency_code'].upper()
        rate_val = item['rate']
        date_str = item['date']

        if curr_code not in currency_map:
            stats['skipped'] += 1
            continue

        curr_id = currency_map[curr_code]
        key = (curr_code, date_str, source, rate_type)

        existing_rec = existing_map.get(key)

        if existing_rec:
            if overwrite and abs(existing_rec.rate - rate_val) > 0.00001:
                existing_rec.rate = rate_val
                stats['updated'] += 1
                processed_ids.append(existing_rec.id)
                _logger.info(f"import_rates_to_dino: Updated {source} {rate_type} {curr_code} {date_str}: {rate_val}")
            else:
                stats['skipped'] += 1
        else:
            vals_list.append({
                'name': f"{source.upper()} {rate_type} {curr_code} {date_str}",
                'currency_id': curr_id,
                'rate': rate_val,
                'date': date_str,
                'source': source,
                'rate_type': rate_type
            })
            stats['created'] += 1

    # Массовое создание
    if vals_list:
        _logger.warning(f"import_rates_to_dino: Creating {len(vals_list)} new rate records")
        new_recs = rate_model.create(vals_list)
        processed_ids.extend(new_recs.ids)
        _logger.warning(f"import_rates_to_dino: Created {len(new_recs)} records")

    _logger.warning(f"import_rates_to_dino: Final stats - Created: {stats['created']}, Updated: {stats['updated']}, Skipped: {stats['skipped']}")
    return {'stats': stats, 'processed_ids': processed_ids}


def import_nbu_rates(env, bank=None, start_date=None, end_date=None, overwrite=False):
    """
    Импортирует курсы из API НБУ в основную таблицу dino.currency.rate с rate_type='official'.
    Возвращает список ID созданных/обновленных записей для последующей синхронизации.
    """
    _logger.warning("import_nbu_rates: Starting import to dino.currency.rate")

    # 1. Определение диапазона дат
    today = fields.Date.context_today(env.user) if env.user else fields.Date.today()
    _logger.warning(f"import_nbu_rates: Today = {today}")
    end = fields.Date.to_date(end_date or today)
    _logger.warning(f"import_nbu_rates: End date = {end}")

    if start_date:
        start = fields.Date.to_date(start_date)
        _logger.warning(f"import_nbu_rates: Start date from param = {start}")
    elif bank and bank.start_sync_date:
        start = fields.Date.to_date(bank.start_sync_date)
        _logger.warning(f"import_nbu_rates: Start date from bank = {start}")
    else:
        # Инкрементальный режим по умолчанию: ищем последнюю запись NBU
        last_rec = env['dino.currency.rate'].search([('source', '=', 'nbu'), ('rate_type', '=', 'official')], order='date desc', limit=1)
        _logger.warning(f"import_nbu_rates: Last NBU record = {last_rec.date if last_rec else 'None'}")
        start = last_rec.date + timedelta(days=1) if last_rec else (today - timedelta(days=30))
        _logger.warning(f"import_nbu_rates: Calculated start date = {start}")

    if start > end:
        return {'stats': {}, 'processed_ids': []}

    # 2. Запрос к API
    _logger.warning(f"import_nbu_rates: Fetching data from NBU API for period {start} to {end}")
    client = NBUClient()
    try:
        data = client.fetch_exchange(start, end)
        _logger.warning(f"import_nbu_rates: Received {len(data) if data else 0} records from NBU API")
        if data:
            _logger.warning(f"import_nbu_rates: Sample data: {data[:2]}")
    except requests.RequestException as e:
        _logger.error("Ошибка API НБУ: %s", e)
        return {'error': str(e)}

    if not data:
        _logger.warning("import_nbu_rates: No data received from NBU API")
        return {'stats': {'skipped': 0}, 'processed_ids': []}

    # 3. Преобразование данных для универсальной функции
    rates_data = []
    for item in data:
        code = item.get('cc')
        date_str = item.get('exchangedate')
        rate_val = item.get('rate')

        if not code or not date_str or rate_val is None:
            continue

        try:
            date_obj = datetime.strptime(date_str, '%d.%m.%Y').date()
            date_iso = fields.Date.to_string(date_obj)
        except (ValueError, TypeError):
            continue

        rates_data.append({
            'currency_code': code,
            'rate': rate_val,
            'date': date_iso
        })

    # 4. Импорт через универсальную функцию
    return import_rates_to_dino(env, rates_data, 'nbu', 'official', overwrite)


def run_sync(env, bank=None):
    """
    Импорт курсов НБУ в dino.currency.rate и синхронизация в res.currency.rate
    """
    _logger.warning("run_sync: Starting NBU import and sync")

    # 1. Импорт в основную таблицу
    _logger.warning("run_sync: Starting import to dino.currency.rate")
    import_res = import_nbu_rates(env, bank, overwrite=False)
    _logger.warning(f"run_sync: Import result: {import_res}")

    if 'error' in import_res:
        _logger.error(f"run_sync: Import failed with error: {import_res['error']}")
        raise UserError(_('Ошибка НБУ: %s') % import_res['error'])

    # 2. Синхронизация в систему всех NBU official курсов
    _logger.warning("run_sync: Syncing NBU official rates to system")
    sync_domain = [('source', '=', 'nbu'), ('rate_type', '=', 'official')]
    sync_stats = sync_rates_to_system(
        env,
        domain=sync_domain,
        overwrite=getattr(bank, 'cron_overwrite_existing_rates', False) if bank else False
    )
    _logger.warning(f"run_sync: Sync stats: {sync_stats}")

    import_stats = import_res.get('stats', {})
    return {
        'stats': import_stats,
        'sync_stats': sync_stats
    }
