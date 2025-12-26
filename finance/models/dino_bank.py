# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ВНИМАНИЕ ДЛЯ РАЗРАБОТЧИКОВ (рус.):
# Этот файл содержит модель `dino.bank` и теперь содержит только:
# - объявление полей модели (attributes / fields)
# - валидации и onchange-методы (thin wrappers для сервисов)
# - UI-обработчики кнопок
#
# Рекомендации по структуре выполнены:
# 1) Оставлены только поля модели и минимальные thin-обёртки для UI.
# 2) Логика планирования/cron вынесена в `dino_bank_cron.py` (_inherit = 'dino.bank').
# 3) HTTP-клиенты и парсинг вынесены в `finance/services/*` (nbu_client, privat_client и т.д.).
# 4) Высокоуровневая бизнес-логика импорта/синхронизации держится в services (nbu_service).
# 5) Перемещены `sync_to_system_rates`, `_fetch_nbu_banks` и `_onchange_mfo` в соответствующие сервисы/клиенты.
#
# TODOs (быстрый план):
# - [x] Перенести _fetch_nbu_banks -> nbu_client.get_banks (выполнено? проверить дупликаты). -> Удалено, дублируется с nbu_client.get_banks
# - [x] Перенести _onchange_mfo http lookup -> nbu_client (оставить thin onchange, делегирующий вызов). -> Выполнено
# - [x] Перенести sync_to_system_rates -> nbu_service (и оставить thin wrapper здесь). -> Выполнено, добавлен sync_to_system_rates в nbu_service
# - [ ] Добавить unit-тесты для nbu_client и nbu_service.
# - [x] Максимально очистить файл модели согласно плану -> Выполнено
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
    # Use Text to allow arbitrarily long API tokens; remove password widget for now
    api_key = fields.Text(string=_('API Key / Token'), encrypted=True)

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

    # Smart button / indicators
    account_count = fields.Integer(string=_('Accounts'), compute='_compute_account_count')

    @api.depends()
    def _compute_account_count(self):
        for rec in self:
            rec.account_count = self.env['dino.bank.account'].search_count([('bank_id', '=', rec.id)])

    def action_view_accounts(self):
        self.ensure_one()
        return {
            'name': _('Bank Accounts'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.bank.account',
            'view_mode': 'list,form',
            'domain': [('bank_id', '=', self.id)],
            'context': {'default_bank_id': self.id},
        }

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

        Thin wrapper delegating to nbu_client.get_bank_info.
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
        from ..services.nbu_client import NBUClient
        client = NBUClient()
        try:
            data = client.get_bank_info(mfo_str)
            if not data:
                return {
                    'warning': {
                        'title': _('Bank not found'),
                        'message': _('No data returned for MFO %s') % mfo_str
                    }
                }
            # Предпочитаем запись с TYP == '0'
            record = next((r for r in data if str(r.get('TYP', '')).strip() == '0' and str(r.get('GLMFO') or r.get('MFO') or '').strip() == mfo_str), None)
            if not record:
                record = next((r for r in data if str(r.get('GLMFO') or r.get('MFO') or '').strip() == mfo_str), data[0] if data else None)
            if record:
                self.name = record.get('N_GOL') or record.get('SHORTNAME') or record.get('FULLNAME') or record.get('NAME_E') or self.name
                self.edrpou = record.get('KOD_EDRPOU') or record.get('kod_edrpou') or self.edrpou
        except Exception as e:
            _logger.warning('NBU glmfo lookup failed for %s: %s', mfo_str, e)
            return {
                'warning': {
                    'title': _('NBU lookup failed'),
                    'message': _('Could not fetch bank data for MFO %s: %s') % (mfo_str, e)
                }
            }

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Высокоуровневые делегаты импорта/синхронизации НБУ (использовать services)
    # ------------------------------------------------------------------
    # Делегат: импорт курсов НБУ через сервис nbu_service
    def import_nbu_rates(self, to_date=None, overwrite=False, start_date=None):
        """Delegate to NBU service implementation."""
        from ..services.nbu_service import import_nbu_rates as _import_nbu_rates
        rec = self and self[0]
        return _import_nbu_rates(self.env, rec, to_date=to_date, overwrite=overwrite, start_date=start_date)

    # ------------------------------------------------------------------
    # РАЗДЕЛ: UI-обработчики (кнопки)
    # ------------------------------------------------------------------
    def button_sync(self):
        """
        Universal synchronization button.
        """
        from ..services import bank_dispatcher
        return bank_dispatcher.dispatch_sync(self)

    def button_import_and_sync(self, overwrite=False):
        """UI button wrapper to import and sync NBU rates and return a notification action.

        This method keeps compatibility with older code paths that expect
        `button_import_and_sync` to exist on the `dino.bank` model.
        """
        self.ensure_one()
        _logger.info(f"Запуск button_import_and_sync для банка {self.name} (MFO: {self.mfo})")
        if self.mfo == '300001':
            from ..services.nbu_service import run_sync
            result = run_sync(self)
        else:
            # Для других банков (Privat) используем dispatcher
            from ..services.bank_dispatcher import run_sync
            result = run_sync(self)
        _logger.info(f"Результат импорта: {result}")
        # Отправляем уведомление пользователю
        if result and 'stats' in result:
            stats = result['stats']
            message = f"Импорт завершен: создано {stats.get('created', 0)}, пропущено {stats.get('skipped', 0)}"
            if 'unknown_accounts' in stats:
                message += f", неизвестные счета {stats['unknown_accounts']}"
            self.env['bus.bus'].sendone(
                f'notify_{self.env.user.id}',
                {
                    'type': 'simple_notification',
                    'title': 'Импорт транзакций',
                    'message': message,
                    'sticky': False,
                }
            )
        return result