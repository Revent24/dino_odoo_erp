import json
import responses
from api_integration.services.privat_client import PrivatClient

BASE = "https://acp.privatbank.ua/api"


def test_check_api_status_success():
    token = "fake-token"
    client = PrivatClient(api_key=token, session=None)
    url = BASE + "/statements/settings"
    body = {"status": "SUCCESS", "settings": {"phase": "WRK", "work_balance": "N"}}

    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, url, json=body, status=200)
        ok = client.check_api_status()
        assert ok is True


def test_check_api_status_not_working():
    token = "fake-token"
    client = PrivatClient(api_key=token, session=None)
    url = BASE + "/statements/settings"
    body = {"status": "SUCCESS", "settings": {"phase": "MAINT", "work_balance": "Y"}}

    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, url, json=body, status=200)
        ok = client.check_api_status()
        assert ok is False


def test_fetch_transactions_iter_pagination():
    token = "fake-token"
    client = PrivatClient(api_key=token, session=None)
    url = BASE + "/statements/transactions"

    page1 = {"status": "SUCCESS", "exist_next_page": 1, "next_page_id": "abc123", "transactions": [{"id": 1}]}
    page2 = {"status": "SUCCESS", "exist_next_page": 0, "transactions": [{"id": 2}]}

    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, url, json=page1, status=200)
        # The second call expects followId param; responses will match by URL without params, so add second same URL
        rsps.add(rsps.GET, url, json=page2, status=200)

        pages = list(client.fetch_transactions_iter('01-01-2020'))
        assert len(pages) == 2
        assert pages[0]['transactions'][0]['id'] == 1
        assert pages[1]['transactions'][0]['id'] == 2
