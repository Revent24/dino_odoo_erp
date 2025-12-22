# --- МОДЕЛЬ: Specification Line (dino.operation.document.specification)
# --- ФАЙЛ: models/dino_operation_document_specification.py

from odoo import fields, models, api


class DinoOperationDocumentSpecification(models.Model):
    _name = 'dino.operation.document.specification'
    _description = 'Specification Line'
    _inherit = ['mixin.auto.translate']
    _order = 'sequence, id'

    # === ОСНОВНЫЕ ПОЛЯ ===
    document_id = fields.Many2one(
        'dino.operation.document',
        string='Document',
        required=True,
        ondelete='cascade'
    )
    line_number = fields.Integer(
        string='№',
        compute='_compute_line_number',
        store=True,
        readonly=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    name = fields.Char(
        string='Description',
        required=True,
        translate=True
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit',
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
    )

    # === ДЕНЕЖНЫЕ ПОЛЯ ===
    price_untaxed = fields.Monetary(
        string='Unit Price',
        required=True,
        currency_field='currency_id'
    )
    amount_untaxed = fields.Monetary(
        string='Subtotal',
        compute='_compute_amount_untaxed',
        store=True,
        currency_field='currency_id'
    )
    vat_rate = fields.Float(
        string='VAT Rate (%)',
        related='document_id.vat_rate',
        store=True,
        readonly=True
    )
    amount_tax = fields.Monetary(
        string='Tax',
        compute='_compute_amount_tax',
        store=True,
        currency_field='currency_id'
    )
    price_tax = fields.Monetary(
        string='Price with Tax',
        store=True,
        default=0.0,
        currency_field='currency_id'
    )
    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amount_total',
        store=True,
        currency_field='currency_id'
    )

    # === СВЯЗАННЫЕ ПОЛЯ ===
    currency_id = fields.Many2one(
        'res.currency',
        related='document_id.currency_id',
        store=True,
        readonly=True
    )
    document_date = fields.Date(
        string='Document Date',
        related='document_id.date',
        store=True,
        readonly=True,
        help='Date from parent document - used for price history and mapping'
    )
    document_number = fields.Char(
        string='Document Number',
        related='document_id.number',
        store=True,
        readonly=True
    )
    partner_id = fields.Many2one(
        'dino.partner',
        related='document_id.partner_id',
        string='Partner',
        store=True,
        readonly=True,
        help='Partner from parent document'
    )
    # product_id = fields.Many2one(
    #     'product.product',
    #     string='Product'
    # )
    supplier_nomenclature_id = fields.Many2one(
        'dino.partner.nomenclature',
        string='Supplier Item Mapping',
        help='Mapping entry: supplier item → internal nomenclature'
    )

    nomenclature_id = fields.Many2one(
        'dino.nomenclature',
        string='Nomenclature',
        help='Link to warehouse nomenclature from stock module'
    )

    # === ВЫЧИСЛЯЕМЫЕ МЕТОДЫ ===

    @api.depends('document_id.specification_ids', 'sequence')
    def _compute_line_number(self):
        """Автонумерация: 1, 2, 3... на основе порядка sequence"""
        for doc in self.mapped('document_id'):
            lines = doc.specification_ids.sorted(key=lambda l: l.sequence)
            number = 1
            for line in lines:
                line.line_number = number
                number += 1

    @api.depends('quantity', 'price_untaxed')
    def _compute_amount_untaxed(self):
        """Вычисляет сумму без НДС: количество × цена за единицу"""
        for line in self:
            line.amount_untaxed = line.quantity * line.price_untaxed

    @api.depends('amount_untaxed', 'vat_rate')
    def _compute_amount_tax(self):
        """Вычисляет сумму НДС: сумма без НДС × ставка НДС / 100"""
        for line in self:
            line.amount_tax = line.amount_untaxed * line.vat_rate / 100

    @api.depends('amount_untaxed', 'amount_tax')
    def _compute_amount_total(self):
        """Вычисляет общую сумму: сумма без НДС + сумма НДС"""
        for line in self:
            line.amount_total = line.amount_untaxed + line.amount_tax

    # === ОБРАБОТЧИКИ ИЗМЕНЕНИЙ (ONCHANGE) ===
    # Эти методы обеспечивают синхронизацию между ценой с НДС и без НДС

    @api.onchange('price_untaxed')
    def _onchange_price_untaxed(self):
        """При изменении цены без НДС пересчитать цену с НДС"""
        if self.price_untaxed and self.vat_rate:
            self.price_tax = self.price_untaxed * (1 + self.vat_rate / 100)
        elif self.price_untaxed:
            self.price_tax = self.price_untaxed

    @api.onchange('price_tax')
    def _onchange_price_tax(self):
        """При изменении цены с НДС пересчитать цену без НДС"""
        if self.price_tax and self.vat_rate:
            self.price_untaxed = self.price_tax / (1 + self.vat_rate / 100)
        elif self.price_tax:
            self.price_untaxed = self.price_tax

    @api.onchange('supplier_nomenclature_id')
    def _onchange_supplier_nomenclature_id(self):
        """Public onchange wrapper to be triggered when mapping selected in the view"""
        self._onchange_supplier_mapping()

    def _update_nomenclature_cost(self):
        """Обновляет стоимость в связанной номенклатуре самой свежей ценой"""
        for rec in self:
            if rec.nomenclature_id:
                # Ищем самую свежую цену для этой номенклатуры из всех документов
                latest_spec = self.search([
                    ('nomenclature_id', '=', rec.nomenclature_id.id),
                    ('price_tax', '>', 0)
                ], limit=1, order='document_date desc, id desc')
                
                if latest_spec and latest_spec.price_tax:
                    # Обновляем cost номенклатуры самой свежей ценой с НДС
                    # ВАЖНО: Этот write запустит _trigger_parents_recalc в Номенклатуре
                    rec.nomenclature_id.sudo().write({
                        'cost': latest_spec.price_tax
                    })

    def write(self, vals):
        """При изменении nomenclature_id или любой цены - обновляем стоимость в номенклатуре"""
        result = super().write(vals)
        
        # Если изменились nomenclature_id, price_tax или price_untaxed
        if 'nomenclature_id' in vals or 'price_tax' in vals or 'price_untaxed' in vals:
            self._update_nomenclature_cost()
        
        return result

    # === ДЕЙСТВИЯ (ACTIONS) ===

    @api.model
    def _find_nomenclature_by_supplier_name(self, supplier_name):
        """Ищет связь номенклатуры по названию поставщика в предыдущих документах"""
        if not supplier_name:
            return False
        
        # Ищем самую свежую связанную запись с таким же названием поставщика
        # Сортируем по document_date desc (дата документа), чтобы взять последний вариант
        existing = self.search([
            ('name', '=', supplier_name),
            ('nomenclature_id', '!=', False)
        ], limit=1, order='document_date desc, id desc')
        
        return existing.nomenclature_id if existing else False

    @api.model_create_multi
    def create(self, vals_list):
        """При создании строки автоматически ищем связь с номенклатурой"""
        for vals in vals_list:
            # Если nomenclature_id не указана, пытаемся найти по названию
            if 'name' in vals and not vals.get('nomenclature_id'):
                nomenclature = self._find_nomenclature_by_supplier_name(vals['name'])
                if nomenclature:
                    vals['nomenclature_id'] = nomenclature.id
        
        records = super().create(vals_list)
        
        # После создания обновляем стоимость в номенклатуре
        records._update_nomenclature_cost()
        
        return records

    def _onchange_supplier_mapping(self):
        """When supplier mapping is chosen, fill name, nomenclature and uom"""
        if self.supplier_nomenclature_id:
            self.name = self.supplier_nomenclature_id.name
            self.nomenclature_id = self.supplier_nomenclature_id.nomenclature_id
            if self.supplier_nomenclature_id.uom_id:
                self.uom_id = self.supplier_nomenclature_id.uom_id

    def action_quick_create_nomenclature(self):
        """Открывает упрощенную форму создания номенклатуры"""
        # Сохраняем текущую строку чтобы получить актуальное значение name
        if not self.id:
            self.sudo().write({})  # Форсируем сохранение если это новая запись
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dino.nomenclature',
            'view_mode': 'form',
            'view_id': self.env.ref('dino_erp.view_nomenclature_quick_create_form', raise_if_not_found=False).id,
            'target': 'new',
            'context': {
                'default_name': self.name,  # Название поставщика из текущей строки
                'supplier_item_name': self.name,
            }
        }

    def action_open_form(self):
        """Открывает форму строки спецификации в модальном окне"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dino.operation.document.specification',
            'res_id': self.id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
        }
# --- END ---