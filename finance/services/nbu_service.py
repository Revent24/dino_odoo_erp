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


def import_nbu_rates(env, bank, start_date=None, end_date=None, overwrite=False):
    """
    Импортирует курсы из API НБУ в промежуточную таблицу `dino.currency.rate`.
    Возвращает список ID созданных/обновленных записей для последующей синхронизации.
    """
    if bank.mfo != '300001':
        raise UserError(_('Импорт поддерживается только для НБУ (МФО 300001).'))

    rate_model = env['dino.currency.rate']
    cur_model = env['res.currency']
    
    # 1. Определение диапазона дат
    today = fields.Date.context_today(bank)
    end = fields.Date.to_date(end_date or today)

    if start_date:
        start = fields.Date.to_date(start_date)
    elif bank.start_sync_date:
        start = fields.Date.to_date(bank.start_sync_date)
    else:
        # Инкрементальный режим по умолчанию: ищем последнюю запись
        last_rec = rate_model.search([('source', '=', 'nbu')], order='date desc', limit=1)
        start = last_rec.date + timedelta(days=1) if last_rec else (today - timedelta(days=30))

    if start > end:
        return {'stats': {}, 'processed_ids': []}

    # 2. Подготовка справочников (Кэширование)
    # Получаем все активные валюты сразу в словарь {code: currency_id}
    active_currencies = cur_model.search([('active', '=', True)])
    currency_map = {c.name.upper(): c.id for c in active_currencies if c.name != 'UAH'}

    # 3. Запрос к API
    client = NBUClient()
    try:
        data = client.fetch_exchange(start, end)
    except requests.RequestException as e:
        _logger.error("Ошибка API НБУ: %s", e)
        return {'error': str(e)}

    if not data:
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
        new_recs = rate_model.create(vals_list)
        processed_ids.extend(new_recs.ids)

    return {'stats': stats, 'processed_ids': processed_ids}


def sync_to_system_rates(env, source_ids=None, overwrite=False):
    """
    Переносит данные из dino.currency.rate в системную res.currency.rate.
    Оптимизация: синхронизирует только указанные ID (source_ids) или, если пусто, ничего.
    """
    if not source_ids:
        return {'created': 0, 'updated': 0, 'skipped': 0}

    dino_rate_model = env['dino.currency.rate']
    sys_rate_model = env['res.currency.rate']
    
    # Читаем только то, что изменилось/создалось
    rates_to_sync = dino_rate_model.browse(source_ids)
    if not rates_to_sync:
        return {}

    # Собираем даты и валюты для поиска существующих системных записей
    min_date = min(rates_to_sync.mapped('date'))
    max_date = max(rates_to_sync.mapped('date'))
    currency_ids = rates_to_sync.mapped('currency_id').ids

    # Загружаем существующие системные курсы в память
    existing_sys_rates = sys_rate_model.search([
        ('currency_id', 'in', currency_ids),
        ('name', '>=', min_date),
        ('name', '<=', max_date),
        ('company_id', '=', env.company.id) # Важно учитывать компанию
    ])
    
    # Карта: {(currency_id, date_str): sys_record}
    sys_map = {(r.currency_id.id, str(r.name)): r for r in existing_sys_rates}

    create_vals = []
    stats = {'created': 0, 'updated': 0, 'skipped': 0}

    for r in rates_to_sync:
        key = (r.currency_id.id, str(r.date))
        sys_rec = sys_map.get(key)
        
        # ВАЖНО: Odoo хранит курс как 1 / Rate (если база UAH).
        # НБУ дает прямые курсы (например 41.5).
        # Если в Odoo UAH - базовая (rate=1), то USD должен быть ~0.024.
        # ТУТ НУЖНО ПРОВЕРИТЬ ЛОГИКУ КОМПАНИИ. Пока копируем 1:1 как было в оригинале,
        # но обычно здесь нужно: final_rate = 1.0 / r.rate
        final_rate = r.rate 

        if sys_rec:
            if overwrite and abs(sys_rec.rate - final_rate) > 0.00001:
                sys_rec.rate = final_rate
                stats['updated'] += 1
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

    return stats


def run_sync(bank):
    """
    Точка входа для Диспетчера.
    """
    _logger.info("Запуск синхронизации НБУ для: %s", bank.name)
    
    # 1. Импорт в промежуточную таблицу
    import_res = import_nbu_rates(
        bank.env, 
        bank, 
        overwrite=getattr(bank, 'cron_overwrite_existing_rates', False)
    )
    
    if 'error' in import_res:
         raise UserError(_('Ошибка НБУ: %s') % import_res['error'])

    # 2. Синхронизация в систему (только то, что затронули)
    processed_ids = import_res.get('processed_ids', [])
    sync_stats = sync_to_system_rates(
        bank.env, 
        source_ids=processed_ids, 
        overwrite=getattr(bank, 'cron_overwrite_existing_rates', False)
    )

    # 3. Результат
    imp_stats = import_res.get('stats', {})
    
    msg = _("НБУ Импорт: Создано %d, Обновлено %d. Системные курсы: Создано %d, Обновлено %d.") % (
        imp_stats.get('created', 0), imp_stats.get('updated', 0),
        sync_stats.get('created', 0), sync_stats.get('updated', 0)
    )

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'title': _('Синхронизация завершена'), 'message': msg, 'sticky': False}
    }
