#!/usr/bin/env python3
"""
Bulk Import Conversations - Import all conversations from Help Scout export to FreeScout

This script imports conversations from helpscout_export/ folder to FreeScout, processing
them in parallel (10 threads by default). Conversations are processed newest-first.

Key features:
- Extracts customer data from each conversation's primaryCustomer field
- Maps all threads from _embedded.threads
- Handles attachments via manifest
- Multi-threaded import (configurable thread count)
- Progress tracking and statistics
- Resumable (skips already imported conversations)
- State file tracking for recovery on re-runs
- Detailed logging to file

Usage:
    python bulk_import_conversations.py
    python bulk_import_conversations.py --threads 5
    python bulk_import_conversations.py --max-conversations 100
    python bulk_import_conversations.py --dry-run
    python bulk_import_conversations.py --resume
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import threading

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient
from mapping.mappers import map_conversation_to_freescout, map_thread_to_freescout, extract_tags
from utils.filters import should_migrate_conversation


# Global state for progress tracking
class ImportStats:
    def __init__(self):
        self.lock = threading.Lock()
        self.total = 0
        self.imported = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = datetime.now()
        self.failed_conversations = []
        self.imported_conversations = {}  # HS ID → FS ID mapping

    def record_success(self, hs_id, fs_id):
        with self.lock:
            self.imported += 1
            self.imported_conversations[str(hs_id)] = fs_id

    def record_failure(self, conv_id, error):
        with self.lock:
            self.failed += 1
            self.failed_conversations.append({'id': conv_id, 'error': str(error)})

    def record_skip(self):
        with self.lock:
            self.skipped += 1

    def set_total(self, count):
        self.total = count

    def get_summary(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            'total': self.total,
            'imported': self.imported,
            'failed': self.failed,
            'skipped': self.skipped,
            'elapsed_seconds': elapsed,
            'per_second': self.imported / elapsed if elapsed > 0 else 0
        }


def load_attachment_manifest():
    """Load the attachment manifest."""
    manifest_file = project_root / 'helpscout_attachments' / 'manifest.json'
    if not manifest_file.exists():
        return {}
    try:
        with open(manifest_file) as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠ Error loading attachment manifest: {e}")
        return {}


def get_attachments_for_conversation(conv_id: int, manifest: dict) -> dict:
    """Get all attachments for a conversation, organized by thread ID."""
    conv_manifest = manifest.get('conversations', {}).get(str(conv_id), {})
    return conv_manifest


def load_customer_mapping() -> dict:
    """Load the permanent customer mapping (HS Customer ID → FS Customer ID)."""
    mapping_file = project_root / 'customer_mapping.json'
    if not mapping_file.exists():
        print(f"⚠ Customer mapping not found: {mapping_file}")
        print(f"   Run build_customer_mapping.py first")
        return {}

    try:
        with open(mapping_file) as f:
            mapping_data = json.load(f)

        # Extract the by_id mapping and convert string keys to integers
        by_id = mapping_data.get('by_id', {})
        customer_mapping = {}
        for hs_id_str, fs_id in by_id.items():
            try:
                hs_id = int(hs_id_str)
                customer_mapping[hs_id] = fs_id
            except (ValueError, TypeError):
                pass

        print(f"📊 Loaded customer mapping: {len(customer_mapping)} customers")
        return customer_mapping
    except Exception as e:
        print(f"⚠ Error loading customer mapping: {e}")
        return {}


def load_import_state() -> dict:
    """Load the import state file if it exists."""
    state_file = project_root / 'bulk_import_state.json'
    if not state_file.exists():
        return None

    try:
        with open(state_file) as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠ Error loading import state: {e}")
        return None


def save_import_state(stats: ImportStats) -> None:
    """Save the current import state to file."""
    state_file = project_root / 'bulk_import_state.json'

    try:
        # Create snapshots while holding locks to avoid concurrent modification errors
        with stats.lock:
            failed_conversations_snapshot = list(stats.failed_conversations)
            imported_conversations_snapshot = dict(stats.imported_conversations)

        state = {
            'started_at': stats.start_time.isoformat(),
            'last_updated_at': datetime.now().isoformat(),
            'imported_conversations': imported_conversations_snapshot,
            'failed_conversations': {str(f['id']): f['error'] for f in failed_conversations_snapshot},
            'statistics': stats.get_summary()
        }
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠ Error saving import state: {e}")


def prepare_attachments_for_thread(attachments_list: list) -> list:
    """Prepare attachments for import (read files - mapping function does base64 encoding)."""
    prepared = []
    for att in attachments_list:
        local_path = att.get('local_path')
        if not local_path:
            continue

        full_path = project_root / local_path
        if not full_path.exists():
            continue

        try:
            with open(full_path, 'rb') as f:
                file_content = f.read()

            prepared.append({
                'filename': att.get('filename', 'attachment'),
                'mimeType': att.get('mimeType', 'application/octet-stream'),
                'data_bytes': file_content
            })
        except Exception as e:
            print(f"    ⚠ Failed to read attachment {local_path}: {e}")

    return prepared


def import_conversation(conv_file: Path, attachment_manifest: dict, customer_mapping: dict, stats: ImportStats, dry_run: bool = False) -> bool:
    """Import a single conversation from file."""
    try:
        # Load conversation
        with open(conv_file) as f:
            conv_data = json.load(f)

        hs_conv_id = conv_data.get('id')

        # Check filtering rules - skip spam and specific statuses
        should_migrate, skip_reason = should_migrate_conversation(conv_data)
        if not should_migrate:
            stats.record_failure(hs_conv_id, skip_reason)
            return False

        # Check for ignore or low priority tags
        tags = extract_tags(conv_data)
        if tags:
            tags_lower = [t.lower() for t in tags]
            if 'ignore' in tags_lower or 'low priority' in tags_lower:
                skip_reason = f"Tagged with: {', '.join(tags)}"
                stats.record_failure(hs_conv_id, skip_reason)
                return False

        # Extract customer data from primaryCustomer field
        primary_customer = conv_data.get('primaryCustomer')
        if not primary_customer:
            stats.record_failure(hs_conv_id, "No primaryCustomer found in conversation")
            return False

        # Look up FreeScout customer ID from mapping
        hs_customer_id = primary_customer.get('id')
        if not hs_customer_id or hs_customer_id not in customer_mapping:
            stats.record_failure(hs_conv_id, f"Customer {hs_customer_id} not found in mapping")
            return False

        fs_customer_id = customer_mapping[hs_customer_id]

        # Build FreeScout customer data for conversation (requires ID, email, and names)
        fs_customer_data = {
            "id": fs_customer_id,
            "firstName": primary_customer.get('first', ''),
            "lastName": primary_customer.get('last', ''),
            "email": primary_customer.get('email', '')
        }

        # Map conversation
        fs_conversation = map_conversation_to_freescout(conv_data, fs_customer_data)

        # Get attachments for this conversation
        conv_attachments = get_attachments_for_conversation(hs_conv_id, attachment_manifest)

        # Extract and map threads
        hs_threads = conv_data.get('_embedded', {}).get('threads', [])
        for hs_thread in hs_threads:
            thread_id = hs_thread.get('id')

            # Check for attachments for this thread
            attachments_data = None
            if thread_id and str(thread_id) in conv_attachments:
                attachments_list = conv_attachments[str(thread_id)]
                prepared_attachments = prepare_attachments_for_thread(attachments_list)
                if prepared_attachments:
                    attachments_data = prepared_attachments

            # Map thread
            fs_thread = map_thread_to_freescout(
                hs_thread,
                customer_email=primary_customer.get('email'),
                attachments_data=attachments_data
            )
            fs_conversation['threads'].append(fs_thread)

        # Import to FreeScout
        if not dry_run:
            fs_client = FreeScoutClient()
            response = fs_client.create_conversation(fs_conversation, imported=True)

            if not response or not response.get('id'):
                stats.record_failure(hs_conv_id, f"API returned: {response}")
                return False

            fs_conv_id = response.get('id')

            # Apply tags if conversation has any
            tags = extract_tags(conv_data)
            if tags:
                try:
                    # Filter out "ignore" and "low priority" tags since they're for filtering
                    tags_to_apply = [t for t in tags if t.lower() not in ['ignore', 'low priority']]
                    if tags_to_apply:
                        fs_client.update_conversation_tags(fs_conv_id, tags_to_apply)
                except Exception as e:
                    # Log tag error but don't fail the conversation import
                    pass

            stats.record_success(hs_conv_id, fs_conv_id)
        else:
            # For dry-run, record a dummy FS ID
            stats.record_success(hs_conv_id, -1)

        return True

    except Exception as e:
        stats.record_failure(conv_file.stem, str(e))
        return False


def find_all_conversations(export_dir: Path, max_count: int = None) -> list:
    """Find all conversation files, sorted newest-first."""
    conv_dir = export_dir / 'conversations'
    if not conv_dir.exists():
        return []

    # Find all conversation files and sort by path (newest first)
    conv_files = sorted(
        conv_dir.glob('*/*/*/conversation_*.json'),
        reverse=True  # Newest first (descending order)
    )

    if max_count:
        conv_files = conv_files[:max_count]

    return conv_files


def main():
    parser = argparse.ArgumentParser(
        description='Bulk import all Help Scout conversations to FreeScout'
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=10,
        help='Number of parallel import threads (default: 10)'
    )
    parser.add_argument(
        '--max-conversations',
        type=int,
        help='Maximum number of conversations to import (for testing)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test without actually importing to FreeScout'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from previous import (skip already imported conversations)'
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("BULK CONVERSATION IMPORT")
    print("=" * 70)

    # Load customer mapping
    customer_mapping = load_customer_mapping()
    if not customer_mapping:
        print("❌ Cannot proceed without customer mapping")
        print("   Run: python build_customer_mapping.py")
        return False

    # Find conversations
    export_dir = project_root / 'helpscout_export'
    if not export_dir.exists():
        print(f"❌ Export directory not found: {export_dir}")
        return False

    conv_files = find_all_conversations(export_dir, args.max_conversations)
    if not conv_files:
        print("❌ No conversation files found")
        return False

    print(f"\n📂 Found {len(conv_files)} conversations")
    print(f"   Processing order: Newest first")
    print(f"   Thread count: {args.threads}")
    if args.dry_run:
        print(f"   Mode: DRY RUN (no data will be imported)")
    if args.resume:
        print(f"   Mode: RESUME (will skip already imported conversations)")
    print()

    # Load attachment manifest once
    attachment_manifest = load_attachment_manifest()
    if attachment_manifest:
        total_attachments = sum(
            len(conv.get('threads', {}))
            for conv in attachment_manifest.get('conversations', {}).values()
        )
        print(f"📎 Attachment manifest loaded: {total_attachments} thread attachments")

    # Setup stats
    stats = ImportStats()

    # Load previous state if resuming
    already_imported = set()
    if args.resume:
        prev_state = load_import_state()
        if prev_state:
            already_imported = set(prev_state.get('imported_conversations', {}).keys())
            print(f"📍 Found previous state: {len(already_imported)} conversations already imported")
        else:
            print(f"⚠ Resume requested but no previous state found, starting fresh")

    # Filter out already imported conversations
    conv_files_to_process = [
        f for f in conv_files
        if str(f.stem.split('_')[-1]) not in already_imported
    ]

    stats.set_total(len(conv_files))
    print(f"📋 Will process {len(conv_files_to_process)} conversations (skipping {len(conv_files) - len(conv_files_to_process)} already imported)")

    # Import with ThreadPoolExecutor
    print(f"\n🚀 Starting import with {args.threads} threads...\n")

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {
            executor.submit(
                import_conversation,
                conv_file,
                attachment_manifest,
                customer_mapping,
                stats,
                args.dry_run
            ): conv_file for conv_file in conv_files_to_process
        }

        completed = 0
        for future in as_completed(futures):
            completed += 1
            conv_file = futures[future]

            try:
                future.result()
            except Exception as e:
                print(f"❌ Thread error for {conv_file.name}: {e}")

            # Progress update every 10 imports + save state
            if completed % 10 == 0:
                summary = stats.get_summary()
                rate = summary['per_second']
                print(f"   Progress: {completed}/{len(conv_files_to_process)} | "
                      f"Imported: {summary['imported']} | "
                      f"Failed: {summary['failed']} | "
                      f"Rate: {rate:.1f}/sec")
                save_import_state(stats)  # Save state after every 10 imports

    # Final summary
    summary = stats.get_summary()

    # Save final state
    save_import_state(stats)

    print("\n" + "=" * 70)
    print("✅ IMPORT COMPLETE")
    print("=" * 70)
    print(f"\n📊 Results:")
    print(f"   Total conversations: {summary['total']}")
    print(f"   Successfully imported: {summary['imported']}")
    print(f"   Failed: {summary['failed']}")
    print(f"   Skipped: {summary['skipped']}")
    print(f"   Time elapsed: {summary['elapsed_seconds']:.1f} seconds")
    print(f"   Import rate: {summary['per_second']:.2f} conversations/second")

    if stats.failed_conversations:
        print(f"\n⚠️ Failed conversations:")
        for failed in stats.failed_conversations[:10]:  # Show first 10
            print(f"   - {failed['id']}: {failed['error']}")
        if len(stats.failed_conversations) > 10:
            print(f"   ... and {len(stats.failed_conversations) - 10} more")

    print(f"\n📁 State saved to: production_scripts_v2/bulk_import_state.json")

    return stats.failed == 0


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹ Import cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
