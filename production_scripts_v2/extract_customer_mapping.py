#!/usr/bin/env python3
"""
Extract customer mapping from FreeScout CSV export.
Create a simple JSON mapping of HS ID -> FS ID based on CSV data.
"""
import csv
import json
from pathlib import Path

# Read the UTF-8 converted CSV
csv_file = Path('/Users/joel/DevProjects/HelpScouttoFreeScoutSync/config/customers_2025-11-16_utf8.csv')

customers = []

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if not row:
            continue

        # Get the ID from the first column (which has BOM+quotes in the key)
        customer_id = None
        first_name = ''
        last_name = ''
        email = ''

        for key, value in row.items():
            clean_key = key.replace('\ufeff', '').strip().strip('"').lower() if key else ''

            if 'id' in clean_key and not customer_id:
                try:
                    customer_id = int(value.strip())
                except:
                    pass
            elif 'first' in clean_key:
                first_name = value.strip() if value else ''
            elif 'last' in clean_key:
                last_name = value.strip() if value else ''
            elif 'email' in clean_key:
                email = value.strip().lower() if value else ''

        if customer_id:
            customers.append({
                'id': customer_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email
            })

print(f"Extracted {len(customers)} customers from CSV")
if customers:
    print(f"Sample: {customers[0]}")

# Save as JSON
output_file = Path('/Users/joel/DevProjects/HelpScouttoFreeScoutSync/freescout_customers.json')
with open(output_file, 'w') as f:
    json.dump(customers, f, indent=2)

print(f"Saved to {output_file}")
