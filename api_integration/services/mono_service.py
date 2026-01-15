#
#  -*- File: api_integration/services/mono_service.py -*-
#

def import_mono_rates(bank, overwrite=True):
    """
    Импорт курсов покупки и продажи Монобанка.
    Выполняется 3-4 раза в день с перезаписью курсов на текущую дату.
    """
    _logger.info("import_mono_rates: Starting MonoBank exchange rates import")

    client = MonoClient(api_key=getattr(bank, 'api_key', None))

    try:
        data = client.fetch_exchange()
        _logger.info(f"import_mono_rates: Received {len(data) if data else 0} exchange rates")
    except Exception as e:
        _logger.error(f"import_mono_rates: Error fetching exchange rates: {e}")
        raise UserError(_("Ошибка получения курсов Монобанка: %s") % e)

    if not data:
        _logger.warning("import_mono_rates: No exchange data received")
        return {'stats': {'created': 0, 'updated': 0, 'skipped': 0}}

    # Текущая дата для всех курсов (перезапись на текущий день)
    today = fields.Date.today()

    buy_rates_data = []
    sell_rates_data = []

    for item in data:
        currency_code_a = item.get('currencyCodeA')  # базовая валюта (840=USD, 978=EUR)
        currency_code_b = item.get('currencyCodeB')  # валюта котировки (980=UAH)

        if currency_code_b != 980:  # Только к UAH
            continue

        rate_buy = item.get('rateBuy')
        rate_sell = item.get('rateSell')

        if not currency_code_a or rate_buy is None or rate_sell is None:
            continue

        # Маппинг кодов валют в символы
        currency_map = {840: 'USD', 978: 'EUR', 826: 'GBP'}
        ccy = currency_map.get(currency_code_a)

        if not ccy:
            continue

        # Добавляем курс покупки
        buy_rates_data.append({
            'currency_code': ccy,
            'rate': rate_buy,
            'date': today
        })

        # Добавляем курс продажи
        sell_rates_data.append({
            'currency_code': ccy,
            'rate': rate_sell,
            'date': today
        })

    if not buy_rates_data and not sell_rates_data:
        _logger.warning("import_mono_rates: No valid rates to import")
        return {'stats': {'created': 0, 'updated': 0, 'skipped': 0}}

    # Импорт buy курсов
    buy_result = import_rates_to_dino(bank.env, buy_rates_data, 'mono', 'buy', overwrite)

    # Импорт sell курсов
    sell_result = import_rates_to_dino(bank.env, sell_rates_data, 'mono', 'sell', overwrite)

    # Объединяем результаты
    total_stats = {
        'buy_created': buy_result['stats']['created'],
        'buy_updated': buy_result['stats']['updated'],
        'buy_skipped': buy_result['stats']['skipped'],
        'sell_created': sell_result['stats']['created'],
        'sell_updated': sell_result['stats']['updated'],
        'sell_skipped': sell_result['stats']['skipped']
    }

    _logger.info(f"import_mono_rates: Import completed - Buy: {buy_result['stats']}, Sell: {sell_result['stats']}")

    return {'stats': total_stats}# End of file api_integration/services/mono_service.py
