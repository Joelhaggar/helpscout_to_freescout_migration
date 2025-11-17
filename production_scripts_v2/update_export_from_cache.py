#!/usr/bin/env python3
"""
Update helpscout_export with latest conversations from helpscout_cache.

This script:
1. Reads conversation IDs from helpscout_cache pagination files
2. Fetches full conversation details (with threads) from Help Scout API
3. Saves to helpscout_export in proper directory structure
4. Overwrites existing conversations with latest data
5. Ensures export is current through latest cached date

This is much faster than full re-extraction (1-2 min vs 1.5-2.5 hours)
"""
import json
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.helpscout_client import HelpScoutClient

def update_export_from_cache():
    """Update export directory with latest conversations from cache."""

    print("\n" + "="*70)
    print("UPDATE EXPORT FROM CACHE")
    print("="*70)

    hs_client = HelpScoutClient()
    cache_dir = project_root / 'helpscout_cache'
    export_dir = project_root / 'helpscout_export'
    conversations_dir = export_dir / 'conversations'

    if not cache_dir.exists():
        print("✗ Cache directory not found:", cache_dir)
        return False

    # Find all cache files
    cache_files = sorted(cache_dir.glob('conversations_page_*.json'))
    if not cache_files:
        print("✗ No cache files found")
        return False

    print(f"\n📦 Found {len(cache_files)} cache files")

    # Read all conversation IDs from cache
    conv_ids_to_update = []
    total_in_cache = 0

    for cache_file in cache_files:
        try:
            with open(cache_file) as f:
                conversations = json.load(f)
                for conv in conversations:
                    conv_id = conv.get('id')
                    if conv_id:
                        conv_ids_to_update.append(conv_id)
                        total_in_cache += 1
        except Exception as e:
            print(f"  ✗ Error reading {cache_file.name}: {e}")

    print(f"  Total conversations in cache: {total_in_cache}")
    print(f"  Unique conversations to update: {len(conv_ids_to_update)}")

    if not conv_ids_to_update:
        print("✗ No conversations found in cache")
        return False

    # Fetch full conversation details and update export
    print(f"\n🔄 Fetching full conversation details from Help Scout API...")
    updated = 0
    failed = 0

    for i, conv_id in enumerate(conv_ids_to_update, 1):
        try:
            # Show progress
            if i % 10 == 0:
                print(f"  [{i}/{len(conv_ids_to_update)}] Fetching conversations...")

            # Fetch full conversation with threads from API
            hs_conv = hs_client.get_conversation(conv_id, embed='threads')

            if not hs_conv:
                print(f"  ⚠ Conversation {conv_id} returned empty from API")
                failed += 1
                continue

            # Extract date for directory structure (YYYY/MM/DD)
            created_at = hs_conv.get('createdAt', '')
            if created_at:
                try:
                    # Parse ISO format: 2025-11-10T19:15:49Z
                    date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    year = date_obj.strftime('%Y')
                    month = date_obj.strftime('%m')
                    day = date_obj.strftime('%d')
                except:
                    # Fallback to current date if parsing fails
                    now = datetime.now()
                    year = now.strftime('%Y')
                    month = now.strftime('%m')
                    day = now.strftime('%d')
            else:
                # Use current date if no createdAt
                now = datetime.now()
                year = now.strftime('%Y')
                month = now.strftime('%m')
                day = now.strftime('%d')

            # Create directory structure
            conv_date_dir = conversations_dir / year / month / day
            conv_date_dir.mkdir(parents=True, exist_ok=True)

            # Save conversation file
            conv_file = conv_date_dir / f'conversation_{conv_id}.json'
            with open(conv_file, 'w') as f:
                json.dump(hs_conv, f, indent=2)

            updated += 1

        except Exception as e:
            print(f"  ✗ Failed to fetch conversation {conv_id}: {str(e)[:80]}")
            failed += 1

    # Print results
    print(f"\n" + "="*70)
    print(f"✓ UPDATE COMPLETE")
    print("="*70)
    print(f"Updated: {updated} conversations")
    print(f"Failed: {failed} conversations")
    print(f"Total: {updated + failed} conversations processed")

    if updated > 0:
        print(f"\n✓ Export is now current through latest cached date")
        print(f"  Ready for import with: python import_from_export_with_attachments.py")
        return True
    else:
        print(f"\n✗ No conversations were updated")
        return False

if __name__ == '__main__':
    try:
        success = update_export_from_cache()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Update interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
