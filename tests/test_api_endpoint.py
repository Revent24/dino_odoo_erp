#
#  -*- File: tests/test_api_endpoint.py -*-
#
# -*- coding: utf-8 -*-
import json
from dino_erp.api_integration.models.dino_api_endpoint import DinoApiEndpoint
from dino_erp.api_integration.services.handlers import NbuRatesHandler


def test_endpoint_creation(env):
    """Test basic endpoint creation"""
    endpoint = env['dino.api.endpoint'].create({
        'name': 'Test NBU Rates',
        'api_type': 'nbu',
        'operation_type': 'nbu_rates',
        'config_params': json.dumps({'test': True})
    })

    assert endpoint.name == 'Test NBU Rates'
    assert endpoint.api_type == 'nbu'
    assert endpoint.operation_type == 'nbu_rates'


def test_handler_initialization(env):
    """Test handler can be initialized"""
    endpoint = env['dino.api.endpoint'].create({
        'name': 'Test Handler',
        'api_type': 'nbu',
        'operation_type': 'nbu_rates'
    })

    handler = NbuRatesHandler(endpoint)
    assert handler.endpoint == endpoint
    assert handler.env == env# End of file tests/test_api_endpoint.py
