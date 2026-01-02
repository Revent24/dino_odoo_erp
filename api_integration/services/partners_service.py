# -*- coding: utf-8 -*-
import re
import logging
import requests
from datetime import datetime
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _parse_date_str(d):
    """Parse date string in various formats"""
    if not d:
        return False
    d = d.strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(d, fmt).date()
        except Exception:
            continue
    return False


def fetch_partner_registry_data(egrpou):
    """
    Fetch partner data from Ukrainian public registry by EGRPOU (ОКПО).
    
    API: https://adm.tools/action/gov/api/?egrpou=<egrpou>
    
    Returns dict with partner fields or empty dict on error.
    
    Fields returned:
    - full_name: Повна назва
    - name_short: Коротка назва
    - name: Назва (short або full)
    - address: Адреса
    - director: Директор
    - director_gen: Директор (генеральний)
    - kved: КВЕД (текст)
    - kved_number: КВЕД (номер)
    - inn: ІПН
    - egrpou: ЄДРПОУ
    - date_from: Дата реєстрації
    - date_to: Дата припинення
    - inn_date: Дата реєстрації ІПН
    - last_update: Остання дата оновлення
    """
    okpo = (egrpou or '').strip()
    if not okpo:
        _logger.warning("fetch_partner_registry_data: Empty EGRPOU provided")
        return {}
    
    url = f'https://adm.tools/action/gov/api/?egrpou={okpo}'
    
    try:
        _logger.info(f"Fetching registry data for EGRPOU: {okpo}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as ex:
        _logger.error(f'Failed to fetch registry for {okpo}: {ex}')
        raise UserError(_("Помилка отримання даних з реєстру для ЄДРПОУ %s: %s") % (okpo, ex))

    content = resp.content
    
    # Try to detect encoding from XML declaration
    m = re.search(br'encoding=["\']([^"\']+)["\']', content[:200])
    enc = (m.group(1).decode('ascii') if m else 'windows-1251')
    
    try:
        text = content.decode(enc, errors='replace')
    except Exception:
        try:
            text = content.decode('windows-1251', errors='replace')
        except Exception as ex:
            _logger.error(f'Cannot decode response for {okpo}: {ex}')
            raise UserError(_("Помилка декодування відповіді для ЄДРПОУ %s") % okpo)

    # Parse XML
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(text)
    except Exception as ex:
        _logger.error(f'Failed to parse XML for {okpo}: {ex}')
        raise UserError(_("Помилка парсингу XML для ЄДРПОУ %s") % okpo)

    # Find company element
    company = None
    if root.tag.lower() == 'export':
        company = root.find('company')
    elif root.tag.lower() == 'company':
        company = root

    if company is None:
        _logger.warning(f'No company element in registry response for {okpo}')
        return {}

    def _att(name):
        """Get attribute value or False"""
        v = company.get(name)
        return v if v is not None else False

    vals = {}
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

    # Parse dates
    df = _parse_date_str(_att('date_from'))
    if df:
        vals['date_from'] = df
    dt = _parse_date_str(_att('date_to'))
    if dt:
        vals['date_to'] = dt
    idt = _parse_date_str(_att('inn_date'))
    if idt:
        vals['inn_date'] = idt
    lu = _parse_date_str(_att('last_update'))
    if lu:
        vals['last_update'] = lu

    # Remove false values so write won't override existing fields with False
    result = {k: v for k, v in vals.items() if v}
    
    _logger.info(f"Successfully fetched data for {okpo}: {list(result.keys())}")
    return result


def update_partners_from_registry(env, partner_ids=None):
    """
    Update multiple partners from registry by their EGRPOU.
    
    Args:
        env: Odoo environment
        partner_ids: List of partner IDs to update. If None, updates all partners with EGRPOU.
    
    Returns:
        dict with stats: {'updated': N, 'skipped': N, 'errors': N}
    """
    Partner = env['dino.partner']
    
    if partner_ids:
        partners = Partner.browse(partner_ids)
    else:
        # Get all partners with EGRPOU
        partners = Partner.search([('egrpou', '!=', False)])
    
    stats = {'updated': 0, 'skipped': 0, 'errors': 0}
    
    _logger.info(f"Starting registry update for {len(partners)} partners")
    
    for partner in partners:
        okpo = (partner.egrpou or '').strip()
        if not okpo:
            _logger.debug(f'No EGRPOU for partner {partner.id} ({partner.name}), skip')
            stats['skipped'] += 1
            continue
        
        try:
            vals = fetch_partner_registry_data(okpo)
            if vals:
                partner.write(vals)
                stats['updated'] += 1
                _logger.info(f'Updated partner {partner.id} ({partner.name}) from registry')
            else:
                stats['skipped'] += 1
                _logger.warning(f'No data returned for partner {partner.id} ({okpo})')
        except Exception as ex:
            stats['errors'] += 1
            _logger.exception(f'Failed to update partner {partner.id} ({partner.name}): {ex}')
    
    _logger.info(f"Registry update completed: {stats}")
    return {'stats': stats}
