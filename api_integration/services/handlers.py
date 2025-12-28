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
                    'errors': stats.get('unknown_accounts', 0)
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
        # Import existing service
        from ...finance.services.nbu_service import import_nbu_rates

        params = json.loads(self.endpoint.config_params or '{}')
        result = import_nbu_rates(
            self.env,
            self.endpoint.bank_id,
            start_date=params.get('start_date'),
            end_date=params.get('end_date'),
            overwrite=params.get('overwrite', False)
        )

        return self._standardize_result(result)


class PrivatBalancesHandler(BaseApiHandler):
    """Handler for Privat balances"""
    required_auth_fields = ['token', 'api_key']

    def execute(self):
        # Import existing service
        from ...finance.services.privat_service import import_accounts

        params = json.loads(self.endpoint.config_params or '{}')
        result = import_accounts(
            self.endpoint.bank_id,
            startDate=params.get('date')
        )

        return self._standardize_result(result)


class PrivatTransactionsHandler(BaseApiHandler):
    """Handler for Privat transactions"""
    required_auth_fields = ['token', 'api_key']

    def execute(self):
        # Import existing service
        from ...finance.services.privat_service import import_transactions

        params = json.loads(self.endpoint.config_params or '{}')
        result = import_transactions(
            self.endpoint.bank_id,
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