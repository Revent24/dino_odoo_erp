# -*- coding: utf-8 -*-
import requests
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Простой in-memory кэш списка банков НБУ
_NBU_BANKS_CACHE = {
    'ts': None,  # datetime (UTC)
    'banks': []
}

# ---------------------------------------------------------------------------
# ВНИМАНИЕ ДЛЯ РАЗРАБОТЧИКОВ (рус.):
# Этот файл содержит модель `dino.bank` и совмещает несколько зон ответственности:
# - объявление полей модели (attributes / fields)
# - валидации и onchange-методы
# - вспомогательные NBU функции (_fetch_nbu_banks, _onchange_mfo)
# - методы оркестрации (fetch_rates) и UI-обработчики кнопок
# - логика импорта/синхронизации курсов (частично вынесена в services/nbu_service.py)
#
# Рекомендации по структуре:
# 1) Оставлять в этом файле только *поля* модели и минимальные thin-обёртки для UI.
# 2) Логику планирования/cron держать в `dino_bank_cron.py` (_inherit = 'dino.bank').
# 3) HTTP-клиенты и парсинг вынести в `finance/services/*` (nbu_client, privat_client и т.д.).
# 4) Высокоуровневую бизнес-логику импорта/синхронизации держать в services (nbu_service). Это уже частично сделано.
# 5) Постепенно переместить `sync_to_system_rates`, `_fetch_nbu_banks` и `_onchange_mfo` в соответствующие сервисы/клиенты.
#
# TODOs (быстрый план):
# - [ ] Перенести _fetch_nbu_banks -> nbu_client.get_banks (выполнено? проверить дупликаты).
# - [ ] Перенести _onchange_mfo http lookup -> nbu_client (оставить thin onchange, делегирующий вызов).
# - [ ] Перенести sync_to_system_rates -> nbu_service (и оставить thin wrapper здесь).
# - [ ] Добавить unit-тесты для nbu_client и nbu_service.
#
# Комментарии: пока что некоторые методы уже делегируют в services (import_nbu_rates/import_and_sync_nbu).
# Оставляйте изменения небольшими и проверяйте поведение через обновление модуля и smoke-тесты.
# ---------------------------------------------------------------------------

