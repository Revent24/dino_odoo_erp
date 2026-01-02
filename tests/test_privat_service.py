import json
import time
from types import SimpleNamespace

import pytest

import api_integration.services.privat_service as privat_service
from api_integration.services.privat_client import PrivatClient


class FakeCurrency:
    def __init__(self, name, id=1):
        self.name = name
        self.id = id


class FakeCurrencyModel:
    def __init__(self):
        self._currs = {'UAH': FakeCurrency('UAH', 1)}

    def search(self, domain, limit=1):
        name = domain[0][2]
        return self._currs.get(name)


class FakeBankAccountModel:
    def __init__(self):
        self.created = []
        self.updated = []
        self._records = []

    def search(self, domain, limit=1):
        return None

    def create(self, vals):
        self.created.append(vals)
        rec = SimpleNamespace(**vals)
        self._records.append(rec)
        return rec


class FakeBank:
    def __init__(self):
        self.api_key = 'fake'
        self.api_client_id = 'cid'
        # Simulate env with model access
        class Env(dict):
            pass
        self.env = Env()
        self.env['dino.bank.account'] = FakeBankAccountModel()
        self.env['res.currency'] = FakeCurrencyModel()
        self.name = 'Privat'
        self.id = 1


class FakePrivatClient:
    def __init__(self, api_key=None, client_id=None, **kwargs):
        pass

    def fetch_balances_for_all_accounts(self, startDate=None, endDate=None):
        # return one valid account and one without iban (skipped)
        return [
            {'iban': 'UA123', 'currency': 'UAH', 'balanceOut': '100', 'acc': 'acc1', 'nameACC': 'Acc 1'},
            {'currency': 'UAH', 'balanceOut': '50'}
        ]

    def get_api_settings(self):
        return {'status': 'SUCCESS', 'settings': {'stdate': '25-12-2025'}}


def test_import_accounts_creates_and_skips(monkeypatch):
    bank = FakeBank()
    # monkeypatch PrivatClient used in service
    monkeypatch.setattr(privat_service, 'PrivatClient', FakePrivatClient)
    stats = privat_service.import_accounts(bank, startDate=None)
    assert stats['created'] == 1
    assert stats['skipped'] == 1




