# -*- coding: utf-8 -*-
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

# Глобальный кэш (в рамках процесса Odoo)
_BANKS_CACHE = {'data': [], 'expires': datetime.min}

class NBUClient:
    """
    Клиент для API НБУ. 
    Использует requests.Session для ускорения серии запросов.
    """
    
    BASE_URL = 'https://bank.gov.ua'

    def __init__(self, user_agent='DinoERP/1.0', timeout=20):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'application/json'
        })
        self.timeout = timeout

    def get_banks(self, refresh=False):
        """Получает список банков (кэш на 24 часа)."""
        now = datetime.now()
        
        # Если кэш валиден — отдаем его сразу
        if not refresh and _BANKS_CACHE['expires'] > now:
            return _BANKS_CACHE['data']

        # Список эндпоинтов (основной и резервный)
        endpoints = [
            '/NBUStatService/v1/statdirectory/banks?json',
            '/NBUStatService/v1/statdirectory/banks' # Бывает, что json отдается и без явного ?json
        ]

        for ep in endpoints:
            try:
                # session.get автоматически подставит базовые хедеры
                resp = self.session.get(f"{self.BASE_URL}{ep}", timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    # Обновляем кэш
                    _BANKS_CACHE['data'] = data
                    _BANKS_CACHE['expires'] = now + timedelta(hours=24)
                    return data
            except requests.RequestException as e:
                _logger.warning("NBU API warning (%s): %s", ep, e)
                continue
        
        # Если ничего не сработало
        _logger.error("Не удалось получить список банков НБУ ни по одному адресу.")
        return []

    def fetch_exchange(self, start_date, end_date, valcode=None):
        """
        Получает курсы валют за период.
        Использует params для безопасного формирования URL.
        """
        url = f"{self.BASE_URL}/NBU_Exchange/exchange_site"
        
        params = {
            'start': start_date.strftime('%Y%m%d'),
            'end': end_date.strftime('%Y%m%d'),
            'sort': 'exchangedate',
            'order': 'asc',
            'json': '' # Пустой ключ для флага &json
        }
        
        if valcode:
            params['valcode'] = valcode

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            _logger.error("Ошибка получения курсов НБУ: %s", e)
            raise

    def get_bank_info(self, mfo):
        """Получает инфо по конкретному МФО."""
        url = f"{self.BASE_URL}/NBU_BankInfo/get_data_branch"
        params = {'glmfo': mfo, 'json': ''}

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            
            # Хак для НБУ: иногда API глючит с ?json, пробуем без него
            if resp.status_code == 400:
                resp = self.session.get(url, params={'glmfo': mfo}, timeout=self.timeout)
            
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            _logger.warning("Ошибка поиска банка по МФО %s: %s", mfo, e)
            raise
