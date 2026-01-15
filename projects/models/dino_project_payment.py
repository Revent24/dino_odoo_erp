#
#  -*- File: projects/models/dino_project_payment.py -*-
#
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DinoProjectPayment(models.Model):
    _name = 'dino.project.payment'
    _description = _('Project Payment')
    _order = 'date desc, id desc'

    name = fields.Char(string=_('Name'), required=True)
    date = fields.Date(string=_('Date'), required=True, default=fields.Date.today)
    number = fields.Char(string=_('Number'))
    purpose = fields.Text(string=_('Purpose'))
    amount = fields.Monetary(string=_('Amount'), currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string=_('Currency'), default=lambda self: self.env.company.currency_id)
    
    project_id = fields.Many2one('dino.project', string=_('Project'), required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(related='project_id.partner_id', string=_('Partner'), store=True, readonly=True)
    project_date = fields.Date(related='project_id.date', string=_('Project Date'), store=True, readonly=True)
    transaction_id = fields.Many2one(
        'dino.bank.transaction', 
        string=_('Transaction'), 
        ondelete='set null', 
        index=True
    )
    
    # Related fields from transaction for convenience
    transaction_amount = fields.Monetary(related='transaction_id.amount', string=_('Transaction Amount'), readonly=True)
    transaction_date = fields.Datetime(related='transaction_id.datetime', string=_('Transaction Date'), readonly=True)
# End of file projects/models/dino_project_payment.py
