# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ВНИМАНИЕ ДЛЯ РАЗРАБОТЧИКОВ (рус.):
# Этот файл содержит модель `dino.bank` и теперь содержит только:
# - объявление полей модели (attributes / fields)
# - валидации и onchange-методы (thin wrappers для сервисов)
# - UI-обработчики кнопок
#
# Рекомендации по структуре выполнены:
# 1) Оставлены только поля модели и минимальные thin-обёртки для UI.
# 2) Логика планирования/cron вынесена в `dino_bank_cron.py` (_inherit = 'dino.bank').
# 3) HTTP-клиенты и парсинг вынесены в `finance/services/*` (nbu_client, privat_client и т.д.).
# 4) Высокоуровневая бизнес-логика импорта/синхронизации держится в services (nbu_service).
# 5) Перемещены `sync_to_system_rates`, `_fetch_nbu_banks` и `_onchange_mfo` в соответствующие сервисы/клиенты.
#
# TODOs (быстрый план):
# - [x] Перенести _fetch_nbu_banks -> nbu_client.get_banks (выполнено? проверить дупликаты). -> Удалено, дублируется с nbu_client.get_banks
# - [x] Перенести _onchange_mfo http lookup -> nbu_client (оставить thin onchange, делегирующий вызов). -> Выполнено
# - [x] Перенести sync_to_system_rates -> nbu_service (и оставить thin wrapper здесь). -> Выполнено, добавлен sync_to_system_rates в nbu_service
# - [ ] Добавить unit-тесты для nbu_client и nbu_service.
# - [x] Максимально очистить файл модели согласно плану -> Выполнено
#
# Комментарии: пока что некоторые методы уже делегируют в services (import_nbu_rates/import_and_sync_nbu).
# Оставляйте изменения небольшими и проверяйте поведение через обновление модуля и smoke-тесты.
# ---------------------------------------------------------------------------

class DinoBank(models.Model):
    _name = 'dino.bank'
    _description = _('Bank Directory')
    _order = 'name'

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Структура / Поля
    # ------------------------------------------------------------------
    # Основные поля модели
    name = fields.Char(string=_('Name'), required=True, index=True)
    mfo = fields.Char(string=_('MFO'), size=6, index=True)
    edrpou = fields.Char(string=_('EDRPOU'), index=True)

    # Common fields
    active = fields.Boolean(string=_('Active'), default=True)

    # Smart button / indicators
    account_count = fields.Integer(string=_('Accounts'), compute='_compute_account_count')

    @api.depends()
    def _compute_account_count(self):
        for rec in self:
            rec.account_count = self.env['dino.bank.account'].search_count([('bank_id', '=', rec.id)])

    def action_view_accounts(self):
        self.ensure_one()
        return {
            'name': _('Bank Accounts'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.bank.account',
            'view_mode': 'list,form',
            'domain': [('bank_id', '=', self.id)],
            'context': {'default_bank_id': self.id, 'active_test': False},
        }

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Ограничения и обработчики onchange
    # ------------------------------------------------------------------
    # Onchange: при изменении MFO выполняем lookup в справочнике НБУ и заполняем name/edrpou
    @api.onchange('mfo')
    def _onchange_mfo(self):
        """Lookup bank info from NBU by specific MFO (glmfo) on change.

        Thin wrapper delegating to nbu_client.get_bank_info.
        """
        if not self.mfo:
            return
        mfo_str = str(self.mfo).strip()
        if len(mfo_str) != 6:
            return {
                'warning': {
                    'title': _('Invalid MFO'),
                    'message': _('MFO must be 6 characters long.')
                }
            }
        from ...api_integration.services.nbu_client import NBUClient
        client = NBUClient()
        try:
            data = client.get_bank_info(mfo_str)
            if not data:
                return {
                    'warning': {
                        'title': _('Bank not found'),
                        'message': _('No data returned for MFO %s') % mfo_str
                    }
                }
            # Предпочитаем запись с TYP == '0'
            record = next((r for r in data if str(r.get('TYP', '')).strip() == '0' and str(r.get('GLMFO') or r.get('MFO') or '').strip() == mfo_str), None)
            if not record:
                record = next((r for r in data if str(r.get('GLMFO') or r.get('MFO') or '').strip() == mfo_str), data[0] if data else None)
            if record:
                self.name = record.get('N_GOL') or record.get('SHORTNAME') or record.get('FULLNAME') or record.get('NAME_E') or self.name
                self.edrpou = record.get('KOD_EDRPOU') or record.get('kod_edrpou') or self.edrpou
        except Exception as e:
            _logger.warning('NBU glmfo lookup failed for %s: %s', mfo_str, e)
            return {
                'warning': {
                    'title': _('NBU lookup failed'),
                    'message': _('Could not fetch bank data for MFO %s: %s') % (mfo_str, e)
                }
            }

    # ------------------------------------------------------------------
    # РАЗДЕЛ: UI-обработчики (кнопки)
    # ------------------------------------------------------------------
    # All sync operations now handled through API endpoints
    # Old button_sync and button_import_and_sync methods removed