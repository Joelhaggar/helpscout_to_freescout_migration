#!/usr/bin/env python3
"""
Lookup utility to find FreeScout conversations by Help Scout ID.

Usage:
    python lookup_conversation.py <helpscout_id>
    python lookup_conversation.py --fs <freescout_id>
    python lookup_conversation.py --url <helpscout_url>
"""
import sys
import json
import re
from api.freescout_client import FreeScoutClient
from api.helpscout_client import HelpScoutClient
from config.config import Config


def load_mapping():
    """Load Help Scout → FreeScout conversation mapping."""
    with open('migration_progress.json', 'r') as f:
        progress = json.load(f)
    return progress.get('conversation_mapping', {})


def extract_hs_id_from_url(url: str) -> str:
    """Extract Help Scout conversation ID from URL."""
    # Match URLs like: https://secure.helpscout.net/conversation/3119109492
    match = re.search(r'/conversation/(\d+)', url)
    if match:
        return match.group(1)
    return None


def lookup_by_hs_id(hs_id: str, mapping: dict):
    """Lookup FreeScout conversation by Help Scout ID."""
    fs_id = mapping.get(hs_id)

    if not fs_id:
        print(f'❌ Help Scout conversation {hs_id} not found in mapping')
        print(f'   This conversation may not have been migrated.')
        return

    print(f'✓ Found mapping:')
    print(f'  Help Scout ID: {hs_id}')
    print(f'  FreeScout ID:  {fs_id}')
    print()

    # Get FreeScout URL
    fs_url = f'{Config.FREESCOUT_URL}/conversation/{fs_id}'
    hs_url = f'https://secure.helpscout.net/conversation/{hs_id}'

    print(f'Links:')
    print(f'  Help Scout:  {hs_url}')
    print(f'  FreeScout:   {fs_url}')
    print()

    # Try to fetch details from FreeScout
    try:
        fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)
        conv = fs_client.get_conversation(int(fs_id))

        if conv:
            print(f'FreeScout Details:')
            print(f'  Number:  #{conv.get("number")}')
            print(f'  Subject: {conv.get("subject", "")[:60]}')
            print(f'  Status:  {conv.get("status")}')
            print(f'  Threads: {conv.get("threads")}')
    except Exception as e:
        print(f'⚠ Could not fetch FreeScout details: {e}')


def lookup_by_fs_id(fs_id: str, mapping: dict):
    """Lookup Help Scout conversation by FreeScout ID."""
    # Reverse lookup
    reverse_mapping = {v: k for k, v in mapping.items()}
    hs_id = reverse_mapping.get(fs_id)

    if not hs_id:
        print(f'❌ FreeScout conversation {fs_id} not found in mapping')
        print(f'   This conversation may not be a migrated conversation.')
        return

    lookup_by_hs_id(hs_id, mapping)


def main():
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python lookup_conversation.py <helpscout_id>')
        print('  python lookup_conversation.py --fs <freescout_id>')
        print('  python lookup_conversation.py --url <helpscout_url>')
        print()
        print('Examples:')
        print('  python lookup_conversation.py 3119109492')
        print('  python lookup_conversation.py --fs 9913')
        print('  python lookup_conversation.py --url https://secure.helpscout.net/conversation/3119109492')
        return 1

    # Load mapping
    mapping = load_mapping()
    print(f'Loaded {len(mapping)} conversation mappings')
    print()

    # Parse arguments
    if sys.argv[1] == '--fs':
        if len(sys.argv) < 3:
            print('Error: --fs requires a FreeScout ID')
            return 1
        lookup_by_fs_id(sys.argv[2], mapping)

    elif sys.argv[1] == '--url':
        if len(sys.argv) < 3:
            print('Error: --url requires a Help Scout URL')
            return 1
        hs_id = extract_hs_id_from_url(sys.argv[2])
        if not hs_id:
            print('Error: Could not extract Help Scout ID from URL')
            return 1
        lookup_by_hs_id(hs_id, mapping)

    else:
        # Assume it's a Help Scout ID
        hs_id = sys.argv[1]
        lookup_by_hs_id(hs_id, mapping)

    return 0


if __name__ == '__main__':
    exit(main())
