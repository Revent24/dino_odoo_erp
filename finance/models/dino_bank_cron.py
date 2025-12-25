# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class DinoBankCron(models.Model):
    _inherit = 'dino.bank'

    def _advance_cron_nextcall(self):
        """Advance self.cron_nextcall by interval_number/interval_type. If cron_time_of_day_hours is set, preserve that time-of-day."""
        from dateutil.relativedelta import relativedelta
        for rec in self:
            if not rec.cron_nextcall:
                continue
            try:
                cur = fields.Datetime.from_string(rec.cron_nextcall)
            except Exception:
                try:
                    cur = datetime.strptime(rec.cron_nextcall, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    cur = datetime.utcnow()
            interval = int(rec.cron_interval_number) if rec.cron_interval_number else 1
            itype = rec.cron_interval_type or 'days'
            if itype == 'minutes':
                nxt = cur + timedelta(minutes=interval)
            elif itype == 'hours':
                nxt = cur + timedelta(hours=interval)
            elif itype == 'days':
                nxt = cur + timedelta(days=interval)
            elif itype == 'weeks':
                nxt = cur + timedelta(weeks=interval)
            elif itype == 'months':
                nxt = cur + relativedelta(months=interval)
            else:
                nxt = cur + timedelta(days=interval)
            # if time_of_day is set, replace time
            if rec.cron_time_of_day_hours is not None:
                try:
                    val = float(rec.cron_time_of_day_hours)
                    hour = int(val)
                    minute = int(round((val - hour) * 60))
                    if minute >= 60:
                        minute = 0
                        hour = (hour + 1) % 24
                    nxt = nxt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    # ensure next is in future; if not, add one more interval
                    if nxt <= datetime.utcnow():
                        if itype == 'minutes':
                            nxt = nxt + timedelta(minutes=interval)
                        elif itype == 'hours':
                            nxt = nxt + timedelta(hours=interval)
                        elif itype == 'days':
                            nxt = nxt + timedelta(days=interval)
                        elif itype == 'weeks':
                            nxt = nxt + timedelta(weeks=interval)
                        elif itype == 'months':
                            nxt = nxt + relativedelta(months=interval)
                except Exception:
                    pass
            rec.cron_nextcall = fields.Datetime.to_string(nxt)

    @api.model
    def cron_fetch_rates(self):
        """Cron entrypoint: check per-bank `cron_enable` and `cron_nextcall`, run fetch when due and advance `cron_nextcall` accordingly."""
        # consider only active banks which have cron enabled
        banks = self.search([('active', '=', True), ('cron_enable', '=', True)])
        now = datetime.utcnow()
        for b in banks:
            try:
                # If no nextcall is set, skip initialization here — initialization happens in the scheduler logic
                if not b.cron_nextcall:
                    _logger.debug('Skipping bank %s: cron_nextcall not set', b.id)
                    continue
                try:
                    nc = fields.Datetime.from_string(b.cron_nextcall)
                except Exception:
                    try:
                        nc = datetime.strptime(b.cron_nextcall, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        _logger.warning('Invalid cron_nextcall for bank %s: %s', b.id, b.cron_nextcall)
                        continue
                if nc <= now:
                    try:
                        b.fetch_rates()
                        # after successful fetch, advance nextcall
                        b._advance_cron_nextcall()
                    except Exception:
                        _logger.exception('Failed to fetch rates for bank %s', b.id)
            except Exception:
                _logger.exception('Unexpected error in cron_fetch_rates for bank %s', b.id)
