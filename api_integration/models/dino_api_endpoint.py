#
#  -*- File: api_integration/models/dino_api_endpoint.py -*-
#
#
#  -*- File: api_integration/models/dino_api_endpoint.py -*-
#

# -*- coding: utf-8 -*-
import json
import logging
import pytz
from datetime import datetime, timedelta
from dateutil import relativedelta
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class DinoApiEndpoint(models.Model):
    _name = 'dino.api.endpoint'
    _description = 'API Endpoint Configuration'
    _order = 'name'

    # Basic info
    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=False)

    # Bank relation
    bank_id = fields.Many2one('dino.bank', string='Bank', help='Bank for API operations')

    # API configuration
    operation_type = fields.Selection([
        ('nbu_rates', 'Импорт курсов валют НБУ'),
        ('privat_balances', 'Импорт балансов счетов ПриватБанк'),
        ('privat_transactions', 'Импорт транзакций ПриватБанк'),
        ('privat_balance_history', 'Импорт истории балансов ПриватБанк'),
        ('mono_client_info', 'Получение информации о клиенте Монобанк'),
        ('mono_rates', 'Импорт курсов валют Монобанк'),
        ('mono_transactions', 'Импорт транзакций Монобанк'),
        ('partners_update', 'Обновление данных партнеров'),
        ('seafile_sync', 'Синхронизация с библиотекой SeaFile')  # Новый тип операции
    ], string='Тип операции', required=True)

    # Authentication
    auth_token = fields.Char(string='Token', encrypted=True)
    auth_api_key = fields.Char(string='Client Id', encrypted=True)

    # History management
    start_date = fields.Date(string='Start Date', help='Глубина истории для загрузки')
    force_full_sync = fields.Boolean(string='Force Full Sync', default=False,
                                   help='Перезаписать все существующие данные')
    last_sync_date = fields.Datetime(string='Last Sync')

    # Cron configuration
    cron_active = fields.Boolean(string='Cron Active', default=False)
    cron_running = fields.Boolean(string='Cron Running', default=False, help='Крон запущен и работает')
    cron_priority = fields.Integer(string='Priority', default=10, help='0 — highest priority')
    cron_interval_number = fields.Integer(string='Interval', default=1)
    cron_interval_type = fields.Selection([
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months')
    ], string='Interval Type', default='days')
    cron_timezone = fields.Selection(
        string='Timezone',
        selection='_get_timezone_selection',
        default=lambda self: self.env.user.tz or 'Europe/Kiev'
    )
    cron_start_time = fields.Float(string='Start Time', help='Start time for Minutes/Hours interval (0-24), or exact time for Days/Weeks/Months')
    cron_end_time = fields.Float(string='End Time', help='End time for Minutes/Hours interval (0-24), hidden for Days/Weeks/Months')
    
    # Weekday filters
    cron_monday = fields.Boolean(string='Monday', default=False)
    cron_tuesday = fields.Boolean(string='Tuesday', default=False)
    cron_wednesday = fields.Boolean(string='Wednesday', default=False)
    cron_thursday = fields.Boolean(string='Thursday', default=False)
    cron_friday = fields.Boolean(string='Friday', default=False)
    cron_saturday = fields.Boolean(string='Saturday', default=False)
    cron_sunday = fields.Boolean(string='Sunday', default=False)
    
    cron_day_of_month = fields.Integer(string='Day of Month', help='1-31, used for Months interval')
    cron_last_day_of_month = fields.Boolean(string='Last Day of Month', help='If true, overrides Day of Month')

    # Computed next run
    next_run = fields.Datetime(string='Next Run', compute='_compute_next_run')

    # Operation parameters (JSON)
    config_params = fields.Text(string='Config Params', default='{}',
                              help='JSON с дополнительными параметрами')

    # Relations
    log_ids = fields.One2many('dino.api.log', 'endpoint_id', string='Logs')

    # Computed last result
    last_result = fields.Char(string='Last Result', compute='_compute_last_result')

    # Computed field visibility
    show_token = fields.Boolean(compute='_compute_auth_visibility', store=False)
    show_api_key = fields.Boolean(compute='_compute_auth_visibility', store=False)
    show_bank = fields.Boolean(compute='_compute_auth_visibility', store=False)

    @api.depends('cron_active', 'cron_interval_number', 'cron_interval_type', 'cron_timezone', 'cron_start_time', 'cron_end_time', 
                 'cron_monday', 'cron_tuesday', 'cron_wednesday', 'cron_thursday', 'cron_friday', 'cron_saturday', 'cron_sunday',
                 'cron_day_of_month', 'cron_last_day_of_month', 'last_sync_date')
    def _compute_next_run(self):
        for record in self:
            if not record.cron_active:
                record.next_run = False
                continue

            # Get timezone
            tz = pytz.timezone(record.cron_timezone or 'UTC')
            now_utc = datetime.now(pytz.UTC)

            # Base time: last sync in TZ
            base_time = record.last_sync_date
            if base_time:
                base_time = fields.Datetime.from_string(base_time).replace(tzinfo=pytz.UTC).astimezone(tz)
            else:
                base_time = now_utc.astimezone(tz)

            _logger.debug(f'Computing next_run for {record.name}: base_time={base_time}, tz={tz}')

            # Calculate next time
            next_time = self._calculate_next_run_time(record, base_time, tz)

            # Convert to UTC for storage (naive datetime)
            if next_time:
                record.next_run = next_time.astimezone(pytz.UTC).replace(tzinfo=None)
                _logger.debug(f'Next run for {record.name}: {record.next_run}')
            else:
                record.next_run = False
                _logger.warning(f'Could not calculate next_run for {record.name}')

    def _calculate_next_run_time(self, record, base_time, tz):
        """Calculate next run time considering all filters"""
        interval = record.cron_interval_number or 1
        itype = record.cron_interval_type or 'days'

        # Start from base_time
        candidate = base_time

        max_attempts = 1000  # Prevent infinite loop
        attempts = 0

        while attempts < max_attempts:
            # Apply interval
            if itype == 'minutes':
                candidate += timedelta(minutes=interval)
            elif itype == 'hours':
                candidate += timedelta(hours=interval)
            elif itype == 'days':
                candidate += timedelta(days=interval)
            elif itype == 'weeks':
                candidate += timedelta(weeks=interval)
            elif itype == 'months':
                candidate += relativedelta.relativedelta(months=interval)
            else:
                candidate += timedelta(days=interval)

            # For Days/Weeks/Months: set exact time from start_time
            if itype in ('days', 'weeks', 'months'):
                if record.cron_start_time is not None:
                    hours = int(record.cron_start_time)
                    minutes = int((record.cron_start_time - hours) * 60)
                    candidate = candidate.replace(hour=hours, minute=minutes, second=0, microsecond=0)

                # Apply day of month for months
                if itype == 'months':
                    if record.cron_last_day_of_month:
                        # Last day of month
                        next_month = candidate.replace(day=28) + timedelta(days=4)
                        candidate = next_month - timedelta(days=next_month.day)
                    elif record.cron_day_of_month:
                        try:
                            candidate = candidate.replace(day=record.cron_day_of_month)
                        except ValueError:
                            # Invalid day, use last day
                            next_month = candidate.replace(day=28) + timedelta(days=4)
                            candidate = next_month - timedelta(days=next_month.day)

            # For Minutes/Hours: check if within window
            elif itype in ('minutes', 'hours'):
                if record.cron_start_time is not None and record.cron_end_time is not None:
                    start_h = int(record.cron_start_time)
                    start_m = int((record.cron_start_time - start_h) * 60)
                    end_h = int(record.cron_end_time)
                    end_m = int((record.cron_end_time - end_h) * 60)

                    start_window = candidate.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                    end_window = candidate.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

                    if candidate < start_window:
                        candidate = start_window
                    elif candidate > end_window:
                        # Move to next day start
                        candidate = (candidate + timedelta(days=1)).replace(hour=start_h, minute=start_m, second=0, microsecond=0)

            # Check weekdays
            weekday_map = {
                0: record.cron_monday,
                1: record.cron_tuesday,
                2: record.cron_wednesday,
                3: record.cron_thursday,
                4: record.cron_friday,
                5: record.cron_saturday,
                6: record.cron_sunday,
            }
            allowed_weekdays = [day for day, enabled in weekday_map.items() if enabled]
            
            if allowed_weekdays:
                current_wd = candidate.weekday()  # 0=Mon, 6=Sun
                if current_wd not in allowed_weekdays:
                    # Find next allowed weekday
                    days_ahead = min((wd - current_wd) % 7 for wd in allowed_weekdays)
                    if days_ahead == 0:
                        days_ahead = 7  # Next week
                    candidate += timedelta(days=days_ahead)

            # Ensure it's in future
            if candidate > datetime.now(tz):
                return candidate

            attempts += 1

        return None  # Could not find valid time

    @api.depends('log_ids')
    def _compute_last_result(self):
        for record in self:
            last_log = record.log_ids.sorted('create_date', reverse=True)[:1]
            if last_log:
                record.last_result = '🆗' if last_log.status == 'success' else '🆘'
            else:
                record.last_result = ''

    @api.depends('operation_type')
    def _compute_auth_visibility(self):
        auth_requirements = {
            'nbu_rates': [],
            'privat_balances': ['token', 'api_key'],
            'privat_transactions': ['token', 'api_key'],
            'privat_balance_history': ['token', 'api_key'],
            'mono_client_info': ['token'],
            'mono_rates': ['token'],
            'mono_transactions': ['token'],
            'partners_update': [],
        }
        bank_requirements = {
            'nbu_rates': False,  # NBU is fixed
            'privat_balances': True,
            'privat_transactions': True,
            'privat_balance_history': True,
            'mono_client_info': True,
            'mono_rates': True,
            'mono_transactions': True,
            'partners_update': False,
        }
        for record in self:
            required = auth_requirements.get(record.operation_type, [])
            record.show_token = 'token' in required
            record.show_api_key = 'api_key' in required
            record.show_bank = bank_requirements.get(record.operation_type, False)



    def action_activate(self):
        """Activate - make form readonly and show Edit/Run buttons"""
        self.ensure_one()
        self.write({'active': True, 'cron_running': False})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_run(self):
        """Run Now - activate and execute"""
        self.ensure_one()
        # Activate endpoint
        self.write({'active': True})
        # If cron is enabled, mark as running
        if self.cron_active:
            self.write({'cron_running': True})
        # Execute the endpoint
        self.run_endpoint(trigger_type='manual')
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_edit(self):
        """Edit mode - deactivate for editing"""
        self.ensure_one()
        self.write({'active': False, 'cron_running': False})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_stop(self):
        """Stop - deactivate endpoint and cron"""
        self.ensure_one()
        self.write({'active': False, 'cron_running': False})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def write(self, vals):
        """Override write to handle activation"""
        return super(DinoApiEndpoint, self).write(vals)
    


    def run_endpoint(self, trigger_type='manual'):
        """Execute the endpoint"""
        self.ensure_one()
        _logger.info(f"Running endpoint: {self.name} (trigger: {trigger_type})")

        try:
            # Get handler
            handler_class = self._get_handler_class()
            handler = handler_class(self)
            result = handler.execute()

            # Log success with progress steps if available
            if isinstance(result, dict) and 'steps' in result:
                # Create progress log entries
                for step in result['steps']:
                    self._log_execution('info', {'progress': step}, 'progress')
                # Log final result
                self._log_execution('success', result.get('final', result), trigger_type)
            else:
                self._log_execution('success', result, trigger_type)
            return result

        except Exception as e:
            _logger.error(f"Endpoint {self.name} failed: {e}")
            self._log_execution('error', str(e), trigger_type)
            raise

    def _get_handler_class(self):
        """Get the appropriate handler class"""
        from ..services.handlers import (
            NbuRatesHandler, PrivatBalancesHandler, PrivatTransactionsHandler,
            PrivatBalanceHistoryHandler,
            MonoClientInfoHandler, MonoRatesHandler, MonoTransactionsHandler,
            PartnersUpdateHandler
        )

        handlers = {
            'nbu_rates': NbuRatesHandler,
            'privat_balances': PrivatBalancesHandler,
            'privat_transactions': PrivatTransactionsHandler,
            'privat_balance_history': PrivatBalanceHistoryHandler,
            'mono_client_info': MonoClientInfoHandler,
            'mono_rates': MonoRatesHandler,
            'mono_transactions': MonoTransactionsHandler,
            'partners_update': PartnersUpdateHandler,
        }

        handler_class = handlers.get(self.operation_type)
        if not handler_class:
            raise ValueError(f"No handler found for operation: {self.operation_type}")

        return handler_class

    def _log_execution(self, status, data, trigger_type='manual'):
        """Log execution result"""
        self.env['dino.api.log'].create({
            'endpoint_id': self.id,
            'trigger_type': trigger_type,
            'status': status,
            'request_data': json.dumps({'endpoint': self.name, 'operation': self.operation_type}, ensure_ascii=False),
            'response_data': json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data),
            'execution_time': 0  # TODO: measure actual time
        })

    @api.model
    def _get_timezone_selection(self):
        """Get list of timezones for selection"""
        return [(tz, tz) for tz in pytz.all_timezones]

    @api.model
    def run_scheduled_endpoints(self):
        """Cron method to run all active scheduled endpoints"""
        now = fields.Datetime.now()
        endpoints = self.search([
            ('cron_active', '=', True),
            ('next_run', '<=', now)
        ])

        for endpoint in endpoints:
            try:
                endpoint.run_endpoint(trigger_type='cron')
                endpoint.last_sync_date = now
            except Exception as e:
                _logger.error(f"Scheduled endpoint {endpoint.name} failed: {e}")

# End of file api_integration/models/dino_api_endpoint.py

# End of file api_integration/models/dino_api_endpoint.py
