#
#  -*- File: stock/models/dino_nomenclature.py -*-
#
# --- МОДЕЛЬ: НОМЕНКЛАТУРА (ИСПОЛНЕНИЕ / КОНКРЕТНЫЙ ТОВАР)
# --- ФАЙЛ: models/dino_nomenclature.py

from odoo import fields, models, _, api

class DinoNomenclature(models.Model):
    _name = 'dino.nomenclature'
    _description = 'Nomenclature (Variant/Execution)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mixin.auto.translate']
    _rec_name = 'fullname'
    _order = 'fullname'

    # === СВЯЗИ ===
    create_date = fields.Date(string=_('Created on'), required=True, default=fields.Date.context_today)
    
    component_id = fields.Many2one('dino.component', string=_('Component Family'), required=True, ondelete='cascade', tracking=True)
    category_id = fields.Many2one(related='component_id.category_id', string=_('Category'), readonly=True, store=True)
    uom_id = fields.Many2one(related='component_id.uom_id', string=_('Unit of Measure'), readonly=True)
    hide_specification = fields.Boolean(related='category_id.hide_specification', readonly=True)
    origin_type = fields.Selection(related='category_id.origin_type', string=_('Origin Type'), readonly=True, store=True)

    # === НАИМЕНОВАНИЕ ===
    name = fields.Char(string=_('Execution Name'), required=False, tracking=True, translate=True)
    fullname = fields.Char(string=_('Full Name'), compute='_compute_fullname', store=True, index=True)
    code = fields.Char(string=_('Reference'), copy=False, tracking=True)

    # === ЭКОНОМИКА ===
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Cost: Цена закупки (вводится вручную или обновляется из документов закупки)
    cost = fields.Monetary(string=_('Purchase Price'), currency_field='currency_id', default=0.0, tracking=True, readonly=True, help="Price from latest purchase document")
    
    # Material Cost: Сумма материалов по BOM (считается автоматически)
    material_cost = fields.Monetary(string="Material Cost", currency_field='currency_id', default=0.0, readonly=True)
    
    qty_available = fields.Float(string=_('On Hand'), default=0.0, tracking=True)

    # === ВЛОЖЕННЫЕ ТАБЛИЦЫ ===
    parameter_ids = fields.One2many('dino.parameter', 'nomenclature_id', string=_('Parameters'))
    bom_line_ids = fields.One2many('dino.bom.line', 'parent_nomenclature_id', string=_('Bill of Materials'))

    # Total Cost: Полная стоимость (Закупка + Материалы)
    total_cost = fields.Monetary(string=_('Total Cost'), compute='_compute_total_cost', currency_field='currency_id', store=True)

    purpose = fields.Char(string=_('Purpose'), translate=True, help="Short description of the execution")
    description = fields.Html(string=_('Internal Notes'), translate=True)
    
    # === SMART BUTTONS ===
    supplier_line_count = fields.Integer(compute='_compute_supplier_line_count')
    bom_count = fields.Integer(compute='_compute_bom_count')
    
    # Поле поиска для фильтра "Top Level Assemblies"
    used_in_count = fields.Integer(string="Used In Count", compute='_compute_used_in_count', search='_search_used_in_count')

    # --- Smart Buttons Logic ---
    
    @api.depends('bom_line_ids')
    def _compute_bom_count(self):
        for rec in self:
            rec.bom_count = len(rec.bom_line_ids)

    def _compute_used_in_count(self):
        for rec in self:
            lines = self.env['dino.bom.line'].search([('nomenclature_ids', 'in', rec.id)])
            parents = lines.mapped('parent_nomenclature_id')
            rec.used_in_count = len(parents)

    def _search_used_in_count(self, operator, value):
        """Позволяет искать по полю used_in_count (поиск ID, используемых в BOM)."""
        bom_line_model = self.env['dino.bom.line']
        if 'nomenclature_ids' not in bom_line_model._fields:
             return []

        field_obj = bom_line_model._fields['nomenclature_ids']
        m2m_table = field_obj.relation
        m2m_col = field_obj.column2 # Колонка nomenclature_id

        # Находим все ID номенклатур, которые используются в BOM
        query = f"SELECT DISTINCT {m2m_col} FROM {m2m_table}"
        self.env.cr.execute(query)
        used_ids = [row[0] for row in self.env.cr.fetchall()]

        if operator == '=' and value == 0:
            return [('id', 'not in', used_ids)]
        elif operator in ('>', '>=', '!=') and value == 0:
            return [('id', 'in', used_ids)]
        else:
            return [('id', 'in', used_ids)]

    def _compute_supplier_line_count(self):
        for rec in self:
            if 'dino.operation.document.specification' in self.env:
                rec.supplier_line_count = self.env['dino.operation.document.specification'].search_count([
                    ('nomenclature_id', '=', rec.id)
                ])
            else:
                rec.supplier_line_count = 0
    
    def action_view_supplier_prices(self):
        self.ensure_one()
        return {
            'name': _('Price History'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.operation.document.specification',
            'view_mode': 'list',
            'view_id': self.env.ref('dino_erp_operations.view_specification_price_history_tree', raise_if_not_found=False).id,
            'domain': [('nomenclature_id', '=', self.id)],
            'context': {'create': False, 'edit': False},
        }

    def action_view_bom(self):
        self.ensure_one()
        return {
            'name': _('Bill of Materials'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.bom.line',
            'view_mode': 'list,form',
            'domain': [('parent_nomenclature_id', '=', self.id)],
            'context': {'default_parent_nomenclature_id': self.id},
        }

    def action_view_used_in(self):
        self.ensure_one()
        lines = self.env['dino.bom.line'].search([('nomenclature_ids', 'in', self.id)])
        parent_ids = lines.mapped('parent_nomenclature_id').ids
        return {
            'name': _('Used In'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.nomenclature',
            'view_mode': 'list,form',
            'domain': [('id', 'in', parent_ids)],
            'context': {'create': False},
        }

    def action_view_parent(self):
        self.ensure_one()
        return {
            'name': _('Component Family'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.component',
            'res_id': self.component_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_form(self):
        self.ensure_one()
        return {
            'name': self.fullname,
            'type': 'ir.actions.act_window',
            'res_model': 'dino.nomenclature',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # === AUTO NAME LOGIC ===
    @api.depends('component_id.name', 'name')
    def _compute_fullname(self):
        for rec in self:
            if rec.component_id and rec.name:
                rec.fullname = f"{rec.component_id.name} {rec.name}"
            else:
                rec.fullname = rec.name or rec.component_id.name

    @api.depends('name', 'fullname')
    @api.depends_context('show_short_name')
    def _compute_display_name(self):
        for rec in self:
            if self.env.context.get('show_short_name'):
                rec.display_name = rec.name
            else:
                rec.display_name = rec.fullname

    # === COST CALCULATION LOGIC ===

    @api.depends('cost', 'material_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.cost + rec.material_cost

    def write(self, vals):
        """
        Переопределяем write, чтобы ловить изменение цены (cost).
        Если цена меняется (например, из документа поступления), 
        мы должны уведомить всех родителей.
        """
        result = super().write(vals)
        
        # Если изменилась Цена Закупки (cost)
        if 'cost' in vals:
            self._trigger_parents_recalc()
            
        return result

    def _trigger_parents_recalc(self):
        """
        Находит все места, где используется эта номенклатура,
        находит их самые верхние сборки (Roots) и запускает пересчет.
        """
        # 1. Находим строки BOM, где используется текущая номенклатура
        usage_lines = self.env['dino.bom.line'].search([('nomenclature_ids', 'in', self.ids)])
        
        if not usage_lines:
            return

        # 2. Берем родителей этих строк
        parents = usage_lines.mapped('parent_nomenclature_id')

        # 3. Ищем КОРНИ (самые верхние изделия) для этих родителей
        # Используем метод поиска корней из модели BOM
        top_levels = self.env['dino.bom.line']._find_roots_from_nodes(parents)

        # 4. Запускаем рекурсию сверху вниз
        for nom in top_levels:
            nom.action_update_cost_recursive()

    def action_update_cost_recursive(self):
        """
        ГЛАВНЫЙ МЕТОД: Рекурсивно обновляет цены (Сверху -> Вниз -> Вверх).
        """
        for record in self:
            # Базовый случай: если нет BOM (покупной товар), возвращаем его текущую полную стоимость
            if not record.bom_line_ids:
                return record.total_cost

            total_material_cost = 0.0
            
            # Проходим по строкам спецификации
            for line in record.bom_line_ids:
                line_avg_cost = 0.0
                
                # Если в строке выбраны конкретные аналоги/исполнения
                if line.nomenclature_ids:
                    # РЕКУРСИЯ: Сначала обновляем каждого ребенка!
                    costs = [nom.action_update_cost_recursive() for nom in line.nomenclature_ids]
                    line_avg_cost = sum(costs) / len(costs) if costs else 0.0
                
                # Обновляем поля строки
                line.write({
                    'cost': line_avg_cost,
                    'total_cost': line.qty * line_avg_cost
                })
                
                total_material_cost += line.qty * line_avg_cost

            # Обновляем свою стоимость материалов
            record.write({'material_cost': total_material_cost})
            
            # Считаем новый итог
            new_total = record.cost + total_material_cost
            return new_total

    _sql_constraints = [
        ('name_uniq_per_component', 'unique (component_id, name)', 'The execution name must be unique within the component family!'),
        ('code_unique', 'unique (code)', 'The Reference must be unique!'),
    ]

# --- END ---# End of file stock/models/dino_nomenclature.py
