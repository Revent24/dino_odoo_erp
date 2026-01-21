# -*- file: projects/models/dino_project_category.py -*-

from odoo import fields, models, _, api

class DinoProjectCategory(models.Model):
    _name = 'dino.project.category'
    _description = _('Project Category')
    _rec_name = 'name'

    name = fields.Char(string=_('Name'), required=True, translate=True)
    code = fields.Char(string=_('Code'), required=True, unique=True)
    
    # Параметры для категории
    storage_location = fields.Char(string=_('Место хранения документов'), required=False, translate=True, tracking=True)
    
    # Флаг для системных записей
    is_system = fields.Boolean(string=_('System Record'), default=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Запретить создание новых записей, если уже есть две системные
        for vals in vals_list:
            system_count = self.search_count([('is_system', '=', True)])
            if system_count >= 2 and not vals.get('is_system', False):
                raise models.ValidationError(_('Нельзя создавать больше двух категорий проектов.'))
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_system(self):
        # Запретить удаление системных записей
        for rec in self:
            if rec.is_system:
                raise models.ValidationError(_('Нельзя удалять системные категории проектов.'))

    def unlink(self):
        self._unlink_except_system()
        return super().unlink()

    @api.model
    def init(self):
        """Создать предустановленные записи при инициализации модуля."""
        super().init()
        # Данные загружаются из XML, init() не нужен

# -*- End of projects/models/dino_project_category.py -*-   