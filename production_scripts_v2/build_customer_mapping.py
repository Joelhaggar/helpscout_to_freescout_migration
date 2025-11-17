#!/usr/bin/env python3
"""
Build a permanent customer mapping file by matching Help Scout customers
with FreeScout customers that have already been extracted.

This creates a JSON file that maps:
  Help Scout Customer ID -> FreeScout Customer ID
  Help Scout Customer Email -> FreeScout Customer ID

Usage:
    python build_customer_mapping.py [--output FILE]

    --output FILE: Output file path (default: customer_mapping.json)
"""
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

project_root = Path(__file__).parent


def load_helpscout_customers() -> Dict:
    """
    Load all Help Scout customers from local export batches.

    Returns:
        Dictionary mapping HS Customer ID to customer data
    """
    customers = {}
    export_dir = project_root / 'helpscout_export'
    customers_dir = export_dir / 'customers'

    if not customers_dir.exists():
        print(f"❌ Customers directory not found: {customers_dir}")
        return customers

    batch_files = sorted(customers_dir.glob('customers_batch_*.json'))
    print(f"📂 Found {len(batch_files)} customer batch files")

    for batch_file in batch_files:
        try:
            with open(batch_file) as f:
                batch_data = json.load(f)

            # Handle both list and dict formats
            if isinstance(batch_data, list):
                batch_customers = batch_data
            else:
                batch_customers = batch_data.get('_embedded', {}).get('customers', [])

            for customer in batch_customers:
                hs_id = customer.get('id')
                if hs_id:
                    customers[hs_id] = customer

            print(f"  ✓ {batch_file.name}: {len(batch_customers)} customers")
        except json.JSONDecodeError as e:
            print(f"  ⚠ {batch_file.name}: JSON decode error - {e}")
        except Exception as e:
            print(f"  ⚠ {batch_file.name}: Error - {e}")

    print(f"\n📊 Total Help Scout customers loaded: {len(customers)}")
    return customers


def load_freescout_customers_from_json(json_path: Path) -> List[Dict]:
    """
    Load pre-extracted FreeScout customers from JSON file.

    Args:
        json_path: Path to freescout_customers.json

    Returns:
        List of customer dictionaries with id, first_name, last_name, email fields
    """
    if not json_path.exists():
        print(f"❌ JSON file not found: {json_path}")
        return []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            customers = json.load(f)

        print(f"📊 Loaded {len(customers)} customers from JSON: {json_path.name}")
        return customers

    except Exception as e:
        print(f"❌ Error reading JSON: {e}")
        import traceback
        traceback.print_exc()
        return []


def match_customers(
    hs_customers: Dict,
    fs_customers: List[Dict]
) -> Tuple[Dict[int, int], Dict[str, int], List[Dict]]:
    """
    Match Help Scout customers to FreeScout customers.

    Matching strategy (in order of preference):
    1. Email exact match (case-insensitive)
    2. Full name match (first + last name)
    3. Unmatched

    Returns:
        Tuple of:
        - ID mapping: HS ID -> FS ID
        - Email mapping: HS email -> FS ID
        - Unmatched HS customers
    """
    id_mapping = {}
    email_mapping = {}
    unmatched = []

    print(f"\n🔗 Matching {len(hs_customers)} HS customers to {len(fs_customers)} FS customers...")

    # Build FS email index and name index
    fs_email_index = {}
    fs_name_index = defaultdict(list)

    for fs_customer in fs_customers:
        fs_id = fs_customer.get('id')
        fs_email = fs_customer.get('email', '').lower().strip()
        fs_first = fs_customer.get('first_name', '').strip()
        fs_last = fs_customer.get('last_name', '').strip()

        if fs_email:
            fs_email_index[fs_email] = fs_id

        if fs_first or fs_last:
            full_name = f"{fs_first} {fs_last}".strip()
            fs_name_index[full_name].append(fs_id)

    matched_count = 0
    email_matched = 0
    name_matched = 0

    for hs_id, hs_customer in hs_customers.items():
        hs_email = hs_customer.get('email', '').lower().strip()
        hs_first = hs_customer.get('firstName', hs_customer.get('first', '')).strip()
        hs_last = hs_customer.get('lastName', hs_customer.get('last', '')).strip()
        hs_full_name = f"{hs_first} {hs_last}".strip()

        fs_id = None
        match_type = None

        # Try email match first
        if hs_email and hs_email in fs_email_index:
            fs_id = fs_email_index[hs_email]
            match_type = "email"
            email_matched += 1

        # Try name match
        elif hs_full_name and hs_full_name in fs_name_index:
            candidates = fs_name_index[hs_full_name]
            if len(candidates) == 1:
                fs_id = candidates[0]
                match_type = "name"
                name_matched += 1

        if fs_id:
            id_mapping[hs_id] = fs_id
            if hs_email:
                email_mapping[hs_email] = fs_id
            matched_count += 1
        else:
            unmatched.append({
                'hs_id': hs_id,
                'email': hs_email,
                'first_name': hs_first,
                'last_name': hs_last
            })

    print(f"  ✓ Email matches: {email_matched}")
    print(f"  ✓ Name matches: {name_matched}")
    print(f"  ⚠ Unmatched: {len(unmatched)}")
    if len(hs_customers) > 0:
        match_pct = 100 * matched_count // len(hs_customers)
        print(f"\n📈 Matched {matched_count}/{len(hs_customers)} customers ({match_pct}%)")

    return id_mapping, email_mapping, unmatched


