"""
Fix conversation statuses and assignees in FreeScout.

This script reads migrated conversations from the progress file,
fetches their current status from Help Scout, and updates FreeScout
to match.

Usage:
    python fix_conversation_statuses.py [--dry-run]
"""
import json
import sys
import argparse
from pathlib import Path
from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient
from mapping.mappers import map_status, map_user_id


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

    print(f"Found {len(conversation_mapping)} migrated conversations")

    # Initialize clients
    hs_client = HelpScoutClient()
    fs_client = FreeScoutClient()

    # Statistics
    stats = {
        'total': 0,
        'status_updated': 0,
        'assignee_updated': 0,
        'no_changes': 0,
        'errors': 0
    }

    print("\n" + "=" * 70)
    if args.dry_run:
        print("DRY RUN - No changes will be made")
    else:
        print("UPDATING CONVERSATIONS")
    print("=" * 70)

    # We'll fetch Help Scout conversations on-demand instead of all upfront
    # This is faster since we only fetch what we need
    print("\nWill fetch Help Scout conversation data on-demand...")

    # Process each conversation
    items = list(conversation_mapping.items())
    if args.limit:
        items = items[:args.limit]
        print(f"Processing first {args.limit} conversations (--limit)")

    print("\nUpdating FreeScout conversations...")

    for i, (hs_id, fs_id) in enumerate(items, 1):
        stats['total'] += 1
        print(f"\n[{i}/{len(items)}] HS:{hs_id} → FS:{fs_id}")

        try:
            # Fetch Help Scout conversation
            hs_conv = hs_client.get_conversation(int(hs_id))
            hs_status = hs_conv.get('status')
            hs_assignee = hs_conv.get('assignee')

            # Get current status from FreeScout
            fs_conv = fs_client.get_conversation(int(fs_id))
            fs_status = fs_conv.get('status')
            fs_assignee = fs_conv.get('assignee')

            # Map Help Scout status to FreeScout
            expected_status = map_status(hs_status)

            # Check what needs updating
            updates = {}
            changes = []

            # Check status
            if fs_status != expected_status:
                updates['status'] = expected_status
                changes.append(f"status: {fs_status} → {expected_status}")
                stats['status_updated'] += 1

            # Check assignee
            expected_assignee_id = None
            if hs_assignee and hs_assignee.get('id'):
                expected_assignee_id = map_user_id(hs_assignee['id'])

            current_assignee_id = fs_assignee.get('id') if fs_assignee else None

            if expected_assignee_id != current_assignee_id:
                if expected_assignee_id:
                    updates['assignTo'] = expected_assignee_id
                    changes.append(f"assignee: {current_assignee_id} → {expected_assignee_id}")
                    stats['assignee_updated'] += 1
                elif current_assignee_id:
                    # Was assigned in FS but not in HS - should unassign
                    # FreeScout might not support unassigning, so we'll skip this
                    pass

            # Apply updates
            if updates:
                print(f"  Changes: {', '.join(changes)}")
                if not args.dry_run:
                    fs_client.update_conversation(int(fs_id), updates)
                    print(f"  ✓ Updated")
                else:
                    print(f"  → Would update (dry run)")
            else:
                stats['no_changes'] += 1
                print(f"  ✓ No changes needed")

        except Exception as e:
            stats['errors'] += 1
            print(f"  ✗ Error: {e}")

        # Progress indicator every 50 conversations
        if i % 50 == 0:
            print(f"\n  Progress: {i}/{len(items)} processed...")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total conversations processed: {stats['total']}")
    print(f"Status updated: {stats['status_updated']}")
    print(f"Assignee updated: {stats['assignee_updated']}")
    print(f"No changes needed: {stats['no_changes']}")
    print(f"Errors: {stats['errors']}")

    if args.dry_run:
        print("\nThis was a DRY RUN - no changes were made")
        print("Run without --dry-run to apply changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
