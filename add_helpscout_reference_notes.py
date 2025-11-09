"""
Add a note to each FreeScout conversation with the Help Scout conversation link.

This makes it easy to cross-reference conversations and troubleshoot issues.
"""
import json
from api.freescout_client import FreeScoutClient
from config.config import Config


def main():
    # Load migration progress to get the mapping
    with open('migration_progress.json', 'r') as f:
        progress = json.load(f)

    conversation_mapping = progress.get('conversation_mapping', {})
    print(f'Found {len(conversation_mapping)} Help Scout → FreeScout mappings')
    print()

    # Initialize FreeScout client
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    stats = {
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }

    print('=' * 70)
    print('ADDING HELP SCOUT REFERENCE NOTES')
    print('=' * 70)
    print()
    print('This will add a system note to each conversation with:')
    print('  - Help Scout Conversation ID')
    print('  - Direct link to Help Scout conversation')
    print()

    # Ask for confirmation
    response = input('Continue? (y/n): ')
    if response.lower() != 'y':
        print('Aborted.')
        return 1

    print()
    print('Adding notes...')
    print()

    # Update each conversation
    count = 0
    for hs_id, fs_id in conversation_mapping.items():
        count += 1

        if count % 100 == 0:
            print(f'Progress: {count}/{len(conversation_mapping)} processed...')
            print(f'  Updated: {stats["updated"]}, Skipped: {stats["skipped"]}, Errors: {stats["errors"]}')

        try:
            # Create note with Help Scout reference
            hs_url = f'https://secure.helpscout.net/conversation/{hs_id}'
            note_text = f'**Migrated from Help Scout**\n\nHelp Scout ID: {hs_id}\nOriginal conversation: {hs_url}'

            note_data = {
                'type': 'note',
                'text': note_text,
                'user': 8,  # System user
                'imported': True  # Don't send notifications
            }

            fs_client.add_thread(int(fs_id), note_data, imported=True)
            stats['updated'] += 1

        except Exception as e:
            error_str = str(e)
            # Skip if conversation doesn't exist (404)
            if '404' in error_str:
                stats['skipped'] += 1
            else:
                stats['errors'] += 1
                print(f'  [ERROR] HS:{hs_id} → FS:{fs_id} - {error_str[:100]}')

    print()
    print('=' * 70)
    print('SUMMARY')
    print('=' * 70)
    print(f'Total: {len(conversation_mapping)}')
    print(f'Notes added: {stats["updated"]}')
    print(f'Skipped (not found): {stats["skipped"]}')
    print(f'Errors: {stats["errors"]}')
    print()

    return 0


if __name__ == '__main__':
    exit(main())
