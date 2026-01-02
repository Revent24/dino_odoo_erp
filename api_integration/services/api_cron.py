# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class DinoApiCron(models.Model):
    _inherit = 'dino.api.endpoint'

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Оркестрация / Точки входа планировщика (cron)
    # ------------------------------------------------------------------
    # Оркестрационная точка входа: запуск fetch для банка; для НБУ делегирует импорт/синхронизацию
    def run_api_endpoint(self):
        """Run the API endpoint"""
        _logger.info('Running API endpoint %s (%s)', self.id, self.name)
        self.run_endpoint(trigger_type='cron')
        return True

    def _advance_next_run(self):
        """Advance next_run by updating last_sync_date, which triggers recompute of next_run."""
        for rec in self:
            rec.last_sync_date = fields.Datetime.now()

    @api.model
    def cron_run_endpoints(self):
        """Cron entrypoint: check per-endpoint `cron_active` and `next_run`, run endpoint when due and advance `next_run` accordingly."""
        # consider only active endpoints which have cron enabled
        endpoints = self.search([('active', '=', True), ('cron_active', '=', True)])
        now = datetime.utcnow()
        for ep in endpoints:
            try:
                # If no next_run is set, skip
                if not ep.next_run:
                    _logger.debug('Skipping endpoint %s: next_run not set', ep.id)
                    continue
                try:
                    nr = fields.Datetime.from_string(ep.next_run)
                except Exception:
                    _logger.warning('Invalid next_run for endpoint %s: %s', ep.id, ep.next_run)
                    continue
                if nr <= now:
                    try:
                        ep.run_api_endpoint()
                        # after successful run, advance next_run
                        ep._advance_next_run()
                    except Exception:
                        _logger.exception('Failed to run endpoint %s', ep.id)
            except Exception:
                _logger.exception('Unexpected error in cron_run_endpoints for endpoint %s', ep.id)
