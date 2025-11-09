#!/usr/bin/env python3
"""
Check for Help Scout conversations that have been updated since migration.

This uses the Help Scout API's modifiedSince parameter to find conversations
that may need to be re-synced.
"""
import json
from datetime import datetime, timedelta
from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient
from config.config import Config


def main():
    # Load migration progress
    with open('migration_progress.json', 'r') as f:
        progress = json.load(f)

    migration_date = progress.get('completed_at')
    if not migration_date:
        migration_date = progress.get('started_at')

    print('=' * 70)
    print('CHECK FOR HELP SCOUT UPDATES SINCE MIGRATION')
    print('=' * 70)
    print()

    if migration_date:
        print(f'Original migration date: {migration_date}')
    else:
        print('Note: Migration date not found in progress file')
    print()

    # Ask user for cutoff date or use migration date
    print('Check for conversations modified since:')
    if migration_date:
        print(f'  1. Migration date ({migration_date})')
    else:
        print(f'  1. Migration date (not available)')
    print(f'  2. Last 7 days')
    print(f'  3. Custom date (YYYY-MM-DD)')
    print()

    choice = input('Enter choice (1-3) [2]: ').strip() or '2'

    if choice == '1' and migration_date:
        modified_since = migration_date
    elif choice == '2':
        date_7_days_ago = datetime.now() - timedelta(days=7)
        modified_since = date_7_days_ago.strftime('%Y-%m-%dT%H:%M:%SZ')
    elif choice == '3':
        date_str = input('Enter date (YYYY-MM-DD): ').strip()
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            modified_since = date_obj.strftime('%Y-%m-%dT00:00:00Z')
        except ValueError:
            print('Error: Invalid date format')
            return 1
    else:
        print('Invalid choice')
        return 1

    print()
    print(f'Checking Help Scout for conversations modified since {modified_since}...')
    print()

    # Initialize clients
    hs_client = HelpScoutClient()
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    # Get mailbox ID from config
    mailbox_id = 312012  # Your Help Scout mailbox ID

    # Get conversations modified since date
    print('Fetching updated conversations from Help Scout...')
    updated_convs = hs_client.get_all_conversations(
        mailbox=mailbox_id,
        status='all',
        modified_since=modified_since
    )

    print(f'Found {len(updated_convs)} conversations modified since {modified_since}')
    print()

    if not updated_convs:
        print('No updated conversations found.')
        return 0

    # Check which ones are in our migration
    conversation_mapping = progress.get('conversation_mapping', {})

    migrated_and_updated = []
    new_conversations = []

    for conv in updated_convs:
        hs_id = str(conv.get('id'))
        if hs_id in conversation_mapping:
            migrated_and_updated.append({
                'hs_id': hs_id,
                'fs_id': conversation_mapping[hs_id],
                'subject': conv.get('subject', '')[:60],
                'status': conv.get('status'),
                'modified': conv.get('userUpdatedAt', conv.get('createdAt'))
            })
        else:
            new_conversations.append({
                'hs_id': hs_id,
                'subject': conv.get('subject', '')[:60],
                'status': conv.get('status'),
                'created': conv.get('createdAt')
            })

    print('=' * 70)
    print('RESULTS')
    print('=' * 70)
    print()

    print(f'Previously migrated conversations that were updated: {len(migrated_and_updated)}')
    if migrated_and_updated:
        print()
        print('These conversations exist in FreeScout but may be out of sync:')
        for conv in migrated_and_updated[:20]:  # Show first 20
            print(f'  HS:{conv["hs_id"]} → FS:{conv["fs_id"]}')
            print(f'    Subject: {conv["subject"]}')
            print(f'    Status: {conv["status"]}')
            print(f'    Modified: {conv["modified"]}')
            print()

        if len(migrated_and_updated) > 20:
            print(f'  ... and {len(migrated_and_updated) - 20} more')
            print()

    print(f'New conversations (not in migration): {len(new_conversations)}')
    if new_conversations:
        print()
        print('These are new conversations created after migration:')
        for conv in new_conversations[:10]:  # Show first 10
            print(f'  HS:{conv["hs_id"]}')
            print(f'    Subject: {conv["subject"]}')
            print(f'    Status: {conv["status"]}')
            print(f'    Created: {conv["created"]}')
            print()

        if len(new_conversations) > 10:
            print(f'  ... and {len(new_conversations) - 10} more')
            print()

    print()
    print('NEXT STEPS:')
    if migrated_and_updated:
        print('1. Review the updated conversations to see if they need re-syncing')
        print('2. Consider creating a sync script to update statuses/threads')
    if new_conversations:
        print('3. Migrate new conversations using migrate_missing_conversations.py')
    print()

    # Save results to file
    results_file = 'helpscout_updates_check.json'
    with open(results_file, 'w') as f:
        json.dump({
            'checked_at': datetime.now().isoformat(),
            'modified_since': modified_since,
            'migrated_and_updated': migrated_and_updated,
            'new_conversations': new_conversations
        }, f, indent=2)

    print(f'Results saved to {results_file}')

    return 0


if __name__ == '__main__':
    exit(main())
