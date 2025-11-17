#!/usr/bin/env python3
"""
Test script to import a single conversation into FreeScout.
This is a minimal test to debug conversation import issues.

Usage:
    python test_single_conversation.py                      # Test most recent conversation
    python test_single_conversation.py 3132185360          # Test specific conversation ID
    python test_single_conversation.py 3132185360 2025/11/6  # Test with specific date path
"""
import sys
import json
from pathlib import Path
from datetime import datetime
import argparse

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient
from mapping.mappers import map_conversation_to_freescout, map_thread_to_freescout

def find_conversation_by_id(conv_id, date_path=None):
    """Find a specific conversation file by ID and optional date path."""
    conv_base_dir = project_root / 'helpscout_export' / 'conversations'

    if not conv_base_dir.exists():
        print(f"❌ Conversations directory not found: {conv_base_dir}")
        return None

    # If date path is provided, look in that specific path first
    if date_path:
        specific_path = conv_base_dir / date_path / f'conversation_{conv_id}.json'
        if specific_path.exists():
            print(f"📍 Found conversation at: {specific_path}")
            return specific_path
        print(f"⚠ Conversation not found at {specific_path}")
        print(f"   Searching in other date folders...")

    # Search all date folders
    conv_files = list(conv_base_dir.glob(f'*/*/*/conversation_{conv_id}.json'))

    if conv_files:
        print(f"📍 Found conversation at: {conv_files[0]}")
        return conv_files[0]

    print(f"❌ Conversation {conv_id} not found in any date folder")
    return None

def find_most_recent_conversation():
    """Find the most recent conversation file in the export."""
    conv_dir = project_root / 'helpscout_export' / 'conversations'

    if not conv_dir.exists():
        print(f"❌ Conversations directory not found: {conv_dir}")
        return None

    # Get all conversation files, sorted by path (newest first)
    conv_files = sorted(conv_dir.glob('*/*/*/conversation_*.json'), reverse=True)

    if not conv_files:
        print("❌ No conversation files found")
        return None

    print(f"📂 Found {len(conv_files)} total conversations")
    print(f"📌 Most recent: {conv_files[0]}")

    return conv_files[0]

def load_customer_mapping():
    """Load the permanent customer mapping."""
    mapping_file = project_root / 'customer_mapping.json'

    if not mapping_file.exists():
        print(f"⚠ Permanent customer mapping not found: {mapping_file}")
        return {}

    try:
        with open(mapping_file) as f:
            mapping_data = json.load(f)

        # Extract the by_id mapping
        id_mapping = mapping_data.get('by_id', {})

        # Convert string keys to integers
        customer_mapping = {}
        for hs_id_str, fs_id in id_mapping.items():
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

def load_attachment_manifest():
    """Load the attachment manifest."""
    manifest_file = project_root / 'helpscout_attachments' / 'manifest.json'

    if not manifest_file.exists():
        print(f"⚠ Attachment manifest not found: {manifest_file}")
        return {}

    try:
        with open(manifest_file) as f:
            manifest = json.load(f)
        return manifest
    except Exception as e:
        print(f"⚠ Error loading attachment manifest: {e}")
        return {}

def get_attachments_for_conversation(conv_id: int, manifest: dict) -> dict:
    """Get all attachments for a conversation, organized by thread ID."""
    conv_manifest = manifest.get('conversations', {}).get(str(conv_id), {})
    return conv_manifest

def prepare_attachments_for_thread(attachments_list: list) -> list:
    """Prepare attachments for import (read files - mapping function does base64 encoding)."""
    prepared = []

    for att in attachments_list:
        local_path = att.get('local_path')
        if not local_path:
            continue

        full_path = project_root / local_path

        if not full_path.exists():
            print(f"    ⚠ Attachment file missing: {local_path}")
            continue

        try:
            # Read file - the mapper will handle base64 encoding
            with open(full_path, 'rb') as f:
                file_content = f.read()

            prepared.append({
                'filename': att.get('filename', 'attachment'),
                'mimeType': att.get('mimeType', 'application/octet-stream'),
                'data_bytes': file_content  # Raw bytes - mapper will base64 encode
            })
            print(f"    ✓ Prepared attachment: {att.get('filename')}")
        except Exception as e:
            print(f"    ✗ Failed to read attachment {local_path}: {e}")

    return prepared

