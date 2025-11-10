#!/usr/bin/env python3
"""
Test single conversation with attachment to verify the fix works correctly.

This script imports a specific conversation with an attachment to FreeScout
and verifies the attachment is stored correctly.
"""
import json
from pathlib import Path
from api.freescout_client import FreeScoutClient
from mapping.mappers import map_thread_to_freescout, map_status
from utils.filters import reorder_threads_for_attachments


def test_import_with_attachment():
    """Import a single test conversation with attachment."""

    print("=" * 70)
    print("TEST: Import Conversation with Attachment")
    print("=" * 70)

    # Initialize FreeScout client
    fs_client = FreeScoutClient()

    # Test conversation ID: Bender Return Label
    hs_conv_id = 2440816639
    conv_file = Path(
        "helpscout_export/conversations/2023/12/03/conversation_2440816639.json"
    )

    if not conv_file.exists():
        print(f"✗ Conversation file not found: {conv_file}")
        return False

    with open(conv_file) as f:
        hs_conv = json.load(f)

    print(f"\nSource: Help Scout")
    print(f"  ID: {hs_conv_id}")
    print(f"  Subject: {hs_conv.get('subject')}")

    # Get threads
    threads = hs_conv.get("_embedded", {}).get("threads", [])
    print(f"  Threads: {len(threads)}")

    # Reorder threads to put attachment thread first
    reordered_threads, was_reordered = reorder_threads_for_attachments(threads)
    if was_reordered:
        print(f"  ⚠ Reordered threads to move attachments to first thread")
    threads = reordered_threads

    # Check for attachments in manifest
    manifest_file = Path("helpscout_attachments/manifest.json")
    if not manifest_file.exists():
        print("✗ Attachment manifest not found")
        return False

    with open(manifest_file) as f:
        manifest = json.load(f)

    conv_attachments = manifest.get("conversations", {}).get(str(hs_conv_id), {})
    attachment_count = sum(len(atts) for atts in conv_attachments.values())

    print(f"  Attachments: {attachment_count}")

    if attachment_count == 0:
        print("✗ No attachments found for this conversation")
        return False

    # Prepare attachments from manifest
    prepared_attachments = []
    for thread_id, atts in conv_attachments.items():
        for att in atts:
            local_path = Path(att["local_path"])
            if not local_path.exists():
                print(f"  ✗ Attachment file missing: {local_path}")
                continue

            with open(local_path, "rb") as f:
                file_content = f.read()

            print(f"  ✓ Attachment: {att['filename']} ({len(file_content)} bytes)")

            prepared_attachments.append(
                {
                    "filename": att["filename"],
                    "mimeType": att["mimeType"],
                    "data_bytes": file_content,
                }
            )

    if not prepared_attachments:
        print("✗ Failed to prepare attachments")
        return False

    # Build conversation data
    print("\n" + "-" * 70)
    print("Creating conversation in FreeScout...")
    print("-" * 70)

    # Use a valid test email
    test_email = "test-attach-freescout@domegaia.com"

    conv_data = {
        "subject": hs_conv.get("subject", "(No subject)"),
        "mailboxId": 4,
        "type": "email",
        "status": "closed",
        "customer": {"email": test_email},
        "user": 8,
        "createdAt": hs_conv.get("createdAt"),
        "imported": True,
    }

    # Create initial thread with attachments
    first_thread = threads[0]
    initial_thread_data = map_thread_to_freescout(
        first_thread,
        customer_email=test_email,
        attachments_data=prepared_attachments,
    )

    conv_data["threads"] = [initial_thread_data]

    # Add remaining threads without attachments
    for thread in threads[1:]:
        thread_data = map_thread_to_freescout(thread, customer_email=test_email)
        conv_data["threads"].append(thread_data)

    # Check thread attachment structure
    print(f"\nThread 0 attachment structure:")
    if "attachments" in initial_thread_data:
        for att in initial_thread_data["attachments"]:
            # Check for both 'data' (base64) and 'content' (binary) fields
            if "data" in att:
                content_type = type(att.get("data")).__name__
                content_len = len(att["data"]) if att["data"] else 0
            elif "content" in att:
                content_type = type(att.get("content")).__name__
                content_len = len(att["content"]) if isinstance(att["content"], bytes) else "N/A"
            else:
                content_type = "unknown"
                content_len = "N/A"

            print(
                f"  ✓ {att['fileName']}: {content_type} ({content_len} bytes)"
            )
    else:
        print("  ✗ No attachments in thread data")

    # Create conversation
    try:
        fs_conv = fs_client.create_conversation(conv_data)
        fs_conv_id = fs_conv.get("id")
        print(f"\n✓ Conversation created: FS:{fs_conv_id}")
        print(f"  Subject: {fs_conv.get('subject')}")
        print(f"  Status: {fs_conv.get('status')}")

        # Check if attachments are in response
        threads_response = fs_conv.get("_embedded", {}).get("threads", [])
        if threads_response:
            first_thread_response = threads_response[0]
            thread_attachments = first_thread_response.get("attachments", [])
            print(f"  Attachments: {len(thread_attachments)}")
            for att in thread_attachments:
                print(
                    f"    - {att.get('fileName')}: {att.get('mimeType')}"
                )

        print("\n" + "=" * 70)
        print("✓ SUCCESS - Conversation with attachment created")
        print("=" * 70)
        print(f"\nTest ticket: FS:{fs_conv_id}")
        print(f"Try downloading the attachment and verify it opens as a PDF")
        print(f"\nLink: https://helpdesk.domegaia.com/conversation/{fs_conv_id}")

        return True

    except Exception as e:
        print(f"\n✗ Failed to create conversation: {e}")
        # Print more details if it's an API error
        if hasattr(e, 'response'):
            print(f"\nAPI Response: {e.response}")
        return False


if __name__ == "__main__":
    import sys

    success = test_import_with_attachment()
    sys.exit(0 if success else 1)
