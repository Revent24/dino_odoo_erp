#
#  -*- File: finance/models/dino_bank_transaction.py -*-
#
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import json


class DinoBankTransaction(models.Model):
    _name = 'dino.bank.transaction'
    _description = _('Bank Transaction Buffer')
    _order = 'datetime desc, id desc'

    # Computed name for display
    name = fields.Char(string=_('Name'), compute='_compute_name', store=False)

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
    partner_id = fields.Many2one('dino.partner', string=_('Counterparty'), index=True, help=_('Linked partner (counterparty)'))
    counterparty_name = fields.Char(string=_('Counterparty Name'))
    counterparty_iban = fields.Char(string=_('Counterparty IBAN'))
    counterparty_edrpou = fields.Char(string=_('Counterparty EDRPOU'))
    counterparty_bank_name = fields.Char(string=_('Bank Name'))
    counterparty_bank_city = fields.Char(string=_('Bank City'))
    counterparty_bank_mfo = fields.Char(string=_('Bank MFO'), help=_('МФО банку (6 цифр)'))

    # Technical & Integration Fields
    external_id = fields.Char(string=_('External ID'), index=True, required=True, help=_("Unique transaction ID from the bank's API."))
    document_number = fields.Char(string=_('Document Number'), help=_("Bank document number (NUM_DOC)"))
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

    @api.depends('datetime', 'document_number', 'external_id', 'amount', 'currency_id')
    def _compute_name(self):
        """Compute display name: date document_number amount currency"""
        for rec in self:
            date_str = rec.datetime.strftime('%Y-%m-%d') if rec.datetime else ''
            doc_num = rec.document_number or rec.external_id or ''
            # Format amount with comma as decimal separator
            amount_str = f"{rec.amount:.2f}".replace('.', ',') if rec.amount else '0,00'
            currency = rec.currency_id.name if rec.currency_id else ''
            rec.name = f"{date_str} {doc_num} {amount_str} {currency}"

    def name_get(self):
        """Display transaction as: date document_number amount currency"""
        result = []
        for rec in self:
            result.append((rec.id, rec.name or f"Transaction {rec.id}"))
        return result

    @api.model
    def _find_or_create_partner(self, edrpou, name=None, iban=None, bank_name=None, bank_city=None, bank_mfo=None):
        """
        Find or create partner by EDRPOU and create/find bank account.
        
        :param edrpou: Counterparty EDRPOU
        :param name: Counterparty name
        :param iban: Counterparty IBAN
        :param bank_name: Bank name
        :param bank_city: Bank city
        :param bank_mfo: Bank MFO
        :return: dino.partner record or False
        """
        if not edrpou:
            return False
        
        Partner = self.env['dino.partner']
        BankAccount = self.env['dino.partner.bank.account']
        
        # Search for existing partner by EDRPOU
        partner = Partner.search([('egrpou', '=', edrpou)], limit=1)
        
        if not partner:
            # Create new partner
            vals = {
                'name': name or f'Partner {edrpou}',
                'egrpou': edrpou,
            }
            partner = Partner.create(vals)
        
        # Create or find bank account if IBAN provided
        if iban and partner:
            BankAccount.find_or_create(
                partner_id=partner.id,
                iban=iban,
                bank_name=bank_name,
                bank_city=bank_city,
                bank_mfo=bank_mfo
            )
        
        return partner

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to automatically link partner by EDRPOU"""
        # Auto-link partner if EDRPOU is provided
        for vals in vals_list:
            if vals.get('counterparty_edrpou') and not vals.get('partner_id'):
                partner = self._find_or_create_partner(
                    edrpou=vals.get('counterparty_edrpou'),
                    name=vals.get('counterparty_name'),
                    iban=vals.get('counterparty_iban'),
                    bank_name=vals.get('counterparty_bank_name'),
                    bank_city=vals.get('counterparty_bank_city'),
                    bank_mfo=vals.get('counterparty_bank_mfo')
                )
                if partner:
                    vals['partner_id'] = partner.id
        
        return super(DinoBankTransaction, self).create(vals_list)

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
        return self.create(payload)# End of file finance/models/dino_bank_transaction.py
