"""
Fix conversation statuses and assignees in FreeScout using cached Help Scout data.

This script uses the cached Help Scout conversation data to update FreeScout
conversations with the correct status and assignee.

Usage:
    python fix_conversation_statuses_v3.py [--dry-run] [--limit N]
"""
import json
import sys
import argparse
from pathlib import Path
from api.freescout_client import FreeScoutClient
from config.config import Config
from mapping.mappers import map_status, map_user_id


def load_helpscout_cache():
    """Load all Help Scout conversations from cache."""
    cache_dir = Path(__file__).parent / 'helpscout_cache'
    if not cache_dir.exists():
        print("Error: helpscout_cache directory not found")
        return {}

    print("Loading Help Scout cache...")
    conversations = {}
    page = 1
    pages_loaded = 0

    while True:
        cache_file = cache_dir / f'conversations_page_{page:04d}.json'
        if not cache_file.exists():
            break

        with open(cache_file, 'r') as f:
            page_conversations = json.load(f)
            for conv in page_conversations:
                conversations[conv['id']] = conv
            pages_loaded += 1

        page += 1

    print(f"  Loaded {len(conversations)} conversations from {pages_loaded} cached pages")
    return conversations


def main():
    parser = argparse.ArgumentParser(description='Fix conversation statuses and assignees in FreeScout')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Only process first N conversations (for testing)'
    )
    args = parser.parse_args()

    # Load migration progress
    progress_file = Path(__file__).parent / 'migration_progress.json'
    if not progress_file.exists():
        print("Error: migration_progress.json not found")
        return 1

    print("Loading migration progress...")
    with open(progress_file, 'r') as f:
        data = json.load(f)

    conversation_mapping = data.get('conversation_mapping', {})

    if not conversation_mapping:
        print("No conversations found in progress file")
        return 1

    print(f"Found {len(conversation_mapping)} migrated conversations\n")

    # Load Help Scout cache
    hs_conversations = load_helpscout_cache()

    if not hs_conversations:
        print("Error: No cached Help Scout conversations found")
        return 1

    # Initialize FreeScout client
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    # Statistics
    stats = {
        'total': 0,
        'status_updated': 0,
        'assignee_updated': 0,
        'no_changes': 0,
        'not_in_cache': 0,
        'errors': 0
    }

    print("\n" + "=" * 70)
    if args.dry_run:
        print("DRY RUN - No changes will be made")
    else:
        print("UPDATING CONVERSATIONS")
    print("=" * 70)

    # Process each conversation
    items = list(conversation_mapping.items())
    if args.limit:
        items = items[:args.limit]
        print(f"\nProcessing first {args.limit} conversations (--limit)")

    print("\nProcessing conversations...\n")

    for i, (hs_id, fs_id) in enumerate(items, 1):
        stats['total'] += 1

        # Progress indicator
        if i % 100 == 0:
            print(f"Progress: {i}/{len(items)} processed...")

        try:
            # Get Help Scout conversation from cache
            hs_conv = hs_conversations.get(int(hs_id))
            if not hs_conv:
                stats['not_in_cache'] += 1
                print(f"[{i}/{len(items)}] HS:{hs_id} → FS:{fs_id} - Not in cache, skipping")
                continue

            hs_status = hs_conv.get('status')
            hs_assignee = hs_conv.get('assignee')

            # Map Help Scout status to FreeScout
            expected_status = map_status(hs_status)

            # Check what needs updating
            updates = {}
            changes = []

            # Always update status (we know it's likely wrong)
            updates['status'] = expected_status
            changes.append(f"status → {expected_status}")
            stats['status_updated'] += 1

            # Check assignee
            if hs_assignee and hs_assignee.get('id'):
                expected_assignee_id = map_user_id(hs_assignee['id'])
                if expected_assignee_id:
                    updates['assignTo'] = expected_assignee_id
                    changes.append(f"assignee → {expected_assignee_id}")
                    stats['assignee_updated'] += 1

            # Apply updates
            if updates:
                updates['byUser'] = 8  # Required by FreeScout

                if not args.dry_run:
                    fs_client.update_conversation(int(fs_id), updates)
                    if i % 100 == 0:  # Only print details every 100
                        print(f"  [{i}] FS:{fs_id} - Updated: {', '.join(changes)}")
                else:
                    print(f"[{i}/{len(items)}] FS:{fs_id} - Would update: {', '.join(changes)}")
            else:
                stats['no_changes'] += 1

        except Exception as e:
            stats['errors'] += 1
            print(f"[{i}/{len(items)}] HS:{hs_id} → FS:{fs_id} - Error: {e}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total conversations processed: {stats['total']}")
    print(f"Status updated: {stats['status_updated']}")
    print(f"Assignee updated: {stats['assignee_updated']}")
    print(f"No changes needed: {stats['no_changes']}")
    print(f"Not in cache: {stats['not_in_cache']}")
    print(f"Errors: {stats['errors']}")

    if args.dry_run:
        print("\nThis was a DRY RUN - no changes were made")
        print("Run without --dry-run to apply changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
