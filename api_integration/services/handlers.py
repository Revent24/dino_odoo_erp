# -*- coding: utf-8 -*-
"""
API Handlers for different operations
Each handler wraps existing services and provides unified interface
"""

import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class BaseApiHandler:
    """Base class for all API handlers"""

    required_auth_fields = []  # Default: no auth required

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.env = endpoint.env

    def execute(self):
        """Main execution method"""
        raise NotImplementedError

    def _standardize_result(self, service_result):
        """Convert service result to standard format"""
        if isinstance(service_result, dict) and 'stats' in service_result:
            stats = service_result['stats']
            return {
                'status': 'success',
                'data': {
                    'created': stats.get('created', 0),
                    'updated': stats.get('updated', 0),
                    'skipped': stats.get('skipped', 0),
                    'inactive_accounts': stats.get('inactive_accounts', 0)
                },
                'metadata': {
                    'operation': self.endpoint.operation_type,
                    'bank': self.endpoint.bank_id.name if self.endpoint.bank_id else None
                }
            }
        return service_result


class NbuRatesHandler(BaseApiHandler):
    """Handler for NBU rates"""
    required_auth_fields = []  # No auth required

    def execute(self):
        progress = {
            'steps': [],
            'final': {}
        }

        def log_step(message):
            timestamp = datetime.now().strftime('%H:%M:%S')
            step_msg = f"{timestamp} - {message}"
            progress['steps'].append(step_msg)
            _logger.warning(f"NbuRatesHandler: {message}")
            # Log intermediate step to database
            self.endpoint._log_execution('info', {'step': step_msg}, 'progress')

        log_step(">>> START EXECUTION")
        log_step(f"Endpoint: '{self.endpoint.name}'")

        params = json.loads(self.endpoint.config_params or '{}')
        log_step(f"[CONFIG] Params loaded: {params}")

        log_step("[STEP 1/2] Calling run_sync for import and sync")
        from .nbu_service import run_sync
        result = run_sync(self.env, None)
        log_step("[STEP 1/2] run_sync completed")

        log_step("[STEP 2/2] Processing result")
        if isinstance(result, dict) and 'type' in result:
            message = result.get('params', {}).get('message', '')
            log_step(f"[RESULT] Message: '{message}'")
            import_stats = {'created': 0, 'updated': 0, 'sync_created': 0, 'sync_updated': 0}

            if 'Создано' in message and 'Обновлено' in message:
                try:
                    import_part = message.split('НБУ Импорт:')[1].split('. Системные')[0]
                    sync_part = message.split('курсы:')[1]

                    # Remove dots and extract numbers
                    import_created_str = import_part.split('Создано')[1].split(',')[0].strip().rstrip('.')
                    import_updated_str = import_part.split('Обновлено')[1].strip().rstrip('.')
                    sync_created_str = sync_part.split('Создано')[1].split(',')[0].strip().rstrip('.')
                    sync_updated_str = sync_part.split('Обновлено')[1].strip().rstrip('.')

                    import_created = int(import_created_str) if import_created_str.isdigit() else 0
                    import_updated = int(import_updated_str) if import_updated_str.isdigit() else 0
                    sync_created = int(sync_created_str) if sync_created_str.isdigit() else 0
                    sync_updated = int(sync_updated_str) if sync_updated_str.isdigit() else 0

                    import_stats.update({
                        'created': import_created,
                        'updated': import_updated,
                        'sync_created': sync_created,
                        'sync_updated': sync_updated
                    })
                    log_step(f"[STATS] Import - Created:{import_created}, Updated:{import_updated}")
                    log_step(f"[STATS] Sync - Created:{sync_created}, Updated:{sync_updated}")
                except Exception as e:
                    log_step(f"[ERROR] Failed to parse stats: {e}")

            standardized = self._standardize_result({'stats': import_stats})
        else:
            log_step("[RESULT] Using result as-is")
            standardized = self._standardize_result(result)

        progress['final'] = standardized
        log_step("<<< EXECUTION COMPLETE")
        return progress


class PrivatBalancesHandler(BaseApiHandler):
    """Handler for Privat balances"""
    required_auth_fields = ['token', 'api_key']

    def execute(self):
        # Import existing service
        from .privat_service import import_accounts

        params = json.loads(self.endpoint.config_params or '{}')
        result = import_accounts(
            self.endpoint,
            startDate=params.get('date')
        )

        return self._standardize_result(result)


class PrivatTransactionsHandler(BaseApiHandler):
    """Handler for Privat transactions"""
    required_auth_fields = ['token', 'api_key']

    def execute(self):
        # Import existing service
        from .privat_service import import_transactions

        params = json.loads(self.endpoint.config_params or '{}')
        result = import_transactions(
            self.endpoint,
            startDate=params.get('start_date'),
            endDate=params.get('end_date')
        )

        return self._standardize_result(result)


# Placeholder handlers for Mono and Partners
class MonoClientInfoHandler(BaseApiHandler):
    required_auth_fields = ['token']

    def execute(self):
        # TODO: Implement Mono client info
        return {'status': 'success', 'data': {'message': 'Not implemented yet'}}


class MonoRatesHandler(BaseApiHandler):
    required_auth_fields = ['token']

    def execute(self):
        # TODO: Implement Mono rates
        return {'status': 'success', 'data': {'message': 'Not implemented yet'}}


class MonoTransactionsHandler(BaseApiHandler):
    required_auth_fields = ['token']

    def execute(self):
        # TODO: Implement Mono transactions
        return {'status': 'success', 'data': {'message': 'Not implemented yet'}}


class PartnersUpdateHandler(BaseApiHandler):
    required_auth_fields = []  # No auth required

    def execute(self):
        # TODO: Implement partners update
        return {'status': 'success', 'data': {'message': 'Not implemented yet'}}