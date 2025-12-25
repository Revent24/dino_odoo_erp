# -*- coding: utf-8 -*-
"""
Service Dispatcher for Bank Integrations.

This module acts as a registry that maps a bank's MFO code to the specific
service function responsible for handling its synchronization logic.
This approach decouples the `dino.bank` model from the concrete implementation
of each bank's integration.
"""
import logging
from odoo.exceptions import UserError
from odoo import _

from . import bank_constants as const
from . import nbu_service
# Import other services as they are implemented
# from . import privat_service
# from . import mono_service

_logger = logging.getLogger(__name__)


def run_privat_sync(bank):
    """
    Full synchronization logic for PrivatBank.
    Step 1: Import/update accounts.
    Step 2: Import transactions for each account.
    """
    _logger.info("Dispatching to PrivatBank full sync for bank: %s", bank.name)
    
    # --- Step 1: Import and update bank accounts ---
    from . import privat_service
    try:
        acc_stats = privat_service.import_accounts(bank)
        _logger.info("PrivatBank account sync stats: %s", acc_stats)
    except Exception as e:
        _logger.error("Error during PrivatBank account import: %s", e, exc_info=True)
        raise UserError(_("Error during account import for PrivatBank: %s") % e)

    # --- Step 2: Import transactions for all linked accounts ---
    accounts = bank.env['dino.bank.account'].search([('bank_id', '=', bank.id)])
    if not accounts:
        # This can happen if the import returned no accounts
        message = _(
            "PrivatBank account import complete. No active accounts found to synchronize transactions."
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('PrivatBank Sync'), 'message': message, 'sticky': True}
        }

    _logger.info("Proceeding to import transactions for %d PrivatBank account(s).", len(accounts))
    # Step 2: Import transactions for each account and aggregate stats
    trx_totals = {'created': 0, 'updated': 0, 'skipped': 0}
    for account in accounts:
        try:
            trx_stats = privat_service.import_transactions(bank, account=account)
            _logger.info('Imported transactions for account %s: %s', account.account_number, trx_stats)
            for k in ('created', 'updated', 'skipped'):
                trx_totals[k] += trx_stats.get(k, 0)
        except Exception as e:
            _logger.error('Error importing transactions for account %s: %s', account.account_number, e, exc_info=True)

    message = _(
        "PrivatBank Sync Summary:\n"
        "Accounts Created: %(created)s\n"
        "Accounts Updated: %(updated)s\n"
        "Transactions Created: %(tx_created)s\n"
        "Transactions Updated: %(tx_updated)s\n"
        "Transactions Skipped: %(tx_skipped)s"
    ) % {
        'created': acc_stats.get('created', 0),
        'updated': acc_stats.get('updated', 0),
        'tx_created': trx_totals['created'],
        'tx_updated': trx_totals['updated'],
        'tx_skipped': trx_totals['skipped'],
    }

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'title': _('PrivatBank Sync Finished'), 'message': message, 'sticky': True}
    }


def run_mono_sync(bank):
    """Placeholder for Monobank synchronization logic."""
    _logger.info("Dispatching to Monobank transaction sync for bank: %s", bank.name)
    # TODO: Implement the actual logic by calling mono_service
    accounts = bank.env['dino.bank.account'].search([('bank_id', '=', bank.id)])
    if not accounts:
        raise UserError(_("No accounts are configured for Monobank. Please add accounts to synchronize."))

    message = _("Synchronization started for %s account(s) of Monobank.") % len(accounts)
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'title': _('Monobank Sync'), 'message': message, 'sticky': False}
    }


# The main dispatcher registry
SYNC_DISPATCHER = {
    const.MFO_NBU: nbu_service.run_sync,
    const.MFO_PRIVAT: run_privat_sync,
    const.MFO_MONO: run_mono_sync,
}


def dispatch_sync(bank):
    """
    Finds and executes the appropriate sync function for the given bank record.
    
    :param bank: A `dino.bank` recordset (should be a singleton).
    :return: The result of the dispatched function (typically an Odoo action).
    """
    bank.ensure_one()
    sync_function = SYNC_DISPATCHER.get(bank.mfo)

    if not sync_function:
        raise UserError(_("Synchronization is not configured for a bank with MFO %s.") % bank.mfo)

    _logger.info("Dispatching sync for bank '%s' (MFO: %s) to function %s", 
                 bank.name, bank.mfo, sync_function.__name__)
    
    return sync_function(bank)
