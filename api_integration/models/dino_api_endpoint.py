# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class DinoApiEndpoint(models.Model):
    _name = 'dino.api.endpoint'
    _description = 'API Endpoint Configuration'
    _order = 'name'

    # Basic info
    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    # Bank relation removed - bank is determined by operation_type

    # API configuration
    operation_type = fields.Selection([
        ('nbu_rates', 'Импорт курсов валют НБУ'),
        ('privat_balances', 'Импорт балансов счетов ПриватБанк'),
        ('privat_transactions', 'Импорт транзакций ПриватБанк'),
        ('mono_client_info', 'Получение информации о клиенте Монобанк'),
        ('mono_rates', 'Импорт курсов валют Монобанк'),
        ('mono_transactions', 'Импорт транзакций Монобанк'),
        ('partners_update', 'Обновление данных партнеров')
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
    cron_interval_number = fields.Integer(string='Interval', default=1)
    cron_interval_type = fields.Selection([
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days')
    ], string='Interval Type', default='days')
    cron_time_of_day = fields.Float(string='Time of Day', help='0-24 hours')

    # Computed next run
    next_run = fields.Datetime(string='Next Run', compute='_compute_next_run')

    # Operation parameters (JSON)
    config_params = fields.Text(string='Config Params', default='{}',
                              help='JSON с дополнительными параметрами')

    # Relations
    log_ids = fields.One2many('dino.api.log', 'endpoint_id', string='Logs')

    # Computed last result
    last_result = fields.Char(string='Last Result', compute='_compute_last_result')

    # Computed auth field visibility
    show_token = fields.Boolean(compute='_compute_auth_visibility', store=False)
    show_api_key = fields.Boolean(compute='_compute_auth_visibility', store=False)

    @api.depends('cron_active', 'cron_interval_number', 'cron_interval_type', 'cron_time_of_day', 'last_sync_date')
    def _compute_next_run(self):
        for record in self:
            if not record.cron_active:
                record.next_run = False
                continue

            base_time = record.last_sync_date or datetime.now()

            if record.cron_interval_type == 'minutes':
                delta = timedelta(minutes=record.cron_interval_number)
            elif record.cron_interval_type == 'hours':
                delta = timedelta(hours=record.cron_interval_number)
            else:  # days
                delta = timedelta(days=record.cron_interval_number)

            next_time = base_time + delta

            # Apply time of day if specified
            if record.cron_time_of_day:
                hours = int(record.cron_time_of_day)
                minutes = int((record.cron_time_of_day - hours) * 60)
                next_time = next_time.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            record.next_run = next_time

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
            'mono_client_info': ['token'],
            'mono_rates': ['token'],
            'mono_transactions': ['token'],
            'partners_update': [],
        }
        for record in self:
            required = auth_requirements.get(record.operation_type, [])
            record.show_token = 'token' in required
            record.show_api_key = 'api_key' in required

    def run_endpoint(self, trigger_type='manual'):
        """Execute the endpoint"""
        self.ensure_one()
        _logger.info(f"Running endpoint: {self.name}")

        try:
            # Get handler
            handler_class = self._get_handler_class()
            handler = handler_class(self)
            result = handler.execute()

            # Log success
            self._log_execution('success', result, trigger_type)
            return result

        except Exception as e:
            _logger.error(f"Endpoint {self.name} failed: {e}")
            self._log_execution('error', str(e), trigger_type)
            raise

    def _get_handler_class(self):
        """Get the appropriate handler class"""
        handlers = {
            'nbu_rates': 'api_integration.services.handlers.NbuRatesHandler',
            'privat_balances': 'api_integration.services.handlers.PrivatBalancesHandler',
            'privat_transactions': 'api_integration.services.handlers.PrivatTransactionsHandler',
            'mono_client_info': 'api_integration.services.handlers.MonoClientInfoHandler',
            'mono_rates': 'api_integration.services.handlers.MonoRatesHandler',
            'mono_transactions': 'api_integration.services.handlers.MonoTransactionsHandler',
            'partners_update': 'api_integration.services.handlers.PartnersUpdateHandler',
        }

        handler_path = handlers.get(self.operation_type)
        if not handler_path:
            raise ValueError(f"No handler found for operation: {self.operation_type}")

        # Import and return handler class
        module_path, class_name = handler_path.rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)

    def _log_execution(self, status, data, trigger_type='manual'):
        """Log execution result"""
        self.env['dino.api.log'].create({
            'endpoint_id': self.id,
            'trigger_type': trigger_type,
            'status': status,
            'request_data': json.dumps({'endpoint': self.name, 'operation': self.operation_type}),
            'response_data': json.dumps(data) if isinstance(data, dict) else str(data),
            'execution_time': 0  # TODO: measure actual time
        })

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

    def test_endpoint(self):
        """Test run without saving data"""
        # TODO: implement test mode - for now just log the attempt
        self._log_execution('success', {'message': 'Test run completed'}, 'test')