# -*- coding: utf-8 -*-
"""High-level Mono service (skeleton).
"""
import logging

from .mono_client import MonoClient

_logger = logging.getLogger(__name__)


class MonoService:
    def __init__(self, env, bank):
        self.env = env
        self.bank = bank
        self.client = MonoClient(api_url=bank.api_url, api_key=bank.api_key)

    def fetch_accounts(self):
        raise NotImplementedError('MonoService.fetch_accounts not implemented')

    def fetch_transactions(self, account, since=None):
        raise NotImplementedError('MonoService.fetch_transactions not implemented')

    def fetch_balances(self):
        raise NotImplementedError('MonoService.fetch_balances not implemented')