def test_single_conversation(conv_id=None, date_path=None):
    """Test importing a single conversation.

    Args:
        conv_id: Optional conversation ID to test. If None, tests most recent.
        date_path: Optional date path like '2025/11/6' for the conversation.
    """
    print("\n" + "="*70)
    print("SINGLE CONVERSATION TEST")
    print("="*70)

    # Find conversation
    if conv_id:
        conv_file = find_conversation_by_id(conv_id, date_path)
    else:
        conv_file = find_most_recent_conversation()

    if not conv_file:
        return False

    # Load conversation data
    try:
        with open(conv_file) as f:
            conv_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading conversation: {e}")
        return False

    hs_conv_id = conv_data.get('id')
    print(f"\n📋 Conversation ID: {hs_conv_id}")
    print(f"   Subject: {conv_data.get('subject', 'N/A')}")
    print(f"   Status: {conv_data.get('status', 'N/A')}")

    # Extract customer data from primaryCustomer field
    primary_customer = conv_data.get('primaryCustomer')
    if primary_customer:
        print(f"   Customer (primaryCustomer): {primary_customer.get('first')} {primary_customer.get('last')} ({primary_customer.get('email')})")
    else:
        print(f"   Customer (primaryCustomer): N/A")

    # Load customer mapping (for reference only in this test)
    customer_mapping = load_customer_mapping()

    # Map conversation to FreeScout format
    print("\n🔄 Mapping conversation to FreeScout format...")
    try:
        # Extract customer data from primaryCustomer if available
        fs_customer_data = None
        if primary_customer:
            fs_customer_data = {
                "firstName": primary_customer.get('first', ''),
                "lastName": primary_customer.get('last', ''),
                "email": primary_customer.get('email', '')
            }
            print(f"   Using primaryCustomer: {fs_customer_data}")
        else:
            print(f"   ⚠ No primaryCustomer found in conversation")
            # Return False since we need customer data
            return False

        fs_conversation = map_conversation_to_freescout(conv_data, fs_customer_data)

        # Load attachment manifest
        attachment_manifest = load_attachment_manifest()
        conv_attachments = get_attachments_for_conversation(hs_conv_id, attachment_manifest)

        # Extract and map threads from _embedded.threads
        hs_threads = conv_data.get('_embedded', {}).get('threads', [])
        print(f"   Found {len(hs_threads)} threads in conversation")

        for i, hs_thread in enumerate(hs_threads):
            try:
                thread_id = hs_thread.get('id')

                # Check if this thread has attachments in the manifest
                attachments_data = None
                if thread_id and str(thread_id) in conv_attachments:
                    print(f"   Preparing attachments for thread {i+1}...")
                    attachments_list = conv_attachments[str(thread_id)]
                    prepared_attachments = prepare_attachments_for_thread(attachments_list)
                    if prepared_attachments:
                        attachments_data = prepared_attachments

                # Map thread to FreeScout format
                fs_thread = map_thread_to_freescout(
                    hs_thread,
                    customer_email=primary_customer.get('email') if primary_customer else None,
                    attachments_data=attachments_data
                )
                fs_conversation['threads'].append(fs_thread)
                thread_type = fs_thread.get('type', 'unknown')
                has_attachments = '(with attachments)' if attachments_data else ''
                print(f"   ✓ Mapped thread {i+1}: type={thread_type} {has_attachments}")
            except Exception as e:
                print(f"   ⚠ Error mapping thread {i+1}: {e}")

        print(f"✓ Mapped successfully")
        print(f"   Total threads: {len(fs_conversation.get('threads', []))}")
        print(f"   Customer: {fs_conversation.get('customer', {})}")
    except Exception as e:
        print(f"❌ Mapping failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Try to import to FreeScout
    print("\n📤 Importing to FreeScout...")
    try:
        fs_client = FreeScoutClient()

        # Create conversation
        response = fs_client.create_conversation(fs_conversation)

        if response and response.get('id'):
            fs_conv_id = response['id']
            print(f"✅ Conversation created successfully!")
            print(f"   FreeScout ID: {fs_conv_id}")
            print(f"   HS ID→FS ID: {hs_conv_id}→{fs_conv_id}")
            return True
        else:
            print(f"❌ API returned unexpected response:")
            print(f"   {response}")
            return False

    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Test importing a single conversation into FreeScout'
    )
    parser.add_argument(
        'conv_id',
        nargs='?',
        help='Conversation ID to test (optional, tests most recent if not provided)'
    )
    parser.add_argument(
        'date_path',
        nargs='?',
        help='Date path like "2025/11/6" (optional, auto-detected if not provided)'
    )

    args = parser.parse_args()

    success = test_single_conversation(conv_id=args.conv_id, date_path=args.date_path)

    print("\n" + "="*70)
    if success:
        print("✅ TEST PASSED - Single conversation imported successfully")
    else:
        print("❌ TEST FAILED - See errors above")
    print("="*70)

    sys.exit(0 if success else 1)
