#!/usr/bin/env python3
"""
Add both Help Scout custom fields to all existing migrated conversations.

Sets:
- Helpscout_ID (field 1): Help Scout conversation ID (e.g., 3119294864)
- Helpscout_No (field 2): Help Scout ticket number (e.g., 11950)

Uses Help Scout cache to get ticket numbers.
"""
import json
import glob
from api.freescout_client import FreeScoutClient
from config.config import Config


def load_helpscout_cache():
    """Load all Help Scout conversations from cache."""
    cache_dir = 'helpscout_cache'
    hs_conversations = {}

    # Load all cache files
    cache_files = sorted(glob.glob(f'{cache_dir}/conversations_page_*.json'))

    for cache_file in cache_files:
        with open(cache_file, 'r') as f:
            page_data = json.load(f)
            conversations = page_data.get('_embedded', {}).get('conversations', [])

            for conv in conversations:
                hs_id = str(conv.get('id'))
                hs_conversations[hs_id] = {
                    'id': hs_id,
                    'number': conv.get('number')
                }

    return hs_conversations


def main():
    # Load migration progress
    print('Loading migration progress...')
    with open('migration_progress.json', 'r') as f:
        progress = json.load(f)

    conversation_mapping = progress.get('conversation_mapping', {})
    print(f'Found {len(conversation_mapping)} Help Scout → FreeScout mappings')
    print()

    # Load Help Scout cache
    print('Loading Help Scout cache...')
    hs_conversations = load_helpscout_cache()
    print(f'Loaded {len(hs_conversations)} conversations from cache')
    print()

    # Initialize FreeScout client
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    print('=' * 70)
    print('ADD BOTH HELP SCOUT CUSTOM FIELDS TO ALL CONVERSATIONS')
    print('=' * 70)
    print()
    print('This will set both custom fields for each conversation:')
    print('  - Helpscout_ID (field 1): Conversation ID')
    print('  - Helpscout_No (field 2): Ticket Number')
    print()
    print(f'Total conversations to update: {len(conversation_mapping)}')
    print()

    # Ask for confirmation
    response = input('Continue? (y/n): ')
    if response.lower() != 'y':
        print('Aborted.')
        return 1

    print()
    print('Updating custom fields...')
    print()

    stats = {
        'updated': 0,
        'skipped_not_found': 0,
        'skipped_no_number': 0,
        'errors': 0
    }

    # Update each conversation
    count = 0
    for hs_id, fs_id in conversation_mapping.items():
        count += 1

        if count % 100 == 0:
            print(f'Progress: {count}/{len(conversation_mapping)} processed...')
            print(f'  Updated: {stats["updated"]}, Skipped: {stats["skipped_not_found"] + stats["skipped_no_number"]}, Errors: {stats["errors"]}')

        try:
            # Get Help Scout number from cache
            hs_data = hs_conversations.get(hs_id)
            if not hs_data:
                stats['skipped_no_number'] += 1
                continue

            hs_number = hs_data.get('number')
            if not hs_number:
                stats['skipped_no_number'] += 1
                continue

            # Update both custom fields
            fs_client.update_custom_fields(int(fs_id), [
                {'id': 1, 'value': str(hs_id)},      # Helpscout_ID
                {'id': 2, 'value': str(hs_number)}   # Helpscout_No
            ])
            stats['updated'] += 1

        except Exception as e:
            error_str = str(e)
            # Skip if conversation doesn't exist (404)
            if '404' in error_str:
                stats['skipped_not_found'] += 1
            else:
                stats['errors'] += 1
                if stats['errors'] <= 10:  # Only print first 10 errors
                    print(f'  [ERROR] HS:{hs_id} → FS:{fs_id} - {error_str[:100]}')

    print()
    print('=' * 70)
    print('SUMMARY')
    print('=' * 70)
    print(f'Total: {len(conversation_mapping)}')
    print(f'Custom fields set: {stats["updated"]}')
    print(f'Skipped (conversation not found): {stats["skipped_not_found"]}')
    print(f'Skipped (no ticket number): {stats["skipped_no_number"]}')
    print(f'Errors: {stats["errors"]}')
    print()

    if stats["errors"] > 10:
        print(f'Note: Only first 10 errors were displayed. Total errors: {stats["errors"]}')
        print()

    print('✓ Custom field update complete!')
    print()
    print('You can now search for conversations in FreeScout by:')
    print('  - Help Scout ID (e.g., 3119294864)')
    print('  - Ticket Number (e.g., 11950)')
    print()

    return 0


if __name__ == '__main__':
    exit(main())
