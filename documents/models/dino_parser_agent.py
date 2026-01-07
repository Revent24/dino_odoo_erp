# -*- coding: utf-8 -*-
from odoo import models, fields, api


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
    
    agent_type = fields.Selection([
        ('regex_universal', 'Universal Regex Parser'),
        ('ai_openai_compatible', 'OpenAI-Compatible API (Universal)'),
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
    
    # Лимиты API (для информации)
    rate_limit_rpm = fields.Integer('Rate Limit (RPM)', help='Requests per minute limit', readonly=True)
    rate_limit_tpm = fields.Integer('Rate Limit (TPM)', help='Tokens per minute limit', readonly=True)
    rate_limit_rpd = fields.Integer('Rate Limit (RPD)', help='Requests per day limit', readonly=True)
    
    # Статистика использования
    usage_count = fields.Integer('Usage Count', readonly=True, default=0)
    last_used_date = fields.Datetime('Last Used', readonly=True)
    total_tokens_used = fields.Integer('Total Tokens Used', readonly=True, default=0)
    total_cost = fields.Float('Total Cost ($)', readonly=True, default=0.0)
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Agent name must be unique!'),
    ]
    
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
        
        # Вызываем парсер в зависимости от типа агента
        if self.agent_type in ['ai_openai_compatible', 'ai_google']:
            # AI парсеры (OpenRouter, Gemini)
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
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Agent {self.name} failed. Trying fallback: {self.fallback_agent_id.name}")
                
                # Добавить информацию о fallback в результат
                result['fallback_used'] = True
                result['original_agent'] = self.name
                result['fallback_agent'] = self.fallback_agent_id.name
                
                # Вызвать fallback агент (передать image_data дальше)
                return self.fallback_agent_id.parse_text(text, partner_name, _tried_agents=_tried_agents, image_data=image_data)
        
        return result
