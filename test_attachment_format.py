#!/usr/bin/env python3
"""
Test script to verify attachment format is correct.

This script tests that attachments are being created with the correct format
('content' with binary data) instead of the incorrect format ('data' with base64).
"""
import json
from pathlib import Path
import sys
from mapping.mappers import map_thread_to_freescout


def test_attachment_format():
    """Test that attachments use correct format for FreeScout API."""

    print("=" * 70)
    print("ATTACHMENT FORMAT TEST")
    print("=" * 70)

    # Load a sample attachment from the manifest
    attachments_dir = Path('helpscout_attachments')
    manifest_file = attachments_dir / 'manifest.json'

    if not manifest_file.exists():
        print("✗ No attachment manifest found - run download_attachments.py first")
        return False

    with open(manifest_file) as f:
        manifest = json.load(f)

    # Get first conversation with attachments
    conv_data = None
    conv_id = None
    for cid, threads_data in manifest['conversations'].items():
        if threads_data:
            conv_id = cid
            conv_data = threads_data
            break

    if not conv_data:
        print("✗ No conversations with attachments found")
        return False

    # Get first attachment
    thread_id = list(conv_data.keys())[0]
    attachments = conv_data[thread_id]
    first_att = attachments[0]

    print(f"\nTesting with conversation {conv_id}, thread {thread_id}")
    print(f"Attachment: {first_att['filename']}")

    # Read the actual attachment file
    local_path = Path(first_att['local_path'])
    if not local_path.exists():
        print(f"✗ Attachment file not found: {local_path}")
        return False

    with open(local_path, 'rb') as f:
        file_content = f.read()

    # Verify it's actual binary, not JSON
    try:
        json_check = json.loads(file_content)
        if isinstance(json_check, dict) and 'data' in json_check:
            print(f"✗ FAILED: File is JSON-wrapped (old format): {file_content[:100]}")
            return False
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass  # Good - it's not JSON

    print(f"✓ File is binary (not JSON): {len(file_content)} bytes")

    # Check file header to see what type it is
    if file_content[:4] == b'%PDF':
        print("✓ File is a valid PDF (starts with %PDF)")
    elif file_content[:3] == b'GIF' or file_content[:3] == b'\x89PN':
        print("✓ File is a valid image (GIF/PNG)")
    elif file_content[:2] == b'\xff\xd8':
        print("✓ File is a valid JPEG")
    else:
        print(f"✓ File is binary data (header: {file_content[:10]})")

    # Test the mapper
    print("\n" + "-" * 70)
    print("Testing mapper output:")
    print("-" * 70)

    sample_thread = {
        'id': 123,
        'type': 'customer',
        'body': 'Test message',
        'createdAt': '2025-01-01T00:00:00Z'
    }

    sample_attachments = [{
        'filename': first_att['filename'],
        'data_bytes': file_content,
        'mimeType': first_att['mimeType']
    }]

    # Map the thread
    mapped = map_thread_to_freescout(
        sample_thread,
        customer_email='test@example.com',
        attachments_data=sample_attachments
    )

    # Check attachment format
    if 'attachments' not in mapped:
        print("✗ FAILED: No attachments in mapped data")
        return False

    att = mapped['attachments'][0]

    # Check for correct fields
    has_content = 'content' in att
    has_data = 'data' in att

    print(f"\nAttachment fields in mapped data:")
    print(f"  'content' field: {'✓ Present' if has_content else '✗ Missing'}")
    print(f"  'data' field: {'✗ Present (WRONG!)' if has_data else '✓ Not present (correct)'}")

    if has_content:
        content = att['content']
        is_bytes = isinstance(content, bytes)
        is_str = isinstance(content, str)

        print(f"\nContent field type:")
        print(f"  Is bytes: {'✓ Yes' if is_bytes else '✗ No'}")
        print(f"  Is string: {'✗ Yes (WRONG!)' if is_str else '✓ No'}")

        if is_bytes:
            print(f"  Length: {len(content)} bytes")
            print(f"  Matches file: {'✓ Yes' if content == file_content else '✗ No'}")

            if content == file_content and is_bytes:
                print("\n" + "=" * 70)
                print("✓ SUCCESS: Attachment format is CORRECT")
                print("=" * 70)
                print("\nAttachments will now work correctly in FreeScout!")
                return True

    print("\n" + "=" * 70)
    print("✗ FAILURE: Attachment format is INCORRECT")
    print("=" * 70)
    return False


if __name__ == '__main__':
    success = test_attachment_format()
    sys.exit(0 if success else 1)
