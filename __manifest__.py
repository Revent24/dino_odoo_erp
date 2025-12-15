{
    'name': 'Dino ERP: Динамическое управление производством',
    'version': '1.0',
    'summary': 'Минимальный модуль с одной моделью и меню',
    'description': 'Минимальный Odoo модуль: одна модель `dino.minimal`, одно поле `name` и пункт меню.',
    'author': 'Revent24',
    'category': 'Tools',
    'depends': ['base', 'mail', 'web'] ,  # minimized dependencies: vendor dino_auto_translate and internal UoM/product replacements
    'data': [
        'finance/views/bank_views.xml',
        'finance/views/dino_bank_transaction_views.xml',
        'finance/views/dino_currency_rate_views.xml',
        'finance/views/dino_cashbook_views.xml',
        'core/views/minimal_views.xml',
        'projects/views/dino_project_views.xml',

        # Core security and shared data
        'core/security/ir.model.access.csv',
        'core/data/ir_sequence_data.xml',

        # Stock section views
        'stock/views/dino_component_views.xml',
        'stock/views/dino_stock_config_views.xml',
        'stock/views/dino_nomenclature_views.xml',
        'stock/views/dino_nomenclature_quick_create.xml',
        'stock/views/dino_component_category_views.xml',
        'stock/data/dino_uom_data.xml',
        'stock/security/ir.model.access.csv',

        'partners/views/dino_partners_actions.xml',
        'partners/views/dino_partners_views.xml',

        'finance/data/ir_cron_data.xml',
        'core/views/menu.xml',
        
    ],
    # assets removed: category sidebar feature was rolled back
    'application': True,
    'installable': True,
    'images': ['core/menu_icons/crm.png'],
}
