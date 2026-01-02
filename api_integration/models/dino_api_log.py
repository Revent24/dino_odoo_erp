# -*- coding: utf-8 -*-
from odoo import fields, models


class DinoApiLog(models.Model):
    _name = 'dino.api.log'
    _description = 'API Execution Log'
    _order = 'executed_at desc'

    endpoint_id = fields.Many2one('dino.api.endpoint', string='Endpoint', required=True, ondelete='cascade')
    executed_at = fields.Datetime(string='Executed At', default=fields.Datetime.now, required=True)
    trigger_type = fields.Selection([
        ('manual', 'Manual'),
        ('cron', 'Cron'),
        ('test', 'Test'),
        ('progress', 'Progress')
    ], string='Trigger Type', default='manual')
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('info', 'Info')
    ], string='Status', required=True)

    request_data = fields.Text(string='Request Data')
    response_data = fields.Text(string='Response Data')
    error_message = fields.Text(string='Error Message')
    execution_time = fields.Float(string='Execution Time (sec)', help='Time in seconds')