#
#  -*- File: tests/test_find_or_create_mixin.py -*-
#
# -*- coding: utf-8 -*-
import unittest
from odoo.tests.common import TransactionCase


class TestFindOrCreateMixin(TransactionCase):

    def setUp(self):
        super(TestFindOrCreateMixin, self).setUp()
        self.DocumentType = self.env['dino.document.type']

    def test_find_or_create_new_record(self):
        """Test creating a new record when it doesn't exist"""
        search_domain = [('code', '=', 'test_code')]
        create_vals = {
            'name': 'Test Document Type',
            'code': 'test_code',
            'description': 'Test description'
        }

        # Should create new record
        record = self.DocumentType.find_or_create(search_domain, create_vals)

        self.assertEqual(record.name, 'Test Document Type')
        self.assertEqual(record.code, 'test_code')
        self.assertEqual(record.description, 'Test description')

    def test_find_or_create_existing_record(self):
        """Test finding existing record"""
        # Create record first
        existing = self.DocumentType.create({
            'name': 'Existing Type',
            'code': 'existing_code',
            'description': 'Existing description'
        })

        search_domain = [('code', '=', 'existing_code')]
        create_vals = {
            'name': 'New Type',
            'code': 'existing_code',
            'description': 'New description'
        }

        # Should return existing record
        record = self.DocumentType.find_or_create(search_domain, create_vals)

        self.assertEqual(record.id, existing.id)
        self.assertEqual(record.name, 'Existing Type')  # Should not change
        self.assertEqual(record.code, 'existing_code')

    def test_find_or_create_with_update(self):
        """Test updating existing record"""
        # Create record first
        existing = self.DocumentType.create({
            'name': 'Old Name',
            'code': 'update_code',
            'description': 'Old description'
        })

        search_domain = [('code', '=', 'update_code')]
        create_vals = {
            'name': 'New Name',
            'code': 'update_code',
            'description': 'New description'
        }
        update_vals = {
            'description': 'Updated description'
        }

        # Should update existing record
        record = self.DocumentType.find_or_create(search_domain, create_vals, update_vals)

        self.assertEqual(record.id, existing.id)
        self.assertEqual(record.name, 'Old Name')  # Not in update_vals
        self.assertEqual(record.description, 'Updated description')  # Updated# End of file tests/test_find_or_create_mixin.py
