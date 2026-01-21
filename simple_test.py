#!/usr/bin/env python3

import psycopg2

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="dino24_dev",
    user="steve"
)

cur = conn.cursor()

# Check nextcloud tables
cur.execute("SELECT tablename FROM pg_tables WHERE tablename LIKE 'nextcloud%'")
tables = cur.fetchall()
print("Nextcloud tables:")
for table in tables:
    print(f"  {table[0]}")

# Check project categories
cur.execute("SELECT id, name FROM dino_project_category LIMIT 5")
categories = cur.fetchall()
print("Project categories:")
for cat in categories:
    print(f"  ID: {cat[0]}, Name: {cat[1]}")

cur.close()
conn.close()