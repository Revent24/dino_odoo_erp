# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import json


class DinoBankTransaction(models.Model):
    _name = 'dino.bank.transaction'
    _description = _('Bank Transaction Buffer')
    _order = 'datetime desc, id desc'

    # Core Fields
    bank_account_id = fields.Many2one('dino.bank.account', string=_('Bank Account'), required=True, ondelete='cascade')
    datetime = fields.Datetime(string=_('Date & Time'), required=True, index=True)
    amount = fields.Monetary(
        string=_('Amount'),
        currency_field='currency_id',
        help=_("Transaction amount. Positive for income, negative for expenses.")
    )
    currency_id = fields.Many2one(related='bank_account_id.currency_id', store=True)
    description = fields.Text(string=_('Description'))
    balance_after = fields.Monetary(string=_('Balance After'), currency_field='currency_id')

    # Counterparty Details
    counterparty_name = fields.Char(string=_('Counterparty Name'))
    counterparty_iban = fields.Char(string=_('Counterparty IBAN'))
    counterparty_edrpou = fields.Char(string=_('Counterparty EDRPOU'))

    # Technical & Integration Fields
    external_id = fields.Char(string=_('External ID'), index=True, required=True, help=_("Unique transaction ID from the bank's API."))
    mcc = fields.Integer(string="MCC", help="Merchant Category Code (ISO 18245)")
    raw_data = fields.Text(string="Raw Data", help="Stores the original JSON data of the transaction.")

    # Computed fields for convenience
    debit = fields.Monetary(compute='_compute_debit_credit', string=_('Debit'), currency_field='currency_id')
    credit = fields.Monetary(compute='_compute_debit_credit', string=_('Credit'), currency_field='currency_id')

    _sql_constraints = [
        ('external_id_uniq', 'unique(bank_account_id, external_id)', 'The external transaction ID must be unique per bank account!')
    ]

    @api.depends('amount')
    def _compute_debit_credit(self):
        for trx in self:
            trx.debit = -trx.amount if trx.amount < 0 else 0.0
            trx.credit = trx.amount if trx.amount > 0 else 0.0

    @api.model
    def create_from_api(self, bank_account, payload):
        """
        A helper method to create a transaction record from a standardized API payload.
        This method should be called by specific bank integration services (mono, privat, etc.).

        :param bank_account: The `dino.bank.account` record this transaction belongs to.
        :param payload: A dictionary with standardized keys.
        :return: The newly created `dino.bank.transaction` record.
        """
        # Ensure raw data is stored as a string
        if 'raw_data' in payload and isinstance(payload['raw_data'], dict):
            payload['raw_data'] = json.dumps(payload['raw_data'], ensure_ascii=False)

        payload['bank_account_id'] = bank_account.id
        return self.create(payload)