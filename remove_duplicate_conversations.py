#!/usr/bin/env python3
"""
Find and remove duplicate conversations based on Helpscout_ID custom field.
Keeps the FIRST occurrence and deletes subsequent duplicates.
"""
from api.freescout_client import FreeScoutClient
from config.config import Config
from collections import defaultdict


def find_duplicates(fs_client: FreeScoutClient, mailbox_id: int = None):
    """
    Find duplicate conversations by Helpscout_ID custom field.

    Returns:
        dict: Mapping of Helpscout_ID -> list of FreeScout conversation IDs
    """
    print('=' * 70)
    print('FINDING DUPLICATE CONVERSATIONS')
    print('=' * 70)
    print()

    helpscout_id_map = defaultdict(list)
    page = 1
    total_conversations = 0

    while True:
        print(f'Fetching page {page}...')

        # Get all conversations
        params = {'status': 'all', 'page': page, 'page_size': 50}
        if mailbox_id:
            params['mailboxId'] = mailbox_id

        response = fs_client.get_conversations(**params)

        conversations = response.get('_embedded', {}).get('conversations', [])

        if not conversations:
            print('No more conversations found.')
            break

        print(f'  Processing {len(conversations)} conversations...')
        total_conversations += len(conversations)

        for conv in conversations:
            conv_id = conv['id']
            custom_fields = conv.get('customFields', [])

            # Find Helpscout_ID custom field
            helpscout_id = None
            for field in custom_fields:
                if field.get('name') == 'Helpscout':
                    helpscout_id = field.get('value')
                    break

            if helpscout_id:
                helpscout_id_map[helpscout_id].append(conv_id)

        page += 1

    print()
    print(f'Total conversations scanned: {total_conversations}')
    print()

    # Find duplicates
    duplicates = {hs_id: fs_ids for hs_id, fs_ids in helpscout_id_map.items() if len(fs_ids) > 1}

    print(f'Found {len(duplicates)} Help Scout conversations with duplicates')
    print()

    return duplicates, helpscout_id_map


def remove_duplicates(fs_client: FreeScoutClient, duplicates: dict, dry_run: bool = True):
    """
    Remove duplicate conversations, keeping the first occurrence.

    Args:
        fs_client: FreeScout client
        duplicates: Dict mapping Helpscout_ID -> list of FreeScout conversation IDs
        dry_run: If True, only show what would be deleted without deleting
    """
    print('=' * 70)
    if dry_run:
        print('DRY RUN - SHOWING WHAT WOULD BE DELETED')
    else:
        print('REMOVING DUPLICATE CONVERSATIONS')
    print('=' * 70)
    print()

    total_to_delete = 0
    total_to_keep = 0

    for hs_id, fs_ids in sorted(duplicates.items()):
        # Sort by ID to keep the first created
        fs_ids_sorted = sorted(fs_ids)
        keep_id = fs_ids_sorted[0]
        delete_ids = fs_ids_sorted[1:]

        total_to_keep += 1
        total_to_delete += len(delete_ids)

        print(f'Helpscout ID: {hs_id}')
        print(f'  KEEP:   FreeScout #{keep_id}')
        for delete_id in delete_ids:
            print(f'  DELETE: FreeScout #{delete_id}')

        if not dry_run:
            for delete_id in delete_ids:
                try:
                    fs_client.delete_conversation(delete_id)
                    print(f'    ✓ Deleted #{delete_id}')
                except Exception as e:
                    print(f'    ✗ Failed to delete #{delete_id}: {e}')

        print()

    print('=' * 70)
    print('SUMMARY')
    print('=' * 70)
    print(f'Conversations to keep: {total_to_keep}')
    print(f'Duplicates to delete:  {total_to_delete}')
    print()

    if dry_run:
        print('This was a DRY RUN. No conversations were deleted.')
        print('Run with --delete flag to actually remove duplicates.')
    else:
        print('Duplicate removal complete!')
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Find and remove duplicate conversations')
    parser.add_argument('--delete', action='store_true',
                       help='Actually delete duplicates (default is dry-run)')
    args = parser.parse_args()

    print()
    print('=' * 70)
    print('DUPLICATE CONVERSATION REMOVAL TOOL')
    print('=' * 70)
    print(f'FreeScout URL: {Config.FREESCOUT_URL}')
    print()

    if args.delete:
        print('⚠️  WARNING: This will PERMANENTLY delete duplicate conversations!')
        print()
        response = input('Type "DELETE DUPLICATES" to confirm: ')
        if response != "DELETE DUPLICATES":
            print('Aborted.')
            return 1
        print()

    # Initialize FreeScout client
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    # Find duplicates (search all mailboxes)
    duplicates, helpscout_id_map = find_duplicates(fs_client)

    if not duplicates:
        print('✓ No duplicates found!')
        return 0

    # Remove duplicates
    remove_duplicates(fs_client, duplicates, dry_run=not args.delete)

    return 0


if __name__ == '__main__':
    exit(main())
