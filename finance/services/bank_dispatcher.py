# -*- coding: utf-8 -*-
"""finance/services/bank_dispatcher.py

Сервис-диспетчер для интеграций с банками (Bank Integration Dispatcher).
Сопоставляет МФО банка с функцией-обработчиком синхронизации.
"""
import logging
from odoo.exceptions import UserError
from odoo import _

from . import bank_constants as const
from . import nbu_service

_logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# ФУНКЦИИ-ОБРАБОТЧИКИ СИНХРОНИЗАЦИИ
# ----------------------------------------------------------------------

def _sync_nbu(bank):
    """Обертка для синхронизации НБУ."""
    return nbu_service.run_sync(bank)

def _sync_privat(bank):
    """Логика синхронизации ПриватБанка."""
    _logger.info("Запуск синхронизации ПриватБанка: %s", bank.name)
    from . import privat_service

    try:
        import_result = privat_service.import_accounts(bank)
    except Exception as e:
        raise UserError(_("Ошибка при импорте счетов: %s") % e)

    stats_accounts = import_result.get('stats', {})
    msg_accounts = _("Импорт балансов завершён. Создано: %d, Обновлено: %d, Пропущено: %d") % (
        stats_accounts.get('created', 0), stats_accounts.get('updated', 0), stats_accounts.get('skipped', 0)
    )

    try:
        trans_result = privat_service.import_transactions(bank)
    except Exception as e:
        raise UserError(_("Ошибка при импорте транзакций: %s") % e)

    stats_trans = trans_result.get('stats', {})
    msg_trans = _("Импорт транзакций завершён. Создано: %d, Пропущено: %d") % (
        stats_trans.get('created', 0), stats_trans.get('skipped', 0)
    )
    if 'unknown_accounts' in stats_trans:
        msg_trans += _(", Неизвестные счета: %d") % stats_trans['unknown_accounts']

    full_msg = msg_accounts + "\n" + msg_trans

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'title': _('Импорт завершён'), 'message': full_msg, 'sticky': False}
    }

def _sync_mono(bank):
    """Заглушка для синхронизации Монобанка."""
    _logger.info("Запуск синхронизации Монобанка: %s", bank.name)

    accounts = bank.env['dino.bank.account'].search([('bank_id', '=', bank.id)])
    if not accounts:
        raise UserError(_("Для Монобанка не настроены счета."))

    # TODO: Вызов реального сервиса mono_service

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'title': _('Синхронизация Монобанка'), 'message': _("Запущено для %s счетов") % len(accounts), 'sticky': False}
    }

# ----------------------------------------------------------------------
# РЕЕСТР ДИСПЕТЧЕРА
# ----------------------------------------------------------------------

SYNC_HANDLERS = {
    const.MFO_NBU: _sync_nbu,
    const.MFO_PRIVAT: _sync_privat,
    const.MFO_MONO: _sync_mono,
}

def dispatch_sync(bank):
    """
    Основная точка входа. Находит функцию по МФО и вызывает её.
    """
    bank.ensure_one()

    handler = SYNC_HANDLERS.get(bank.mfo)

    if not handler:
        raise UserError(_("Синхронизация для банка с МФО %s не настроена.") % bank.mfo)

    _logger.info("Диспетчер: запуск %s для банка '%s'", handler.__name__, bank.name)
    return handler(bank)
