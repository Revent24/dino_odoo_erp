import re
import logging
from datetime import datetime

import requests

from odoo import models, fields, _, api


class DinoPartner(models.Model):
    _name = 'dino.partner'
    _description = 'Partner'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mixin.auto.translate']

    name = fields.Char(string='Name', required=True, translate=True, tracking=True)
    full_name = fields.Char(string='Full Name', translate=True)
    name_short = fields.Char(string='Short Name', translate=True)
    egrpou = fields.Char(string='EGRPOU', index=True)
    address = fields.Char(string='Address', translate=True)
    director = fields.Char(string='Director', translate=True)
    director_gen = fields.Char(string='Director (Gen)', translate=True)
    kved = fields.Char(string='KVED', translate=True)
    kved_number = fields.Char(string='KVED Number')
    inn = fields.Char(string='INN', index=True)
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    inn_date = fields.Date(string='INN Date')
    last_update = fields.Date(string='Last Update')
    # ownership_type_id removed (ownership model deleted)

    contact_ids = fields.One2many('dino.partner.contact', 'partner_id', string='Contacts')

    # Partner type toggles (legacy booleans kept for compatibility)
    partner_is_customer = fields.Boolean(string='Customer', default=False)
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
            vals = self._fetch_registry_vals(okpo)
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
        # Use helper `_fetch_registry_vals` for each record and write results.
        for rec in self:
            okpo = (rec.egrpou or '').strip()
            if not okpo:
                logging.getLogger(__name__).debug('No EGRPOU for partner %s (%s), skip', rec.id, rec.name)
                continue
            try:
                vals = self._fetch_registry_vals(okpo)
                if vals:
                    rec.write(vals)
            except Exception:
                logging.getLogger(__name__).exception('Failed to update partner %s from registry', rec.id)

    @api.model
    def _fetch_registry_vals(self, okpo):
        """Fetch registry data for a single EGRPOU and return a dict of vals (do not write).

        Returns False or empty dict on failure.
        """
        _logger = logging.getLogger(__name__)
        okpo = (okpo or '').strip()
        if not okpo:
            return {}
        url = 'https://adm.tools/action/gov/api/?egrpou=%s' % okpo
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as ex:
            _logger.exception('Failed to fetch registry for %s: %s', okpo, ex)
            return {}

        content = resp.content
        # Try to detect encoding from XML declaration
        m = re.search(br'encoding=["\']([^"\']+)["\']', content[:200])
        enc = (m.group(1).decode('ascii') if m else 'windows-1251')
        try:
            text = content.decode(enc, errors='replace')
        except Exception:
            try:
                text = content.decode('windows-1251', errors='replace')
            except Exception:
                _logger.exception('Cannot decode response for %s', okpo)
                return {}

        # Parse XML
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)
        except Exception as ex:
            _logger.exception('Failed to parse XML for %s: %s', okpo, ex)
            return {}

        company = None
        if root.tag.lower() == 'export':
            company = root.find('company')
        elif root.tag.lower() == 'company':
            company = root

        if company is None:
            _logger.debug('No company element in registry response for %s', okpo)
            return {}

        vals = {}
        def _att(name):
            v = company.get(name)
            return v if v is not None else False

        vals['full_name'] = _att('name') or False
        vals['name_short'] = _att('name_short') or False
        vals['name'] = vals.get('name_short') or vals.get('full_name') or False
        vals['address'] = _att('address') or False
        vals['director'] = _att('director') or False
        vals['director_gen'] = _att('director_gen') or False
        vals['kved'] = _att('kved') or False
        vals['kved_number'] = _att('kved_number') or False
        vals['inn'] = _att('inn') or False
        vals['egrpou'] = _att('egrpou') or okpo

        # Dates
        df = self._parse_date_str(_att('date_from'))
        if df:
            vals['date_from'] = df
        dt = self._parse_date_str(_att('date_to'))
        if dt:
            vals['date_to'] = dt
        idt = self._parse_date_str(_att('inn_date'))
        if idt:
            vals['inn_date'] = idt
        lu = self._parse_date_str(_att('last_update'))
        if lu:
            vals['last_update'] = lu

        # Remove false values so write won't override existing fields with False
        return {k: v for k, v in vals.items() if v}

    @api.model
    def create(self, vals):
        record = super(DinoPartner, self).create(vals)
        try:
            # If egrpou provided on create, update from registry
            if vals.get('egrpou'):
                record.action_update_from_registry()
        except Exception:
            logging.getLogger(__name__).exception('Error updating partner on create: %s', record.id)
        return record

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
        customer_tag = Tag.search([('name', '=', 'Customer')], limit=1) or Tag.create({'name': 'Customer'})
        vendor_tag = Tag.search([('name', '=', 'Vendor')], limit=1) or Tag.create({'name': 'Vendor'})

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
    partner_ids = fields.Many2many('dino.partner', 'dino_partner_tag_rel', 'tag_id', 'partner_id', string='Partners')
class DinoPartnerContact(models.Model):
    _name = 'dino.partner.contact'
    _description = 'Partner Contact'

    partner_id = fields.Many2one('dino.partner', string='Partner', required=True, ondelete='cascade')
    name = fields.Char(string='Contact Name', required=True, translate=True)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    position = fields.Char(string='Position', translate=True)
