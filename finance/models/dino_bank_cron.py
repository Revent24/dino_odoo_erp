# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class DinoBankCron(models.Model):
    _inherit = 'dino.bank'

    # ------------------------------------------------------------------
    # РАЗДЕЛ: Оркестрация / Точки входа планировщика (cron)
    # ------------------------------------------------------------------
    # Оркестрационная точка входа: запуск fetch для банка; для НБУ делегирует импорт/синхронизацию
    def fetch_rates(self):
        """Stub: implement per-bank fetch logic (kept for compatibility).
        For NBU (mfo=300001) this will import exchange rates if called explicitly."""
        _logger.info('Fetching rates for bank %s (%s)', self.id, self.name)
        self.last_sync_date = fields.Datetime.now()
        # If this is NBU, delegate to import_nbu_rates incrementally for missing dates
        for rec in self:
            if rec.mfo == '300001':
                rate_model = self.env['dino.currency.rate']
                last = rate_model.search([('source', '=', 'nbu')], order='date desc', limit=1)
                start_date_import = rec.start_sync_date
                if last and last.date:
                    start_date_import = max(start_date_import, last.date + timedelta(days=1))
                # убедиться, что start_date задана и <= сегодняшней даты
                if start_date_import:
                    try:
                        rec.import_and_sync_nbu(start_date=start_date_import, to_date=fields.Date.context_today(rec), overwrite=rec.cron_overwrite_existing_rates)
                    except Exception as e:
                        _logger.error('Error during scheduled NBU import+sync for bank %s: %s', rec.id, e)
                else:
                    _logger.warning('Skipping scheduled NBU import for bank %s: start date not configured.', rec.id)
        return True

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
