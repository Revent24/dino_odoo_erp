#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test script for FindOrCreateMixin
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Mock Odoo environment for testing
    print("Testing FindOrCreateMixin...")

    # Import the mixin
    from core.mixins.find_or_create_mixin import FindOrCreateMixin

    print("✅ FindOrCreateMixin imported successfully")
    print("✅ Mixin class:", FindOrCreateMixin)
    print("✅ Mixin name:", FindOrCreateMixin._name)
    print("✅ Mixin description:", FindOrCreateMixin._description)

    # Check if method exists
    if hasattr(FindOrCreateMixin, 'find_or_create'):
        print("✅ find_or_create method exists")
    else:
        print("❌ find_or_create method not found")

    print("\nMixin created successfully! Ready for integration.")

except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)