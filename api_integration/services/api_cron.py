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
    
    def _advance_next_run(self):
        """Advance next_run by updating last_sync_date, which triggers recompute of next_run."""
        for rec in self:
            rec.last_sync_date = fields.Datetime.now()

    @api.model
    def cron_run_endpoints(self):
        """Cron entrypoint: check per-endpoint `cron_active` and `next_run`, run endpoint when due and advance `next_run` accordingly."""
        # consider only active endpoints which have cron enabled
        endpoints = self.search([('active', '=', True), ('cron_active', '=', True)])
        now = fields.Datetime.now()
        _logger.info(f'Cron check: found {len(endpoints)} active endpoints with cron enabled')
        
        for ep in endpoints:
            try:
                # If no next_run is set, skip
                if not ep.next_run:
                    _logger.debug(f'Skipping endpoint {ep.name} (ID: {ep.id}): next_run not set')
                    continue
                
                # Compare times
                _logger.debug(f'Endpoint {ep.name}: next_run={ep.next_run}, now={now}')
                if ep.next_run <= now:
                    _logger.info(f'Running scheduled endpoint: {ep.name} (ID: {ep.id})')
                    try:
                        # Mark as running
                        ep.write({'cron_running': True})
                        # Run endpoint with cron trigger
                        ep.run_endpoint(trigger_type='cron')
                        # After successful run, advance next_run
                        ep._advance_next_run()
                        _logger.info(f'Successfully completed endpoint: {ep.name}')
                    except Exception:
                        _logger.exception(f'Failed to run endpoint {ep.name} (ID: {ep.id})')
                else:
                    _logger.debug(f'Endpoint {ep.name} not due yet (next_run: {ep.next_run})')
            except Exception:
                _logger.exception(f'Unexpected error in cron_run_endpoints for endpoint {ep.name} (ID: {ep.id})')
