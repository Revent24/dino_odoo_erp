#!/usr/bin/env python3
"""
Simple XML-RPC script to batch-update `dino.vendor` records by `egrpou`.
Run it on a machine that can reach your Odoo server.

Examples:
  python3 scripts/update_partners.py --host localhost --port 8069 --db mydb --user admin --password admin --limit 100 --sleep 0.5
  python3 scripts/update_partners.py --host localhost --port 8069 --db mydb --user admin --password admin --only-empty --sleep 0.2

The script searches for vendors and calls `action_update_from_registry` on each record.
"""

import sys
import time
import argparse
from xmlrpc import client

DEFAULT_PORT = 8070


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--host', required=True, help='Odoo host')
    p.add_argument('--port', type=int, default=DEFAULT_PORT, help='Odoo port')
    p.add_argument('--scheme', choices=['http', 'https'], default='http', help='URL scheme')
    p.add_argument('--db', required=True, help='Database name')
    p.add_argument('--user', required=True, help='Odoo login')
    p.add_argument('--password', required=True, help='Odoo password')
    p.add_argument('--limit', type=int, default=0, help='Limit number of records to update (0 = all)')
    p.add_argument('--offset', type=int, default=0, help='Offset for search')
    p.add_argument('--only-empty', action='store_true', help='Only update records with empty egrpou')
    p.add_argument('--sleep', type=float, default=0.5, help='Seconds to sleep between updates')
    return p.parse_args()


def main():
    args = parse_args()
    url = '%s://%s:%s' % (args.scheme, args.host, args.port)
    common = client.ServerProxy('{}/xmlrpc/2/common'.format(url))
    uid = common.authenticate(args.db, args.user, args.password, {})
    if not uid:
        print('Authentication failed')
        sys.exit(1)

    models = client.ServerProxy('{}/xmlrpc/2/object'.format(url))

    domain = []
    if args.only_empty:
        domain = [['|', ('egrpou', '=', False), ('egrpou', '=', '')]]

    search_kwargs = {}
    if args.limit and args.limit > 0:
        search_kwargs['limit'] = args.limit
    if args.offset and args.offset > 0:
        search_kwargs['offset'] = args.offset

    print('Searching vendors...')
    vendor_ids = models.execute_kw(args.db, uid, args.password,
                                   'dino.vendor', 'search', [domain], search_kwargs)
    print('Found %s vendors' % len(vendor_ids))

    for idx, vid in enumerate(vendor_ids, start=1):
        print('[%d/%d] Updating vendor id=%s' % (idx, len(vendor_ids), vid))
        try:
            # call the method on single record
            models.execute_kw(args.db, uid, args.password,
                              'dino.vendor', 'action_update_from_registry', [[vid]])
        except Exception as ex:
            print('Error updating %s: %s' % (vid, ex))
        time.sleep(args.sleep)

    print('Done')


if __name__ == '__main__':
    main()
