# -*- coding: utf-8 -*-
"""Low-level NBU HTTP client with simple caching and helpers."""
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

_NBU_BANKS_CACHE = {'ts': None, 'banks': []}


class NBUClient:
    """Simple client for NBU endpoints used by services.

    Methods are simple and return parsed JSON (list/dicts) or raise requests exceptions.
    """

    def __init__(self, user_agent='DinoERP/1.0', timeout=20):
        self.user_agent = user_agent
        self.timeout = timeout

    def get_banks(self, refresh=False):
        cache_ttl = timedelta(hours=24)
        now = datetime.utcnow()
        if not refresh and _NBU_BANKS_CACHE['ts'] and (now - _NBU_BANKS_CACHE['ts']) < cache_ttl:
            return _NBU_BANKS_CACHE['banks']

        urls = [
            'https://bank.gov.ua/NBUStatService/v1/statdirectory/banks?json',
            'https://bank.gov.ua/NBUStatService/v1/statdirectory/banks'
        ]
        headers = {'Accept': 'application/json', 'User-Agent': self.user_agent}
        banks = []
        for url in urls:
            try:
                resp = requests.get(url, timeout=self.timeout, headers=headers)
                if resp.status_code == 400:
                    continue
                resp.raise_for_status()
                banks = resp.json()
                break
            except requests.RequestException as e:
                _logger.warning('NBU banks lookup failed for url %s: %s', url, e)
                continue

        _NBU_BANKS_CACHE['ts'] = now
        _NBU_BANKS_CACHE['banks'] = banks
        return banks

    def fetch_exchange(self, start_date, end_date, valcode):
        """Fetch exchange data for a value code in a date range.
        start_date / end_date are date objects; returns list of records (dicts).
        """
        s_str = start_date.strftime('%Y%m%d')
        e_str = end_date.strftime('%Y%m%d')
        headers = {'Accept': 'application/json', 'User-Agent': self.user_agent}
        url = f'https://bank.gov.ua/NBU_Exchange/exchange_site?start={s_str}&end={e_str}&valcode={valcode}&sort=exchangedate&order=asc&json'
        resp = requests.get(url, timeout=self.timeout, headers=headers)
        resp.raise_for_status()
        return resp.json()
