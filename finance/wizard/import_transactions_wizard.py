# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ImportTransactionsWizard(models.TransientModel):
    _name = 'dino.import.transactions.wizard'
    _description = _('Wizard to import bank transactions for a selected period')

    bank_id = fields.Many2one('dino.bank', string=_('Bank'), required=True, readonly=True)
    date_from = fields.Date(string=_('Date From'), required=True)
    date_to = fields.Date(string=_('Date To'), required=True, default=fields.Date.context_today)

    def action_run_import(self):
        """Disabled: transaction import is removed in this version.

        To keep the UI stable we provide an explicit message instead of running the import.
        """
        raise UserError(_('Импорт транзакций отключён. Функциональность удалена.'))
