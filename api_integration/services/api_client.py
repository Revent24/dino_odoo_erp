#
#  -*- File: api_integration/services/api_client.py -*-
#
# -*- coding: utf-8 -*-
import requests
import json
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_logger = logging.getLogger(__name__)


class ApiClient:
    """Universal API client for different services"""

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self):
        """Setup session with authentication and retry strategy"""
        # Authentication
        if self.endpoint.auth_type == 'token':
            self.session.headers['X-Token'] = self.endpoint.auth_token
        elif self.endpoint.auth_type == 'api_key':
            self.session.headers['X-API-Key'] = self.endpoint.auth_api_key
        elif self.endpoint.auth_type == 'basic':
            self.session.auth = (self.endpoint.auth_username, self.endpoint.auth_password)

        # Common headers
        self.session.headers.update({
            'User-Agent': 'DinoERP Integration',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        # Retry strategy
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.mount('http://', HTTPAdapter(max_retries=retries))

    def execute_request(self, method='GET', url=None, params=None, data=None, timeout=30):
        """Execute HTTP request"""
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=timeout
            )

            # Handle response
            if response.status_code == 200:
                try:
                    return {
                        'status': 'success',
                        'data': response.json(),
                        'raw_response': response.text
                    }
                except ValueError:
                    return {
                        'status': 'success',
                        'data': response.text,
                        'raw_response': response.text
                    }
            else:
                return {
                    'status': 'error',
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'status_code': response.status_code
                }

        except requests.RequestException as e:
            _logger.error(f"Request failed for endpoint {self.endpoint.name}: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def get_paginated_data(self, base_url, params_func, max_pages=50, delay=1):
        """Handle pagination for APIs that support it"""
        all_data = []
        page = 0

        while page < max_pages:
            # Get params for current page
            params = params_func(page)

            # Execute request
            result = self.execute_request(url=base_url, params=params)

            if result['status'] == 'error':
                break

            data = result.get('data', [])
            if not data:
                break

            all_data.extend(data)
            page += 1

            # Check if we have more pages (API-specific logic)
            if not self._has_more_pages(data, page):
                break

            # Delay between requests
            import time
            time.sleep(delay)

        return {
            'status': 'success',
            'data': all_data,
            'pages_processed': page
        }

    def _has_more_pages(self, data, current_page):
        """Check if API has more pages (override in subclasses)"""
        # Default implementation - assume no pagination
        return False# End of file api_integration/services/api_client.py
