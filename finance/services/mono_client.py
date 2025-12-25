# -*- coding: utf-8 -*-
"""Skeleton Mono client.
"""
import logging

_logger = logging.getLogger(__name__)


class MonoClient:
    def __init__(self, api_url=None, api_key=None, timeout=20):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout

    def fetch_exchange(self, *args, **kwargs):
        raise NotImplementedError('Mono client fetch_exchange not implemented yet')

    def fetch_accounts(self, *args, **kwargs):
        raise NotImplementedError('fetch_accounts not implemented yet')

    def fetch_transactions(self, *args, **kwargs):
        raise NotImplementedError('fetch_transactions not implemented yet')