class DinoBank(models.Model):
    _name = 'dino.bank'
    _description = _('Bank Directory')
    _order = 'name'

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Структура / Поля
    # ------------------------------------------------------------------
    # Основные поля модели
    name = fields.Char(string=_('Name'), required=True, index=True)
    mfo = fields.Char(string=_('MFO'), size=6, index=True)
    edrpou = fields.Char(string=_('EDRPOU'), index=True)

    # --- API Credentials ---
    api_client_id = fields.Char(string=_('API Client ID'))
    api_key = fields.Char(string=_('API Key / Token'), password=True)

    # Common fields
    active = fields.Boolean(string=_('Active'), default=True)

    # Информация об обновлениях/синхронизации
    last_sync_date = fields.Datetime(string=_('Last sync'))
    start_sync_date = fields.Date(string=_('Start Date'))
    cron_overwrite_existing_rates = fields.Boolean(
        string=_('Overwrite Existing'), default=False,
        help="If true, scheduled imports will overwrite existing notes.")

    # Per-bank cron configuration (displayed on API tab)
    cron_enable = fields.Boolean(
        string=_('Enable Cron'), default=False,
        help="If true, a per-bank scheduled job can be configured (informational only).")
    cron_interval_number = fields.Integer(
        string=_('Interval Number'), default=1,
        help="Interval count for the scheduled job (e.g., 1 day).")
    cron_interval_type = fields.Selection([
        ('minutes', _('Minutes')),
        ('hours', _('Hours')),
        ('days', _('Days')),
        ('weeks', _('Weeks')),
        ('months', _('Months')),
    ], string=_('Interval Type'), default='days')
    cron_nextcall = fields.Datetime(string=_('Next Call'), help="Date/time for the next scheduled run.")
    cron_numbercall = fields.Integer(string=_('Max Calls'), default=-1, help='Maximum number of calls (-1 = unlimited).')
    # Время дня в часах (float, например 3.5 = 03:30). Для UI использовать виджет float_time.
    cron_time_of_day_hours = fields.Float(
        string=_('Time of Day (hours)'),
        help="Optional. Time of day for daily/weekly runs as decimal hours (e.g., 3.5 = 03:30).")

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Ограничения и обработчики onchange
    # ------------------------------------------------------------------
    # Проверка целостности: cron_interval_number должно быть положительным
    @api.constrains('cron_interval_number')
    def _check_cron_interval_number(self):
        """Validate that cron interval number is positive."""
        for rec in self:
            if rec.cron_interval_number is None:
                continue
            if rec.cron_interval_number <= 0:
                raise UserError(_('Cron Interval Number must be a positive integer.'))

    # Проверка целостности: cron_time_of_day_hours должно быть пустым или в диапазоне 0.0–23.99
    @api.constrains('cron_time_of_day_hours')
    def _check_cron_time_hours_range(self):
        """Validate cron_time_of_day_hours is either empty or 0 <= value < 24."""
        for rec in self:
            if rec.cron_time_of_day_hours is None:
                continue
            try:
                val = float(rec.cron_time_of_day_hours)
            except Exception:
                raise UserError(_('Cron Time of Day must be a number representing hours (e.g., 3.5 = 03:30).'))
            if not (0 <= val < 24):
                raise UserError(_('Cron Time of Day must be between 0.0 and 23.99 hours.'))

    # Onchange: при смене типа интервала очищаем поле времени дня для minute/hours
    @api.onchange('cron_interval_type')
    def _onchange_cron_interval_type(self):
        """Clear time-of-day when interval is minutes/hours since it's irrelevant then."""
        for rec in self:
            try:
                if rec.cron_interval_type in ('minutes', 'hours') and rec.cron_time_of_day_hours:
                    rec.cron_time_of_day_hours = False
                    return {
                        'warning': {
                            'title': _('Cron Time cleared'),
                            'message': _('Time of Day is ignored for minute/hour intervals and was cleared.')
                        }
                    }
            except Exception:
                # do not block saving on unexpected errors
                _logger.exception('Error in onchange_cron_interval_type for bank %s', getattr(rec, 'id', 'unknown'))
        return {}

    # Onchange: при изменении MFO выполняем lookup в справочнике НБУ и заполняем name/edrpou
    @api.onchange('mfo')
    def _onchange_mfo(self):
        """Lookup bank info from NBU by specific MFO (glmfo) on change.

        Uses the endpoint `get_data_branch?glmfo=<MFO>&json` and maps common keys.
        Returns a warning dict on failure instead of raising exceptions.
        """
        if not self.mfo:
            return
        mfo_str = str(self.mfo).strip()
        if len(mfo_str) != 6:
            return {
                'warning': {
                    'title': _('Invalid MFO'),
                    'message': _('MFO must be 6 characters long.')
                }
            }
        url = f'https://bank.gov.ua/NBU_BankInfo/get_data_branch?glmfo={mfo_str}&json'
        headers = {'Accept': 'application/json', 'User-Agent': 'DinoERP/1.0'}
        try:
            resp = requests.get(url, timeout=10, headers=headers)
            if resp.status_code == 400:
                # запасной вариант: тот же endpoint без параметра json
                alt_url = f'https://bank.gov.ua/NBU_BankInfo/get_data_branch?glmfo={mfo_str}'
                resp = requests.get(alt_url, timeout=10, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return {
                    'warning': {
                        'title': _('Bank not found'),
                        'message': _('No data returned for MFO %s') % mfo_str
                    }
                }
            # data — список записей; предпочитаем запись с TYP == 0
            record = None
            for r in data:
                try:
                    typ = str(r.get('TYP', '')).strip()
                except Exception:
                    typ = ''
                if typ == '0' and str(r.get('GLMFO') or r.get('MFO') or '').strip() == mfo_str:
                    record = r
                    break
            if not record:
                # запасной вариант: первая запись с совпадающим MFO/GLMFO
                record = next((r for r in data if str(r.get('GLMFO') or r.get('MFO') or '').strip() == mfo_str), None)
            if not record:
                # в крайнем случае используем первый элемент
                record = data[0]
            name = record.get('N_GOL') or record.get('SHORTNAME') or record.get('FULLNAME') or record.get('NAME_E') or self.name
            edrpou = record.get('KOD_EDRPOU') or record.get('kod_edrpou') or self.edrpou
            self.name = name
            self.edrpou = edrpou
        except requests.RequestException as e:
            _logger.warning('NBU glmfo lookup failed for %s: %s', mfo_str, e)
            return {
                'warning': {
                    'title': _('NBU lookup failed'),
                    'message': _('Could not fetch bank data for MFO %s: %s') % (mfo_str, e)
                }
            }

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Вспомогательное / HTTP-утилиты (кандидат на перенос в services)
    # ------------------------------------------------------------------
    # Вспомогательная функция: получить и кэшировать список банков НБУ
    def _fetch_nbu_banks(self, refresh=False):
        """Fetch (and cache) list of banks from NBU. Returns list of bank dicts."""
        cache_ttl = timedelta(hours=24)
        now = datetime.utcnow()
        if not refresh and _NBU_BANKS_CACHE['ts'] and (now - _NBU_BANKS_CACHE['ts']) < cache_ttl:
            return _NBU_BANKS_CACHE['banks']

        urls = [
            'https://bank.gov.ua/NBUStatService/v1/statdirectory/banks?json',
            'https://bank.gov.ua/NBUStatService/v1/statdirectory/banks'
        ]
        headers = {'Accept': 'application/json', 'User-Agent': 'DinoERP/1.0'}
        banks = []
        for url in urls:
            try:
                resp = requests.get(url, timeout=10, headers=headers)
                if resp.status_code == 400:
                    # пробуем следующий URL
                    continue
                resp.raise_for_status()
                banks = resp.json()
                break
            except requests.RequestException as e:
                _logger.warning('NBU banks lookup failed for url %s: %s', url, e)
                continue

        # обновляем кэш (даже если пустой, чтобы избежать частых повторов)
        _NBU_BANKS_CACHE['ts'] = now
        _NBU_BANKS_CACHE['banks'] = banks
        return banks

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Оркестрация / Точки входа планировщика (cron)
    # ------------------------------------------------------------------
    # Оркестрационная точка входа: запуск fetch для банка; для НБУ делегирует импорт/синхронизацию
    def fetch_rates(self):
        """Stub: implement per-bank fetch logic (kept for compatibility).
        For NBU (mfo=300001) this will import exchange rates if called explicitly."""
        _logger.info('Fetching rates for bank %s (%s)', self.id, self.name)
        self.last_sync_date = fields.Datetime.now()
        # If this is NBU, delegate to import_nbu_rates incrementally for missing dates
        for rec in self:
            if rec.mfo == '300001':
                rate_model = self.env['dino.currency.rate']
                last = rate_model.search([('source', '=', 'nbu')], order='date desc', limit=1)
                start_date_import = rec.start_sync_date
                if last and last.date:
                    start_date_import = max(start_date_import, last.date + timedelta(days=1))
                # убедиться, что start_date задана и <= сегодняшней даты
                if start_date_import:
                    try:
                        rec.import_and_sync_nbu(start_date=start_date_import, to_date=fields.Date.context_today(rec), overwrite=rec.cron_overwrite_existing_rates)
                    except UserError as e:
                        _logger.error('Error during scheduled NBU import+sync for bank %s: %s', rec.id, e)
                else:
                    _logger.warning('Skipping scheduled NBU import for bank %s: start date not configured.', rec.id)
        return True

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Высокоуровневые делегаты импорта/синхронизации НБУ (использовать services)
    # ------------------------------------------------------------------
    # Делегат: импорт курсов НБУ через сервис nbu_service
    def import_nbu_rates(self, to_date=None, overwrite=False, start_date=None):
        """Delegate to NBU service implementation."""
        from ..services.nbu_service import import_nbu_rates as _import_nbu_rates
        rec = self and self[0]
        return _import_nbu_rates(self.env, rec, to_date=to_date, overwrite=overwrite, start_date=start_date)

    # Делегат: однопроходный импорт и синхронизация НБУ через сервис nbu_service
    def import_and_sync_nbu(self, overwrite=False):
        """Delegate to NBU service single-pass import+sync."""
        from ..services.nbu_service import import_and_sync_nbu as _import_and_sync_nbu
        rec = self and self[0]
        return _import_and_sync_nbu(self.env, rec, overwrite=overwrite)

    # Синхронизация: перенос/обновление курсов из dino.currency.rate (source='nbu') в res.currency.rate
    def sync_to_system_rates(self, overwrite=False):
        """Sync existing `dino.currency.rate` (source='nbu') into system `res.currency.rate`.

        By default does not overwrite existing `res.currency.rate` entries. Returns stats dict.
        """
        rate_model = self.env['dino.currency.rate']
        sys_rate = self.env['res.currency.rate']
        created = 0
        updated = 0
        skipped = 0
        details = []
        # учитывать только активные валюты в res.currency (исключая UAH)
        active_currencies = self.env['res.currency'].search([('active', '=', True)])
        active_map = {c.name.upper(): c for c in active_currencies}
        active_map.pop('UAH', None)
        # выбрать все курсы НБУ для этих валют
        nbu_rates = rate_model.search([('source', '=', 'nbu')], order='date asc')
        for r in nbu_rates:
            code = r.currency_id.name.upper() if r.currency_id else None
            if not code or code not in active_map:
                skipped += 1
                details.append((str(r.date), code or 'NONE', 'currency_not_active_or_missing'))
                continue
            currency = active_map[code]
            # проверить, существует ли системный курс на ту же дату и для той же валюты
            exists = sys_rate.search([('currency_id', '=', currency.id), ('name', '=', r.date),], limit=1)
            # Примечание: в Odoo `res.currency.rate` поле 'name' часто используется для даты (Char/Date). Используем поле даты, если доступно.
            # Для идемпотентности предпочитаем искать по 'currency_id' и 'name' (строка даты).
            if exists:
                if overwrite:
                    exists.rate = r.rate
                    updated += 1
                    details.append((str(r.date), code, 'updated'))
                else:
                    skipped += 1
                    details.append((str(r.date), code, 'exists'))
            else:
                # создать запись системного курса
                # Подобрать подходящие поля для res.currency.rate (разные версии Odoo)
                vals = {
                    'currency_id': currency.id,
                    'rate': r.rate,
                }
                # поле name может быть строкой даты или Date — попробуем задать 'name'; company_id оставляем пустым
                try:
                    vals['name'] = r.date
                except Exception:
                    vals['name'] = str(r.date)
                sys_rate.create(vals)
                created += 1
                details.append((str(r.date), code, 'created'))
        _logger.info('Sync to system rates finished: created=%s updated=%s skipped=%s', created, updated, skipped)
        return {'created': created, 'updated': updated, 'skipped': skipped, 'details': details}

    # ------------------------------------------------------------------
    # РАЗДЕЛ: UI-обработчики (кнопки)
    # ------------------------------------------------------------------
    def button_sync(self):
        """
        Universal synchronization button.
        This method delegates the actual sync logic to the dispatcher in services.
        """
        from ..services import bank_dispatcher
        return bank_dispatcher.dispatch_sync(self)


