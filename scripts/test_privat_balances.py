#
#  -*- File: scripts/test_privat_balances.py -*-
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования импорта балансов счетов ПриватБанка.

Использование:
    python3 test_privat_balances.py --endpoint-id <ID> [--date DD-MM-YYYY]

Примеры:
    python3 test_privat_balances.py --endpoint-id 1
    python3 test_privat_balances.py --endpoint-id 1 --date 02-01-2026
"""
import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.tools import config
except ImportError:
    print("Error: Unable to import Odoo. Make sure PYTHONPATH is set correctly.")
    sys.exit(1)


def test_privat_balances(endpoint_id, target_date=None):
    """Test PrivatBank balances import"""
    
    # Initialize Odoo
    config.parse_config(['-c', '/etc/odoo/odoo.conf'])
    odoo.cli.server.report_configuration()
    
    dbname = config['db_name']
    if not dbname:
        print("Error: Database name not found in config")
        return False
    
    with odoo.api.Environment.manage():
        registry = odoo.registry(dbname)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            
            # Get endpoint
            endpoint = env['dino.api.endpoint'].browse(endpoint_id)
            if not endpoint.exists():
                print(f"Error: Endpoint with ID {endpoint_id} not found")
                return False
            
            print(f"\n{'='*60}")
            print(f"Testing PrivatBank Balances Import")
            print(f"{'='*60}")
            print(f"Endpoint: {endpoint.name}")
            print(f"Bank: {endpoint.bank_id.name} (MFO: {endpoint.bank_id.mfo})")
            print(f"Operation: {endpoint.operation_type}")
            print(f"Date: {target_date or 'Today'}")
            print(f"{'='*60}\n")
            
            # Validate operation type
            if endpoint.operation_type != 'privat_balances':
                print(f"Error: Endpoint operation type is '{endpoint.operation_type}', expected 'privat_balances'")
                return False
            
            # Check authentication
            if not endpoint.auth_token:
                print("Error: No API token configured for this endpoint")
                return False
            
            print("✓ Endpoint validated")
            print("✓ Authentication configured")
            
            # Import balances
            try:
                from api_integration.services.privat_service import import_accounts
                
                print("\nFetching balances from PrivatBank API...")
                result = import_accounts(endpoint, startDate=target_date)
                
                print("\n" + "="*60)
                print("Import Results")
                print("="*60)
                
                stats = result.get('stats', {})
                print(f"Created:  {stats.get('created', 0)}")
                print(f"Updated:  {stats.get('updated', 0)}")
                print(f"Skipped:  {stats.get('skipped', 0)}")
                
                accounts = result.get('accounts')
                if accounts:
                    print(f"\nTotal accounts: {len(accounts)}")
                    print("\nAccount Details:")
                    print("-" * 60)
                    
                    for acc in accounts:
                        print(f"\n{acc.name}")
                        print(f"  IBAN: {acc.account_number}")
                        print(f"  Currency: {acc.currency_id.name}")
                        print(f"  Date: {acc.balance_end_date}")
                        print(f"  Start Balance: {acc.balance_start:,.2f}")
                        print(f"  Credit Turnover: {acc.turnover_credit:,.2f}")
                        print(f"  Debit Turnover: {acc.turnover_debit:,.2f}")
                        print(f"  End Balance: {acc.balance:,.2f}")
                        if acc.external_id:
                            print(f"  External ID: {acc.external_id}")
                        print(f"  Last Import: {acc.last_import_date}")
                
                print("\n" + "="*60)
                print("✓ Import completed successfully")
                print("="*60 + "\n")
                
                # Commit changes
                cr.commit()
                return True
                
            except Exception as e:
                print(f"\n✗ Error during import: {e}")
                import traceback
                traceback.print_exc()
                return False


def main():
    parser = argparse.ArgumentParser(
        description='Test PrivatBank balances import',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --endpoint-id 1
  %(prog)s --endpoint-id 1 --date 02-01-2026
        """
    )
    
    parser.add_argument('--endpoint-id', type=int, required=True,
                       help='ID of the API endpoint to test')
    parser.add_argument('--date', type=str,
                       help='Target date in DD-MM-YYYY format (default: today)')
    
    args = parser.parse_args()
    
    # Validate date format if provided
    target_date = None
    if args.date:
        try:
            datetime.strptime(args.date, '%d-%m-%Y')
            target_date = args.date
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use DD-MM-YYYY")
            sys.exit(1)
    
    # Run test
    success = test_privat_balances(args.endpoint_id, target_date)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
# End of file scripts/test_privat_balances.py
