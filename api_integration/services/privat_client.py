# -*- coding: utf-8 -*-
import logging
import requests
import json
import time
from datetime import date
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_logger = logging.getLogger(__name__)

BASE_URL = 'https://acp.privatbank.ua/api'

class PrivatClient:
    def __init__(self, api_key, client_id=None, timeout=30, request_delay=0.3):
        if not api_key:
            raise ValueError("API key (token) is required")
        
        self.timeout = timeout
        self.request_delay = request_delay
        self.session = requests.Session()
        
        # Настраиваем заголовки один раз для всех запросов
        self.session.headers.update({
            'User-Agent': 'DinoERP Integration',
            'token': api_key,
            'Content-Type': 'application/json;charset=cp1251' # На всякий случай, хотя для GET не критично
        })
        
        # Если это группа предприятий, добавляем ID
        if client_id:
            self.session.headers['id'] = str(client_id)

        # Retry strategy
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def _get(self, endpoint, params=None):
        """Выполняет GET запрос с автоматической обработкой кодировки CP1251."""
        url = f"{BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            # Обработка ошибки 416 - дата за пределами доступного диапазона
            if response.status_code == 416:
                error_msg = f"Дата {params.get('startDate')} за пределами доступного диапазона API ПриватБанк. Рекомендуется использовать данные не старше 1095 дней (3 года)."
                _logger.error(error_msg)
                return {'status': 'ERROR', 'error': error_msg, 'transactions': [], 'balances': []}
            
            response.raise_for_status()
            
            # Приват часто отдает cp1251, requests иногда не угадывает
            try:
                return response.json()
            except ValueError:
                text = response.content.decode('cp1251', errors='replace')
                return json.loads(text)
                
        except requests.RequestException as e:
            _logger.error(f"PrivatBank API Error [{endpoint}]: {e}")
            raise

    def check_api_status(self):
        """Проверка статуса API."""
        data = self._get('/statements/settings')
        settings = data.get('settings', {})
        # Логика: если phase=WRK и work_balance=N — все ок.
        return settings.get('phase') == 'WRK' and settings.get('work_balance') == 'N'

    def fetch_balances(self, date_str=None):
        """Получает балансы по всем счетам."""
        d = date_str or date.today().strftime('%d-%m-%Y')
        params = {'startDate': d, 'endDate': d}
        
        data = self._get('/statements/balance', params=params)
        return data.get('balances', []) if data.get('status') == 'SUCCESS' else []

    def fetch_exchange(self, date=None):
        """
        Получает курсы валют Приватбанка (покупка/продажа).
        Возвращает список словарей с ключами: ccy, base_ccy, buy, sale
        """
        url = "https://api.privatbank.ua/p24api/pubinfo"
        params = {'exchange': '', 'coursid': '5'}  # coursid=5 - наличные курсы

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            _logger.info(f"Privat exchange rates received: {len(data) if data else 0} currencies")
            return data if data else []
        except requests.RequestException as e:
            _logger.error(f"PrivatBank exchange API error: {e}")
            raise

    def get_transactions_generator(self, account_num=None, start_date=None, end_date=None, limit=100):
        """
        Генератор, который листает страницы транзакций.
        Автоматически обрабатывает followId.
        """
        params = {
            'startDate': start_date,
            'limit': limit
        }
        # Добавляем acc только если он передан
        if account_num:
            params['acc'] = account_num

        if end_date:
            params['endDate'] = end_date

        follow_id = None

        while True:
            if follow_id:
                params['followId'] = follow_id

            data = self._get('/statements/transactions', params=params)

            # Если статус ERROR (например, 416), логируем и прерываем
            if data.get('status') == 'ERROR':
                _logger.error(f"API error: {data.get('error')}")
                raise Exception(data.get('error', 'Unknown API error'))
            
            # Если статус не SUCCESS, прерываем
            if data.get('status') != 'SUCCESS':
                _logger.warning(f"Error fetching transactions page for {account_num}: {data}")
                break

            transactions = data.get('transactions', [])
            if transactions:
                yield transactions

            # Проверка на наличие следующей страницы
            if data.get('exist_next_page') and data.get('next_page_id'):
                follow_id = data['next_page_id']
                if self.request_delay:
                    time.sleep(self.request_delay)
            else:
                break

    def get_balance_history_generator(self, account_num=None, start_date=None, end_date=None, limit=100):
        """
        Генератор, который листает страницы истории балансов.
        Автоматически обрабатывает followId.
        """
        params = {
            'startDate': start_date,
            'limit': limit
        }
        # Добавляем acc только если он передан
        if account_num:
            params['acc'] = account_num

        if end_date:
            params['endDate'] = end_date

        follow_id = None

        while True:
            if follow_id:
                params['followId'] = follow_id

            data = self._get('/statements/balance', params=params)

            # Если статус ERROR (например, 416), логируем и прерываем
            if data.get('status') == 'ERROR':
                _logger.error(f"API error: {data.get('error')}")
                raise Exception(data.get('error', 'Unknown API error'))
            
            # Если статус не SUCCESS, прерываем
            if data.get('status') != 'SUCCESS':
                _logger.warning(f"Error fetching balance history page for {account_num}: {data}")
                break

            balances = data.get('balances', [])
            if balances:
                yield balances

            # Проверка на наличие следующей страницы
            if data.get('exist_next_page') and data.get('next_page_id'):
                follow_id = data['next_page_id']
                if self.request_delay:
                    time.sleep(self.request_delay)
            else:
                break
