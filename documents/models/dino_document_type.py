# -*- coding: utf-8 -*-
from odoo import models, fields, api


class DinoDocumentType(models.Model):
    """
    Справочник типов документов
    """
    _name = 'dino.document.type'
    _inherit = ['mixin.find.or.create']
    _description = 'Document Type'
    _order = 'sequence, name'

    name = fields.Char('Document Type', required=True, translate=True)
    code = fields.Char('Type ID', required=True, help='Unique identifier for document type')
    description = fields.Text('Description', translate=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Статистика
    document_count = fields.Integer('Documents', compute='_compute_document_count')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Type ID must be unique!'),
    ]
    
    def _compute_document_count(self):
        """Подсчет количества документов этого типа"""
        for record in self:
            record.document_count = self.env['dino.operation.document'].search_count([
                ('document_type_id', '=', record.id)
            ])
    
    def action_view_documents(self):
        """Открыть документы этого типа"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Documents: {self.name}',
            'res_model': 'dino.operation.document',
            'view_mode': 'list,form',
            'domain': [('document_type_id', '=', self.id)],
            'context': {'default_document_type_id': self.id}
        }
