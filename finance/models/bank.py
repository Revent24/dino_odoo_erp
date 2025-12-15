import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class DinoBankConfig(models.Model):
    _name = 'dino.bank.config'
    _description = _('Bank Integration Settings')

    name = fields.Char(string=_('Name'), required=True)
    api_url = fields.Char(string=_('API URL'))
    api_key = fields.Char(string=_('API Key'))
    active = fields.Boolean(string=_('Active'), default=True)
    last_sync = fields.Datetime(string=_('Last sync'))

    @api.model
    def cron_fetch_rates(self):
        """Cron wrapper to fetch currency rates from configured connections."""
        configs = self.search([('active', '=', True)])
        for cfg in configs:
            try:
                cfg.fetch_rates()
            except Exception:
                _logger.exception('Failed to fetch rates for config %s', cfg.id)

    def fetch_rates(self):
        """Stub: actual implementation should call external bank API and create `dino.currency.rate` records."""
        _logger.info('Fetching rates for %s (%s)', self.id, self.name)
        # Minimal implementation: update last_sync
        self.last_sync = fields.Datetime.now()
        return True
