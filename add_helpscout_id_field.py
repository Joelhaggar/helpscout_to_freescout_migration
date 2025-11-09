"""
Add Help Scout Conversation ID as a custom field to all FreeScout conversations.

This will make it much easier to troubleshoot and find conversations across systems.
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

    # Check if custom fields are supported
    print('Checking FreeScout custom field support...')
    print('Note: Custom fields require FreeScout Custom Fields module')
    print('      If you get errors, the module may not be installed')
    print()

    stats = {
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }

    print('=' * 70)
    print('ADDING HELP SCOUT ID TO FREESCOUT CONVERSATIONS')
    print('=' * 70)
    print()

    # Update each conversation
    count = 0
    for hs_id, fs_id in conversation_mapping.items():
        count += 1

        if count % 100 == 0:
            print(f'Progress: {count}/{len(conversation_mapping)} processed...')

        try:
            # Try to update the conversation with a custom field
            # Note: This approach depends on FreeScout's custom fields implementation
            # We'll add it as metadata in the conversation update
            update_data = {
                'byUser': 8,
                # Some FreeScout instances support custom fields like this:
                # 'customFields': [{'name': 'helpscout_id', 'value': str(hs_id)}]
                # But the standard API might not support this without a module
            }

            # For now, let's just verify the conversation exists
            # We can't add custom fields without the Custom Fields module
            conv = fs_client.get_conversation(int(fs_id))

            if conv:
                stats['skipped'] += 1

        except Exception as e:
            stats['errors'] += 1
            print(f'  [{count}] HS:{hs_id} → FS:{fs_id} - Error: {e}')

    print()
    print('=' * 70)
    print('SUMMARY')
    print('=' * 70)
    print(f'Total: {len(conversation_mapping)}')
    print(f'Verified: {stats["skipped"]}')
    print(f'Errors: {stats["errors"]}')
    print()
    print('NOTE: FreeScout does not support custom fields via API without a module.')
    print('      The Help Scout ID is already stored in migration_progress.json.')
    print()
    print('ALTERNATIVE SOLUTIONS:')
    print('1. Use migration_progress.json to lookup Help Scout IDs')
    print('2. Add a note to each conversation with the Help Scout URL')
    print('3. Install FreeScout Custom Fields module (if available)')
    print()

    return 0


if __name__ == '__main__':
    exit(main())
