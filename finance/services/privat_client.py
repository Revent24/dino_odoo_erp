# -*- coding: utf-8 -*-
"""Privatbank client for Autoklient API.
Implements low-level HTTP requests and authentication.
"""
import logging
import requests
from datetime import date

_logger = logging.getLogger(__name__)

BASE_URL = 'https://acp.privatbank.ua/api'


class PrivatClient:
    def __init__(self, api_key=None, timeout=30):
        if not api_key:
            raise ValueError("API key (token) is required for PrivatClient")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, endpoint, params=None):
        """Generic method to perform a GET request."""
        url = f"{BASE_URL}{endpoint}"
        headers = {
            'User-Agent': 'DinoERP Integration',
            'token': self.api_key,
            # Content-Type is not needed for GET requests
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("PrivatBank API request failed: %s", e)
            raise  # Re-raise the exception to be handled by the service layer

    def fetch_balances_for_all_accounts(self):
        """
        Fetches balances for all active accounts.
        The /statements/balance endpoint without 'acc' parameter returns all accounts.
        We need a date range, so we'll just ask for today to get the list.
        """
        today_str = date.today().strftime('%d-%m-%Y')
        params = {
            'startDate': today_str,
            'endDate': today_str,
        }
        response = self._get('/statements/balance', params=params)
        
        if response.get('status') == 'SUCCESS':
            return response.get('balances', [])
        else:
            _logger.error("Failed to fetch balances from PrivatBank: %s", response)
            return []

    def check_api_status(self):
        """Check API health/status via /statements/settings.
        Returns True if API is in working state (phase == 'WRK' and work_balance == 'N'), False otherwise.
        Raises requests exceptions on HTTP errors.
        """
        try:
            resp = self._get('/statements/settings')
        except Exception:
            _logger.exception('Failed to fetch PrivatBank settings endpoint')
            raise
        if resp.get('status') != 'SUCCESS':
            _logger.warning('PrivatBank settings response not SUCCESS: %s', resp)
            return False
        settings = resp.get('settings') or {}
        if settings.get('phase') == 'WRK' and settings.get('work_balance') == 'N':
            return True
        _logger.info('Privat API not in working mode: %s', settings)
        return False

    def fetch_transactions_page(self, startDate, followId=None, acc=None):
        """Fetch a single page of transactions.
        :param startDate: 'DD-MM-YYYY' string
        :param followId: optional next_page_id from previous response
        :param acc: optional account number to filter
        :return: parsed JSON response
        """
        params = {'startDate': startDate}
        if followId:
            params['followId'] = followId
        if acc:
            params['acc'] = acc
        response = self._get('/statements/transactions', params=params)
        return response

    def fetch_transactions_iter(self, startDate, acc=None):
        """Generator that yields transactions pages for given startDate and account.
        Handles followId pagination as in legacy PHP code.
        Yields each response dict.
        """
        next_page = None
        while True:
            resp = self.fetch_transactions_page(startDate=startDate, followId=next_page, acc=acc)
            yield resp
            if not resp or not resp.get('exist_next_page'):
                break
            next_page = resp.get('next_page_id')
