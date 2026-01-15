#
#  -*- File: partners/models/dino_partner_bank_account.py -*-
#
# -*- coding: utf-8 -*-
from odoo import models, fields, api


class DinoPartnerBankAccount(models.Model):
    """
    Банковские счета контрагентов
    Один контрагент может иметь несколько счетов в разных банках
    """
    _name = 'dino.partner.bank.account'
    _description = 'Partner Bank Account'
    _order = 'is_default desc, sequence, id'
    
    partner_id = fields.Many2one('dino.partner', string='Partner', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    
    # Банковская информация
    iban = fields.Char('IBAN', required=True, help='Номер рахунку у форматі UA...')
    bank_name = fields.Char('Bank Name', help='Назва банку')
    bank_city = fields.Char('Bank City', help='Місто банку')
    bank_mfo = fields.Char('Bank MFO', help='МФО банку (6 цифр)')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.UAH'))
    
    # Статус
    is_default = fields.Boolean('Default Account', default=False, help='Основний рахунок контрагента')
    active = fields.Boolean('Active', default=True)
    
    # Дополнительно
    notes = fields.Text('Notes')
    
    _sql_constraints = [
        ('iban_partner_unique', 'unique(iban, partner_id)', 'This IBAN already exists for this partner!'),
    ]
    
    @api.model
    def create(self, vals):
        """При создании первого счета автоматически делаем его основным"""
        record = super().create(vals)
        
        # Если это первый счет партнера - делаем его основным
        if not record.partner_id.bank_account_ids.filtered(lambda a: a.is_default and a.id != record.id):
            record.is_default = True
        
        return record
    
    def write(self, vals):
        """Если делаем счет основным - снимаем флаг с других счетов"""
        result = super().write(vals)
        
        if vals.get('is_default'):
            for record in self:
                # Снять is_default с других счетов этого партнера
                other_accounts = record.partner_id.bank_account_ids.filtered(
                    lambda a: a.is_default and a.id != record.id
                )
                if other_accounts:
                    other_accounts.write({'is_default': False})
        
        return result
    
    def name_get(self):
        """Отображение: IBAN (Bank Name)"""
        result = []
        for record in self:
            name = record.iban or 'New Account'
            if record.bank_name:
                name = f"{name} ({record.bank_name})"
            if record.is_default:
                name = f"★ {name}"
            result.append((record.id, name))
        return result
    
    @api.model
    def find_or_create(self, partner_id, iban, bank_name=None, bank_city=None, bank_mfo=None):
        """
        Найти счет по IBAN или создать новый
        
        Args:
            partner_id: ID контрагента
            iban: номер счета
            bank_name: название банка (опционально)
            bank_city: город банка (опционально)
            bank_mfo: МФО банка (опционально)
            
        Returns:
            dino.partner.bank.account record
        """
        if not iban:
            return self.env['dino.partner.bank.account']
        
        # Поиск существующего счета
        account = self.search([
            ('partner_id', '=', partner_id),
            ('iban', '=', iban)
        ], limit=1)
        
        # Если найден - обновляем данные
        if account:
            update_vals = {}
            if bank_name and not account.bank_name:
                update_vals['bank_name'] = bank_name
            if bank_city and not account.bank_city:
                update_vals['bank_city'] = bank_city
            if bank_mfo and not account.bank_mfo:
                update_vals['bank_mfo'] = bank_mfo
            
            if update_vals:
                account.write(update_vals)
            
            return account
        
        # Создаем новый счет
        vals = {
            'partner_id': partner_id,
            'iban': iban,
        }
        if bank_name:
            vals['bank_name'] = bank_name
        if bank_city:
            vals['bank_city'] = bank_city
        if bank_mfo:
            vals['bank_mfo'] = bank_mfo
        
        return self.create(vals)
# End of file partners/models/dino_partner_bank_account.py