def save_mapping_file(
    id_mapping: Dict[int, int],
    email_mapping: Dict[str, int],
    unmatched: List[Dict],
    output_path: Path
):
    """
    Save customer mapping to JSON file.

    Args:
        id_mapping: HS ID -> FS ID mapping
        email_mapping: HS email -> FS ID mapping
        unmatched: List of unmatched HS customers
        output_path: Path to output file
    """
    # Convert integer keys to strings for JSON
    id_mapping_str = {str(k): v for k, v in id_mapping.items()}

    mapping_data = {
        'generated_at': str(__import__('datetime').datetime.utcnow().isoformat()),
        'statistics': {
            'total_helpscout_customers': len(id_mapping) + len(unmatched),
            'matched_customers': len(id_mapping),
            'unmatched_customers': len(unmatched),
            'match_percentage': round(100 * len(id_mapping) / (len(id_mapping) + len(unmatched)), 1) if (len(id_mapping) + len(unmatched)) > 0 else 0
        },
        'by_id': id_mapping_str,
        'by_email': email_mapping,
        'unmatched': unmatched
    }

    with open(output_path, 'w') as f:
        json.dump(mapping_data, f, indent=2, sort_keys=True)

    print(f"\n💾 Mapping saved to {output_path}")
    print(f"   File size: {output_path.stat().st_size:,} bytes")
    print(f"\n📊 Statistics:")
    print(f"   Total customers: {mapping_data['statistics']['total_helpscout_customers']}")
    print(f"   Matched: {mapping_data['statistics']['matched_customers']}")
    print(f"   Unmatched: {mapping_data['statistics']['unmatched_customers']}")
    print(f"   Match rate: {mapping_data['statistics']['match_percentage']}%")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Build permanent customer mapping file from pre-extracted FreeScout customers'
    )
    parser.add_argument(
        '--output',
        default='customer_mapping.json',
        help='Output file path (default: customer_mapping.json)'
    )

    args = parser.parse_args()
    output_path = Path(args.output)

    print("="*70)
    print("BUILDING PERMANENT CUSTOMER MAPPING")
    print("="*70)

    try:
        # Load Help Scout customers from local export
        hs_customers = load_helpscout_customers()
        if not hs_customers:
            print("❌ No Help Scout customers found in local export")
            return False

        # Load FreeScout customers from pre-extracted JSON
        fs_json_path = project_root / 'freescout_customers.json'
        fs_customers = load_freescout_customers_from_json(fs_json_path)
        if not fs_customers:
            print("❌ No FreeScout customers found in JSON")
            print(f"   Expected file: {fs_json_path}")
            return False

        # Match customers
        id_mapping, email_mapping, unmatched = match_customers(
            hs_customers,
            fs_customers
        )

        # Save mapping file
        save_mapping_file(id_mapping, email_mapping, unmatched, output_path)

        print("\n✓ Customer mapping complete!")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
