#
#  -*- File: stock/models/dino_bom.py -*-
#
# --- МОДЕЛЬ: СТРОКИ СПЕЦИФИКАЦИИ (BOM)
# --- ФАЙЛ: models/dino_bom.py

from odoo import fields, models, _, api

class DinoBomLine(models.Model):
    _name = 'dino.bom.line'
    _description = 'BOM Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string=_('Sequence'), default=10)

    # Владелец спецификации (Родитель)
    parent_nomenclature_id = fields.Many2one('dino.nomenclature', string=_('Parent Nomenclature'), required=True, ondelete='cascade')
    
    # Фильтр семейства компонентов
    component_id = fields.Many2one('dino.component', string=_('Component Family'), required=True)
    
    # Конкретные исполнения (Дети)
    nomenclature_ids = fields.Many2many(
        'dino.nomenclature', 
        string=_('Executions / Analogs'),
        domain="[('component_id', '=', component_id)]"
    )
    
    qty = fields.Float(string=_('Quantity'), default=1.0, required=True)
    
    currency_id = fields.Many2one(related='parent_nomenclature_id.currency_id', readonly=True)
    
    # Поля стоимости (вычисляемые, stored=True для быстрого чтения, но обновляются рекурсией)
    cost = fields.Monetary(string=_('Unit Cost'), compute='_compute_cost', currency_field='currency_id', store=True)
    total_cost = fields.Monetary(string=_('Subtotal'), compute='_compute_total_cost', currency_field='currency_id', store=True)

    # === ДЕЙСТВИЯ ===
    def action_open_analogs(self):
        self.ensure_one()
        if not self.nomenclature_ids:
            return 
        analog_ids = self.nomenclature_ids.ids
        if len(analog_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'dino.nomenclature',
                'res_id': analog_ids[0],
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'name': _('Selected Analogs'),
                'type': 'ir.actions.act_window',
                'res_model': 'dino.nomenclature',
                'domain': [('id', 'in', analog_ids)],
                'view_mode': 'list,form',
                'target': 'current',
            }

    # === ВЫЧИСЛЕНИЯ ===
    @api.depends('nomenclature_ids.total_cost')
    def _compute_cost(self):
        """
        Предварительный расчет цены для отображения.
        Реальная цена гарантированно обновляется методом action_update_cost_recursive.
        """
        for line in self:
            total_price = sum(nom.total_cost for nom in line.nomenclature_ids)
            count = len(line.nomenclature_ids)
            line.cost = total_price / count if count > 0 else 0.0

    @api.depends('qty', 'cost')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = line.qty * line.cost

    # === TRIGGER LOGIC: АВТОМАТИЧЕСКИЙ ЗАПУСК ПЕРЕСЧЕТА ===

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Если добавили строку в спецификацию - нужно пересчитать владельца этой спецификации (и всё, что выше)
        records._trigger_top_down_recalc()
        return records

    def write(self, vals):
        result = super().write(vals)
        # Если изменилось кол-во, состав аналогов или сам родитель - запускаем пересчет
        trigger_fields = ['qty', 'nomenclature_ids', 'parent_nomenclature_id', 'component_id']
        if any(f in vals for f in trigger_fields):
            self._trigger_top_down_recalc()
        return result

    def unlink(self):
        # При удалении self уже не будет существовать, поэтому запоминаем родителей заранее
        parents = self.mapped('parent_nomenclature_id')
        result = super().unlink()
        
        # Запускаем поиск корней для осиротевших родителей
        if parents:
            # Используем хелпер для поиска корней от списка номенклатур
            top_levels = self.env['dino.bom.line']._find_roots_from_nodes(parents)
            for nom in top_levels:
                nom.action_update_cost_recursive()
        return result

    def _trigger_top_down_recalc(self):
        """
        Находит корневые сборки для текущих строк BOM и запускает их пересчет.
        """
        # 1. Берем непосредственных родителей (в чьих BOM мы находимся)
        direct_parents = self.mapped('parent_nomenclature_id')
        
        if not direct_parents:
            return

        # 2. Ищем их самые верхние сборки (Roots)
        top_levels = self._find_roots_from_nodes(direct_parents)
        
        # 3. Запускаем рекурсивный пересчет на Вершинах
        for nom in top_levels:
            nom.action_update_cost_recursive()

    @api.model
    def _find_roots_from_nodes(self, start_nodes):
        """
        Универсальный метод поиска Верхних сборок (которые никуда не входят), 
        поднимаясь вверх от списка start_nodes.
        """
        roots = set()
        to_check = set(start_nodes.ids)
        visited = set() # Защита от зацикливания

        while to_check:
            current_id = to_check.pop()
            if current_id in visited:
                continue
            visited.add(current_id)

            # Проверяем: используется ли current_id где-то как компонент?
            # Ищем строки BOM, где в списке аналогов (nomenclature_ids) есть current_id
            usage_lines = self.search([('nomenclature_ids', 'in', current_id)])
            
            if not usage_lines:
                # Если нигде не используется — значит это Корень (Top Level)
                roots.add(current_id)
            else:
                # Если используется — добавляем родителей этих строк в очередь проверки
                parents = usage_lines.mapped('parent_nomenclature_id')
                to_check.update(parents.ids)
        
        return self.env['dino.nomenclature'].browse(list(roots))

# --- END ---# End of file stock/models/dino_bom.py
