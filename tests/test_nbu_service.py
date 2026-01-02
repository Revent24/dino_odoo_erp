import json
from types import SimpleNamespace
import pytest
import responses

import api_integration.services.nbu_service as nbu_service
from api_integration.services.nbu_client import NBUClient


class FakeCurrency:
    def __init__(self, name, id=1, active=True):
        self.name = name
        self.id = id
        self.active = active


class FakeCurrencyModel:
    def __init__(self):
        self._currs = {
            'USD': FakeCurrency('USD', 2, True),
            'EUR': FakeCurrency('EUR', 3, True),
            'UAH': FakeCurrency('UAH', 1, True)
        }

    def search(self, domain):
        active_filter = None
        for d in domain:
            if d[0] == 'active':
                active_filter = d[2]
        if active_filter is True:
            return [c for c in self._currs.values() if c.active]
        return list(self._currs.values())


class FakeRateModel:
    def __init__(self):
        self.created = []
        self.updated = []
        self._records = []

    def search(self, domain, limit=1):
        # Simple mock: return None for now
        return None

    def create(self, vals_list):
        if isinstance(vals_list, list):
            for vals in vals_list:
                self.created.append(vals)
                rec = SimpleNamespace(**vals)
                self._records.append(rec)
        else:
            self.created.append(vals_list)
            rec = SimpleNamespace(**vals_list)
            self._records.append(rec)
        return rec


class FakeSysRateModel(FakeRateModel):
    def __init__(self):
        super().__init__()
        self._records = []

    def search(self, domain, limit=1):
        # Parse domain for sys rates
        records = []
        for rec in self._records:
            match = True
            for d in domain:
                if d[0] == 'name' and d[1] == '>=':
                    if rec.name < d[2]:
                        match = False
                        break
                elif d[0] == 'name' and d[1] == '<=':
                    if rec.name > d[2]:
                        match = False
                        break
                elif d[0] == 'company_id' and d[1] == '=':
                    if rec.company_id != d[2]:
                        match = False
                        break
            if match:
                records.append(rec)
        return records

    def create(self, vals_list):
        if isinstance(vals_list, list):
            for vals in vals_list:
                rec = SimpleNamespace(**vals)
                rec.currency_id = SimpleNamespace(id=vals.get('currency_id'))
                rec.name = vals.get('name')
                rec.rate = vals.get('rate')
                rec.company_id = vals.get('company_id')
                self.created.append(vals)
                self._records.append(rec)
        else:
            rec = SimpleNamespace(**vals_list)
            rec.currency_id = SimpleNamespace(id=vals_list.get('currency_id'))
            rec.name = vals_list.get('name')
            rec.rate = vals_list.get('rate')
            rec.company_id = vals_list.get('company_id')
            self.created.append(vals_list)
            self._records.append(rec)
        return rec


class FakeCompany:
    def __init__(self):
        self.id = 1
        self.currency_id = SimpleNamespace(name='UAH')


class FakeEnv:
    def __init__(self):
        self.company = FakeCompany()
        self.user = None
        self['res.currency'] = FakeCurrencyModel()
        self['dino.currency.rate'] = FakeRateModel()
        self['res.currency.rate'] = FakeSysRateModel()

    def __getitem__(self, key):
        return getattr(self, key.replace('.', '_'))


class FakeBank:
    def __init__(self, mfo='300001', start_sync_date='2023-01-01'):
        self.mfo = mfo
        self.start_sync_date = start_sync_date
        self.env = FakeEnv()


@responses.activate
def test_import_nbu_rates_success():
    bank = FakeBank()
    client = NBUClient()
    url = "https://bank.gov.ua/NBU_Exchange/exchange_site?start=20230101&end=20230101&sort=exchangedate&order=asc&json"
    body = [
        {"cc": "USD", "rate": 36.5, "exchangedate": "01.01.2023"},
        {"cc": "EUR", "rate": 40.0, "exchangedate": "01.01.2023"}
    ]

    responses.add(responses.GET, url, json=body, status=200)

    result = nbu_service.import_nbu_rates(bank.env, bank, to_date='2023-01-01')
    assert result['stats']['created'] == 2
    assert result['stats']['updated'] == 0
    assert result['stats']['skipped'] == 0

    # Check that dino rates were created with rate_type='official'
    dino_rates = bank.env['dino.currency.rate'].created
    assert len(dino_rates) == 2
    for rate in dino_rates:
        assert rate['rate_type'] == 'official'
        assert rate['source'] == 'nbu'


@responses.activate
def test_import_nbu_rates_skip_uah():
    bank = FakeBank()
    url = "https://bank.gov.ua/NBU_Exchange/exchange_site?start=20230101&end=20230101&sort=exchangedate&order=asc&json"
    body = [
        {"cc": "USD", "rate": 36.5, "exchangedate": "01.01.2023"},
        {"cc": "UAH", "rate": 1.0, "exchangedate": "01.01.2023"}  # Should be skipped
    ]

    responses.add(responses.GET, url, json=body, status=200)

    result = nbu_service.import_nbu_rates(bank.env, bank, to_date='2023-01-01')
    assert result['stats']['created'] == 1  # Only USD
    assert result['stats']['skipped'] == 0  # UAH skipped before processing


# MFO check removed - NBU import doesn't require specific bank


@responses.activate
def test_run_sync():
    bank = FakeBank()
    url = "https://bank.gov.ua/NBU_Exchange/exchange_site?start=20230101&end=20230101&sort=exchangedate&order=asc&json"
    body = [
        {"cc": "USD", "rate": 36.5, "exchangedate": "01.01.2023"}
    ]

    responses.add(responses.GET, url, json=body, status=200)

    result = nbu_service.run_sync(bank.env, bank)
    assert result['stats']['created'] == 1
    assert result['stats']['updated'] == 0
    assert result['stats']['skipped'] == 0
    assert 'sync_stats' in result


def test_sync_to_system_rates():
    bank = FakeBank()
    # Add some fake dino rates
    bank.env['dino.currency.rate']._records = [
        SimpleNamespace(currency_id=SimpleNamespace(name='USD'), date='2023-01-01', rate=36.5, source='nbu')
    ]

    result = nbu_service.sync_to_system_rates(bank.env)
    assert result['created'] == 1
    assert result['updated'] == 0
    assert result['skipped'] == 0