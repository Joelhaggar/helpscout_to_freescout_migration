#!/usr/bin/env python3
"""
Add Help Scout ID custom field to all existing migrated conversations.

This script updates all conversations that were migrated before the custom field
was added to include the Help Scout conversation ID in the "Helpscout" custom field.
"""
import json
from api.freescout_client import FreeScoutClient
from config.config import Config


def main():
    # Load migration progress to get the mapping
    print('Loading migration progress...')
    with open('migration_progress.json', 'r') as f:
        progress = json.load(f)

    conversation_mapping = progress.get('conversation_mapping', {})
    print(f'Found {len(conversation_mapping)} Help Scout → FreeScout mappings')
    print()

    # Initialize FreeScout client
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    print('=' * 70)
    print('ADD HELP SCOUT ID CUSTOM FIELD TO ALL CONVERSATIONS')
    print('=' * 70)
    print()
    print('This will set the "Helpscout" custom field (ID: 1) for each conversation.')
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
        'skipped': 0,
        'errors': 0
    }

    # Update each conversation
    count = 0
    for hs_id, fs_id in conversation_mapping.items():
        count += 1

        if count % 100 == 0:
            print(f'Progress: {count}/{len(conversation_mapping)} processed...')
            print(f'  Updated: {stats["updated"]}, Skipped: {stats["skipped"]}, Errors: {stats["errors"]}')

        try:
            # Update custom field
            fs_client.update_custom_fields(int(fs_id), [
                {'id': 1, 'value': str(hs_id)}
            ])
            stats['updated'] += 1

        except Exception as e:
            error_str = str(e)
            # Skip if conversation doesn't exist (404)
            if '404' in error_str:
                stats['skipped'] += 1
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
    print(f'Skipped (not found): {stats["skipped"]}')
    print(f'Errors: {stats["errors"]}')
    print()

    if stats["errors"] > 10:
        print(f'Note: Only first 10 errors were displayed. Total errors: {stats["errors"]}')
        print()

    print('✓ Custom field update complete!')
    print()
    print('You can now search for conversations in FreeScout by Help Scout ID.')
    print()

    return 0


if __name__ == '__main__':
    exit(main())
