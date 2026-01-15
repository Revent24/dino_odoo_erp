#
#  -*- File: api_integration/services/mono_client.py -*-
#
# -*- coding: utf-8 -*-
"""Skeleton Mono client.
"""
import logging

_logger = logging.getLogger(__name__)


import requests
import logging

_logger = logging.getLogger(__name__)


class MonoClient:
    def __init__(self, api_url=None, api_key=None, timeout=20):
        self.api_url = api_url or "https://api.monobank.ua"
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({'X-Token': api_key})

    def fetch_exchange(self):
        """
        Получает курсы валют Монобанка.
        Возвращает список словарей с ключами: currencyCodeA, currencyCodeB, date, rateBuy, rateSell
        """
        url = f"{self.api_url}/bank/currency"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            _logger.info(f"Mono exchange rates received: {len(data) if data else 0} currency pairs")
            return data if data else []
        except requests.RequestException as e:
            _logger.error(f"MonoBank exchange API error: {e}")
            raise

    def fetch_accounts(self, *args, **kwargs):
        raise NotImplementedError('fetch_accounts not implemented yet')

    def fetch_transactions(self, *args, **kwargs):
        raise NotImplementedError('fetch_transactions not implemented yet')
# End of file api_integration/services/mono_client.py
