import json
import responses
from api_integration.services.nbu_client import NBUClient

BASE = "https://bank.gov.ua"


def test_get_banks_success():
    client = NBUClient()
    url = BASE + "/NBUStatService/v1/statdirectory/banks?json"
    body = [{"mfo": "300001", "name": "National Bank of Ukraine"}]

    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, url, json=body, status=200)
        banks = client.get_banks(refresh=True)
        assert banks == body


def test_get_banks_cached():
    client = NBUClient()
    url = BASE + "/NBUStatService/v1/statdirectory/banks?json"
    body = [{"mfo": "300001", "name": "National Bank of Ukraine"}]

    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, url, json=body, status=200)
        # First call
        banks1 = client.get_banks(refresh=True)
        # Second call should use cache
        banks2 = client.get_banks(refresh=False)
        assert banks1 == banks2 == body
        assert len(rsps.calls) == 1  # Only one request made


def test_fetch_exchange_success():
    client = NBUClient()
    start_date = "2023-01-01"
    end_date = "2023-01-02"
    url = f"{BASE}/NBU_Exchange/exchange_site?start=20230101&end=20230102&sort=exchangedate&order=asc&json"
    body = [{"cc": "USD", "rate": 36.5, "exchangedate": "01.01.2023"}]

    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, url, json=body, status=200)
        data = client.fetch_exchange(start_date, end_date)
        assert data == body


def test_fetch_exchange_with_valcode():
    client = NBUClient()
    start_date = "2023-01-01"
    end_date = "2023-01-02"
    valcode = "USD"
    url = f"{BASE}/NBU_Exchange/exchange_site?start=20230101&end=20230102&sort=exchangedate&order=asc&json&valcode={valcode}"
    body = [{"cc": "USD", "rate": 36.5, "exchangedate": "01.01.2023"}]

    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, url, json=body, status=200)
        data = client.fetch_exchange(start_date, end_date, valcode)
        assert data == body


def test_get_bank_info_success():
    client = NBUClient()
    mfo = "300001"
    url = f"{BASE}/NBU_BankInfo/get_data_branch?glmfo={mfo}&json"
    body = {"mfo": "300001", "name": "National Bank of Ukraine"}

    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, url, json=body, status=200)
        info = client.get_bank_info(mfo)
        assert info == body