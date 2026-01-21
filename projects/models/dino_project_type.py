#
#  -*- File: projects/models/dino_project_type.py -*-
#
from odoo import fields, models, _, api


class DinoProjectType(models.Model):
    _name = 'dino.project.type'
    _description = _('Project Type')
    _rec_name = 'name'

    name = fields.Char(string=_('Name'), required=True, translate=True)
    code = fields.Char(string=_('Code'), required=True, unique=True)
    project_category_id = fields.Many2one('dino.project.category', string=_('Категория проекта'), required=True, index=True, tracking=True)

    @api.model
    def init(self):
        """Создать предустановленные записи при инициализации модуля."""
        super().init()
        # Получить категории
        income_cat = self.env['dino.project.category'].search([('code', '=', 'income')], limit=1)
        expense_cat = self.env['dino.project.category'].search([('code', '=', 'expense')], limit=1)
        if income_cat:
            # Создать типы для доходов, если не существуют
            if not self.search([('code', '=', 'sales')]):
                self.create({
                    'name': 'Продажи',
                    'code': 'sales',
                    'project_category_id': income_cat.id,
                })
        if expense_cat:
            # Создать типы для расходов
            if not self.search([('code', '=', 'purchases')]):
                self.create({
                    'name': 'Закупки',
                    'code': 'purchases',
                    'project_category_id': expense_cat.id,
                })
            if not self.search([('code', '=', 'overhead')]):
                self.create({
                    'name': 'Расходы',
                    'code': 'overhead',
                    'project_category_id': expense_cat.id,
                })

# -*- End of projects/models/dino_project_type.py -*-