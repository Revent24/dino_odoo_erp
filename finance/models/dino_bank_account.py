#
#  -*- File: finance/models/dino_bank_account.py -*-
#
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DinoBankAccount(models.Model):
    _name = 'dino.bank.account'
    _description = _('Company Bank Account')
    _order = 'name'

    name = fields.Char(string=_('Account Name'), required=True, index=True)
    bank_id = fields.Many2one('dino.bank', string=_('Bank'), required=True, ondelete='restrict')
    account_number = fields.Char(string=_('Account Number (IBAN)'), required=True)
    currency_id = fields.Many2one('res.currency', string=_('Currency'), required=True)
    
    # Balance fields from API
    balance = fields.Monetary(string=_('Current Balance (Out)'), currency_field='currency_id', help="Исходящий остаток на конец дня")
    balance_start = fields.Monetary(string=_('Start Balance (In)'), currency_field='currency_id', help="Входящий остаток на начало дня")
    turnover_debit = fields.Monetary(string=_('Turnover Debit'), currency_field='currency_id', help="Сумма списаний за период")
    turnover_credit = fields.Monetary(string=_('Turnover Credit'), currency_field='currency_id', help="Сумма зачислений за период")
    balance_end_date = fields.Date(string="Balance Date", help="Дата, на которую актуальны балансы")

    last_import_date = fields.Datetime(string=_('Last Import'))

    # Technical fields
    external_id = fields.Char(string=_('External ID'), index=True, help=_("The unique account identifier from the bank's API."))
    account_type = fields.Char(string=_('Account Type'), help=_("e.g., 'black', 'white' for Monobank."))
    active = fields.Boolean(string=_('Active'), default=True)
    show_in_transactions = fields.Boolean(string=_('Show in Transactions'), default=True)

    _sql_constraints = [
        ('account_number_uniq', 'unique(account_number)', 'The account number (IBAN) must be unique!'),
    ]

    def name_get(self):
        result = []
        for account in self:
            name = f"{account.name} ({account.account_number})"
            result.append((account.id, name))
        return result
# End of file finance/models/dino_bank_account.py
