#
#  -*- File: documents/models/dino_parser_agent.py -*-
#
# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class DinoParserAgent(models.Model):
    """
    Модель для настройки агентов парсинга документов.
    Каждый агент представляет собой алгоритм обработки текста/изображений:
    - regex (локальный парсер)
    - AI API (OpenAI, Claude, Gemini и т.д.)
    """
    _name = 'dino.parser.agent'
    _description = 'Parser Agent'
    _order = 'sequence, name'

    name = fields.Char('Agent Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    is_default = fields.Boolean('Default Agent', default=False, help='Use this agent by default for new documents')
    
    agent_type = fields.Selection([
        ('regex_universal', 'Universal Regex Parser'),
        ('ai_openai_compatible', 'OpenAI-Compatible API (Universal)'),
        ('ai_groq', 'Groq API (Llama Vision)'),
        ('ai_anthropic', 'Anthropic Claude'),
        ('ai_google', 'Google Gemini'),
    ], string='Agent Type', required=True, default='regex_universal')
    
    description = fields.Text('Description', translate=True)
    
    # Fallback agent
    fallback_agent_id = fields.Many2one('dino.parser.agent', string='Fallback Agent', help='Alternative agent if this one fails')
    
    # API настройки (для AI агентов)
    api_key = fields.Char('API Key', help='API key for external AI services')
    api_endpoint = fields.Char('API Endpoint', help='Custom API endpoint (optional)')
    model_name = fields.Char('Model Name', help='Specific model name (e.g., gpt-4o-mini)')
    
    # Дополнительные параметры
    temperature = fields.Float('Temperature', default=0.0, help='AI temperature parameter (0.0-1.0)')
    max_tokens = fields.Integer('Max Tokens', default=4000, help='Maximum tokens for AI response')
    
    # Лимиты API (можно редактировать для контроля использования)
    rate_limit_rpm = fields.Integer('Rate Limit (RPM)', help='Requests per minute limit')
    rate_limit_tpm = fields.Integer('Rate Limit (TPM)', help='Tokens per minute limit')
    rate_limit_rpd = fields.Integer('Rate Limit (RPD)', help='Requests per day limit')
    
    # Статистика использования
    usage_count = fields.Integer('Usage Count', readonly=True, default=0)
    last_used_date = fields.Datetime('Last Used', readonly=True)
    total_tokens_used = fields.Integer('Total Tokens Used', readonly=True, default=0)
    total_cost = fields.Float('Total Cost ($)', readonly=True, default=0.0)
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Agent name must be unique!'),
    ]
    
    def write(self, vals):
        """
        При установке is_default=True, автоматически снять с других.
        Также проверять что default agent всегда активен.
        """
        from odoo.exceptions import UserError
        
        # Если устанавливаем is_default=True, автоматически делаем active=True
        if vals.get('is_default'):
            vals['active'] = True
        
        # Запретить деактивацию агента по умолчанию
        if 'active' in vals and not vals['active']:
            for record in self:
                if record.is_default:
                    raise UserError('Нельзя деактивировать агента по умолчанию. Сначала снимите флаг "Default Agent".')
        
        if vals.get('is_default'):
            # Если устанавливаем is_default=True на нескольких записях,
            # оставляем только первую
            if len(self) > 1:
                # При массовом изменении оставляем только первую запись
                first_record = self[0]
                other_records = self[1:]
                # Снимаем флаг с остальных в текущем наборе
                if other_records:
                    super(DinoParserAgent, other_records).write({'is_default': False})
                # Применяем к первой записи
                result = super(DinoParserAgent, first_record).write(vals)
                # Снять флаг со всех других агентов в БД
                other_defaults = self.search([
                    ('is_default', '=', True),
                    ('id', '!=', first_record.id)
                ])
                if other_defaults:
                    super(DinoParserAgent, other_defaults).write({'is_default': False})
                return result
            else:
                # Для одной записи - обычная логика
                other_defaults = self.search([
                    ('is_default', '=', True),
                    ('id', '!=', self.id)
                ])
                if other_defaults:
                    super(DinoParserAgent, other_defaults).write({'is_default': False})
        return super(DinoParserAgent, self).write(vals)
    
    @api.model
    def create_default_agent(self):
        """Создать агента по умолчанию 'Universal Regex Parser'"""
        existing = self.search([('agent_type', '=', 'regex_universal')], limit=1)
        if not existing:
            self.create({
                'name': 'Universal Regex Parser',
                'agent_type': 'regex_universal',
                'sequence': 1,
                'description': 'Локальный парсер на основе регулярных выражений. Быстрый и бесплатный.',
            })
    
    def increment_usage(self):
        """Увеличить счетчик использования"""
        self.ensure_one()
        self.write({
            'usage_count': self.usage_count + 1,
            'last_used_date': fields.Datetime.now(),
        })
    
    def parse_text(self, text, partner_name=None, _tried_agents=None, image_data=None):
        """
        Парсинг текста документа с использованием этого агента.
        Поддерживает автоматический fallback на другой агент при ошибке.
        
        :param text: Текст документа для парсинга
        :param partner_name: Название партнера (опционально)
        :param _tried_agents: Список уже попробованных агентов (для предотвращения циклов)
        :param image_data: Бинарные данные изображения (для AI парсеров с vision)
        :return: dict с распознанными данными
        """
        self.ensure_one()
        
        # Предотвращение циклических fallback
        if _tried_agents is None:
            _tried_agents = []
        
        if self.id in _tried_agents:
            return {
                'success': False,
                'document': {},
                'supplier': {},
                'lines': [],
                'errors': ['Циклический fallback обнаружен. Прерывание.'],
            }
        
        _tried_agents.append(self.id)
        
        # Импортируем сервисы парсинга
        from ..services.ai_parser_service import AIParserService
        from ..services.regex_parser_service import RegexParserService
        
        # Получить список единиц измерения из БД
        units_list = []
        try:
            units_list = self.env['dino.uom'].search([('active', '=', True)]).mapped('name')
        except Exception as e:
            _logger.warning(f"Failed to load units: {e}")
        
        # Вызываем парсер в зависимости от типа агента
        if self.agent_type in ['ai_openai_compatible', 'ai_google', 'ai_groq']:
            # AI парсеры (OpenRouter, Gemini, Groq)
            result = AIParserService.parse(
                text=text,
                image_data=image_data,
                agent_type=self.agent_type,
                partner_name=partner_name,
                api_key=self.api_key,
                api_base_url=self.api_endpoint,  # Передаємо як api_base_url
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                units_list=units_list,  # ← Передаємо список одиниць
            )
        elif self.agent_type == 'regex_universal':
            # Regex парсер (тільки текст)
            result = RegexParserService.parse(
                text=text,
                partner_name=partner_name
            )
        else:
            result = {
                'success': False,
                'errors': [f'Unknown agent type: {self.agent_type}'],
                'document': {},
                'supplier': {},
                'lines': []
            }
        
        # Обновить статистику использования
        if result.get('success'):
            update_vals = {
                'usage_count': self.usage_count + 1,
                'last_used_date': fields.Datetime.now(),
            }
            
            # Обновить счетчик токенов если есть
            if result.get('tokens_used'):
                update_vals['total_tokens_used'] = self.total_tokens_used + result['tokens_used']
            
            # Обновить стоимость если есть
            if result.get('cost'):
                update_vals['total_cost'] = self.total_cost + result['cost']
            
            self.write(update_vals)
        else:
            # Если ошибка и есть fallback агент - попробовать его
            if self.fallback_agent_id:
                _logger.warning(f"Agent {self.name} failed. Trying fallback: {self.fallback_agent_id.name}")
                
                # Добавить информацию о fallback в результат
                result['fallback_used'] = True
                result['original_agent'] = self.name
                result['fallback_agent'] = self.fallback_agent_id.name
                
                # Вызвать fallback агент (передать image_data дальше)
                return self.fallback_agent_id.parse_text(text, partner_name, _tried_agents=_tried_agents, image_data=image_data)
        
        return result
# End of file documents/models/dino_parser_agent.py
