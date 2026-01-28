#
#  -*- File: partners/models/dino_partners.py -*-
#
import re
import logging
from datetime import datetime

import requests

from odoo import models, fields, _, api
from odoo.osv.expression import expression

_logger = logging.getLogger(__name__)


class DinoPartner(models.Model):
    _name = 'dino.partner'
    _description = 'Partner'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mixin.auto.translate']

    name = fields.Char(string='Name', required=True, translate=True, tracking=True)
    full_name = fields.Char(string='Full Name', translate=True)
    name_short = fields.Char(string='Short Name', translate=True)
    egrpou = fields.Char(string='EGRPOU', index=True)
    
    # Банковские счета (через отдельную модель)
    bank_account_ids = fields.One2many('dino.partner.bank.account', 'partner_id', string='Bank Accounts')
    bank_account_count = fields.Integer('Bank Accounts', compute='_compute_bank_account_count')
    default_bank_account_id = fields.Many2one('dino.partner.bank.account', string='Default Account', compute='_compute_default_bank_account', store=False)
    
    address = fields.Char(string='Address', translate=True)
    phone = fields.Char(string='Phone', help='Телефони контрагента')
    director = fields.Char(string='Director', translate=True)
    director_gen = fields.Char(string='Director (Gen)', translate=True)
    kved = fields.Char(string='KVED', translate=True)
    kved_number = fields.Char(string='KVED Number')
    inn = fields.Char(string='INN', index=True)
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    inn_date = fields.Date(string='INN Date')
    last_update = fields.Date(string='Last Update')
    tax_system_id = fields.Many2one('dino.tax.system', string='Tax System')
    vat_rate = fields.Float(string='VAT Rate (%)', compute='_compute_vat_rate', store=False, readonly=True)
    category_id = fields.Many2one('dino.component.category', string='Default Category')
    # ownership_type_id removed (ownership model deleted)

    contact_ids = fields.One2many('dino.partner.contact', 'partner_id', string='Contacts')

    project_ids = fields.One2many('dino.project', 'partner_id', string='Projects')
    project_count = fields.Integer(string='Number of Projects', compute='_compute_project_count')

    partner_nomenclature_ids = fields.One2many('dino.partner.nomenclature', 'partner_id', string='Nomenclature Mapping')
    partner_nomenclature_count = fields.Integer(string='Nomenclature', compute='_compute_partner_nomenclature_count')

    document_ids = fields.One2many('dino.operation.document', 'partner_id', string='Documents')
    document_count = fields.Integer(string='Number of Documents', compute='_compute_document_count')

    transaction_ids = fields.One2many('dino.bank.transaction', 'partner_id', string='Bank Transactions')
    transaction_count = fields.Integer(string='Number of Transactions', compute='_compute_transaction_count')

    def _compute_partner_nomenclature_count(self):
        for rec in self:
            rec.partner_nomenclature_count = self.env['dino.partner.nomenclature'].search_count([('partner_id', '=', rec.id)])
    
    def _compute_bank_account_count(self):
        """Подсчет количества банковских счетов"""
        for rec in self:
            rec.bank_account_count = len(rec.bank_account_ids)
    
    def _compute_default_bank_account(self):
        """Получить основной банковский счет"""
        for rec in self:
            rec.default_bank_account_id = rec.bank_account_ids.filtered(lambda a: a.is_default)[:1]

    def action_view_partner_nomenclature(self):
        self.ensure_one()
        return {
            'name': 'Nomenclature',
            'type': 'ir.actions.act_window',
            'res_model': 'dino.partner.nomenclature',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    # Partner type toggles (legacy booleans kept for compatibility)
    partner_is_customer = fields.Boolean(string='Customer', default=False)

    def _compute_project_count(self):
        for rec in self:
            rec.project_count = self.env['dino.project'].search_count([('partner_id', '=', rec.id)])

    def action_view_projects(self):
        self.ensure_one()
        return {
            'name': 'Projects',
            'type': 'ir.actions.act_window',
            'res_model': 'dino.project',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def _compute_document_count(self):
        for rec in self:
            rec.document_count = self.env['dino.operation.document'].search_count([('partner_id', '=', rec.id)])

    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = self.env['dino.bank.transaction'].search_count([('partner_id', '=', rec.id)])

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'name': 'Bank Transactions',
            'type': 'ir.actions.act_window',
            'res_model': 'dino.bank.transaction',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_documents(self):
        self.ensure_one()
        return {
            'name': 'Documents',
            'type': 'ir.actions.act_window',
            'res_model': 'dino.operation.document',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
    partner_is_vendor = fields.Boolean(string='Vendor', default=False)

    # New: tags/multi-choice for partner types
    tag_ids = fields.Many2many(
        'dino.partner.tag',
        'dino_partner_tag_rel',
        'partner_id',
        'tag_id',
        string='Type',
    )

    partner_type = fields.Char(string='Partner Type', compute='_compute_partner_type')

    @api.depends('partner_is_customer', 'partner_is_vendor')
    def _compute_partner_type(self):
        for rec in self:
            types = []
            # First, collect explicit tags
            if rec.tag_ids:
                types = [t.name for t in rec.tag_ids]
            else:
                # Fallback to legacy booleans
                if rec.partner_is_customer:
                    types.append('Customer')
                if rec.partner_is_vendor:
                    types.append('Vendor')
            rec.partner_type = ', '.join(types) if types else False

    @api.onchange('egrpou')
    def _onchange_egrpou(self):
        """When user enters EGRPOU on the form, fetch registry data and pre-fill the fields.

        This happens before create/write, so it allows the required `name` to be populated
        automatically and the user can save without typing `name` manually.
        """
        okpo = (self.egrpou or '').strip()
        if not okpo:
            return
        try:
            # Use service from api_integration
            from odoo.addons.dino_erp.api_integration.services.partners_service import fetch_partner_registry_data
            vals = fetch_partner_registry_data(okpo)
        except Exception:
            logging.getLogger(__name__).exception('Error fetching registry on onchange for %s', okpo)
            return
        if not vals:
            return
        # Apply fetched values to the in-memory record (no write)
        for k, v in vals.items():
            try:
                setattr(self, k, v)
            except Exception:
                logging.getLogger(__name__).warning('Cannot set field %s on onchange', k)

    # Do not redefine message_follower_ids here — mail.thread provides followers/messages fields
    def _get_fields_to_translate(self):
        return ['name', 'full_name']

    @api.depends('tax_system_id', 'tag_ids')
    def _compute_vat_rate(self):
        for rec in self:
            if rec.tax_system_id and rec.tax_system_id.vat_rate is not None:
                rec.vat_rate = rec.tax_system_id.vat_rate
            else:
                rec.vat_rate = 0.0

    @api.onchange('tag_ids')
    def _onchange_tag_ids_update_vat(self):
        """Recompute vat_rate when tags change (in case tax system is changed by external logic)."""
        for rec in self:
            if rec.tax_system_id and rec.tax_system_id.vat_rate is not None:
                rec.vat_rate = rec.tax_system_id.vat_rate
            else:
                rec.vat_rate = 0.0
    
    def ensure_tax_system(self, vat_rate=None):
        """
        Ensure partner has tax system set. If not, find or create appropriate tax system.
        
        :param vat_rate: VAT rate to set (if creating new tax system), defaults to partner's current vat_rate
        :return: tax system record
        """
        self.ensure_one()
        
        # If already has tax system, return it
        if self.tax_system_id:
            return self.tax_system_id
        
        # Determine VAT rate to use
        if vat_rate is None:
            vat_rate = 20.0  # Default VAT rate in Ukraine
        
        # Try to find existing tax system with this VAT rate
        TaxSystem = self.env['dino.tax.system']
        tax_system = TaxSystem.search([('vat_rate', '=', vat_rate)], limit=1)
        
        # If not found, create new tax system
        if not tax_system:
            _logger.info(f"Creating new tax system with VAT rate {vat_rate}%")
            tax_system = TaxSystem.create({
                'name': f'VAT {vat_rate}%',
                'vat_rate': vat_rate
            })
        
        # Assign tax system to partner
        self.tax_system_id = tax_system
        _logger.info(f"Assigned tax system '{tax_system.name}' to partner {self.name} (EGRPOU: {self.egrpou})")
        
        return tax_system

    @staticmethod
    def _parse_date_str(d):
        if not d:
            return False
        d = d.strip()
        for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(d, fmt).date()
            except Exception:
                continue
        return False

    def action_update_from_registry(self):
        """Update records from the public registry by `egrpou` (OKPO).

        Can be called for a recordset. Uses external API
        `https://adm.tools/action/gov/api/?egrpou=<egrpou>` and parses XML response.
        """
        from odoo.exceptions import UserError
        from odoo.addons.dino_erp.api_integration.services.partners_service import fetch_partner_registry_data
        
        updated = 0
        errors = []
        
        for rec in self:
            okpo = (rec.egrpou or '').strip()
            if not okpo:
                _logger.debug('No EGRPOU for partner %s (%s), skip', rec.id, rec.name)
                errors.append(f'{rec.name}: відсутній ЄДРПОУ')
                continue
            
            try:
                _logger.info(f'🔄 Updating partner {rec.name} (EGRPOU: {okpo}) from registry...')
                vals = fetch_partner_registry_data(okpo)
                
                _logger.info(f"📦 Received vals from API: {vals}")
                
                if vals:
                    _logger.info(f"✍️ Writing to partner {rec.id}: {list(vals.keys())}")
                    rec.write(vals)
                    updated += 1
                    _logger.info(f'✅ Updated partner {rec.name}: {list(vals.keys())}')
                else:
                    errors.append(f'{rec.name} (ЄДРПОУ {okpo}): дані не знайдено в реєстрі')
                    _logger.warning(f'❌ No data returned for partner {rec.name} (EGRPOU: {okpo})')
                    
            except Exception as e:
                error_msg = str(e)
                errors.append(f'{rec.name} (ЄДРПОУ {okpo}): {error_msg}')
                _logger.exception(f'Failed to update partner {rec.id} ({rec.name}): {e}')
        
        # Показати результат користувачу
        if updated > 0 and not errors:
            # Оновити форму після успішного оновлення
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'type': 'success',
                'title': '✅ Успішно оновлено',
                'message': f'Оновлено {updated} контрагент(ів) з реєстру',
                'sticky': False,
            })
            # Повернути action для перезавантаження форми
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        elif updated > 0 and errors:
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'type': 'warning',
                'title': '⚠️ Частково оновлено',
                'message': f'Оновлено: {updated}\nПомилки: {len(errors)}\n\n' + '\n'.join(errors[:3]),
                'sticky': True,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        elif errors:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '❌ Помилка оновлення',
                    'message': '\n'.join(errors[:5]),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    @api.model
    def create(self, vals):
        record = super(DinoPartner, self).create(vals)
        try:
            # If egrpou provided on create, update from registry
            if vals.get('egrpou'):
                record.action_update_from_registry()
        except Exception:
            logging.getLogger(__name__).exception('Error updating partner on create: %s', record.id)
        # Auto-assign tag based on context default_partner_role (set by actions)
        try:
            ctx_role = (self.env.context or {}).get('default_partner_role')
            if ctx_role:
                Tag = self.env['dino.partner.tag']
                tag = Tag.search([('role', '=', ctx_role)], limit=1)
                if not tag:
                    # create a minimal tag if missing
                    tag = Tag.create({'name': ctx_role.capitalize(), 'role': ctx_role})
                record.write({'tag_ids': [(4, tag.id)]})
        except Exception:
            logging.getLogger(__name__).exception('Error assigning default tag on create for %s', record.id)
        return record

    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Restrict name search by partner role when `partner_role_filter` is present in context.

        This affects the Many2one autocomplete and ensures only partners with
        a tag of the requested role are returned.
        """
        args = args or []
        ctx = self.env.context or {}
        role = ctx.get('partner_role_filter') or ctx.get('default_partner_role')
        if role:
            args = expression.AND([args, [('tag_ids.role', '=', role)]])
        return super(DinoPartner, self).name_search(name, args, operator, limit)

    def write(self, vals):
        # Determine which records will have changed egrpou
        records_with_changed_okpo = self
        if 'egrpou' in vals:
            # Only records where new egrpou differs from current
            records_with_changed_okpo = self.filtered(lambda r: (r.egrpou or '') != (vals.get('egrpou') or ''))

        res = super(DinoPartner, self).write(vals)

        try:
            if vals.get('egrpou'):
                # Update only affected records
                records_with_changed_okpo.action_update_from_registry()
        except Exception:
            logging.getLogger(__name__).exception('Error updating partner on write')

        return res

    @api.model
    def migrate_partner_type_flags_to_tags(self):
        """Create 'Customer' and 'Vendor' tags and assign them based on legacy booleans.

        This is a helper you can call once from shell:
            env['dino.partner'].migrate_partner_type_flags_to_tags()
        It will not run automatically; run it when ready.
        """
        Tag = self.env['dino.partner.tag']
        partner = self.env['dino.partner']
        customer_tag = Tag.search([('name', '=', 'Customer')], limit=1) or Tag.create({'name': 'Customer', 'role': 'customer'})
        vendor_tag = Tag.search([('name', '=', 'Vendor')], limit=1) or Tag.create({'name': 'Vendor', 'role': 'vendor'})

        # Assign tags for partners with booleans
        cust_partners = partner.search([('partner_is_customer', '=', True)])
        if cust_partners:
            cust_partners.write({'tag_ids': [(4, customer_tag.id)]})
        vend_partners = partner.search([('partner_is_vendor', '=', True)])
        if vend_partners:
            vend_partners.write({'tag_ids': [(4, vendor_tag.id)]})
        return True


class DinoPartnerTag(models.Model):
    _name = 'dino.partner.tag'
    _description = 'Partner Tag'
    name = fields.Char(string='Name', required=True, translate=True)
    description = fields.Char(string='Description', translate=True)
    color = fields.Char(string='Color Hex') # Изменено на Char для хранения шестнадцатеричного значения
    role = fields.Selection([
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('other', 'Other'),
    ], string='Role', default='other', help='Role of this tag for partner filtering')
    partner_ids = fields.Many2many('dino.partner', 'dino_partner_tag_rel', 'tag_id', 'partner_id', string='Partners')
class DinoPartnerContact(models.Model):
    _name = 'dino.partner.contact'
    _description = 'Partner Contact'

    partner_id = fields.Many2one('dino.partner', string='Partner', required=True, ondelete='cascade')
    name = fields.Char(string='Contact Name', required=True, translate=True)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    position = fields.Char(string='Position', translate=True)
# End of file partners/models/dino_partners.py
