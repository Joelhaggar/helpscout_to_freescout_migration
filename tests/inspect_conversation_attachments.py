"""
Inspect a conversation's attachments in Help Scout.
"""
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.helpscout_client import HelpScoutClient


def inspect_attachments(conversation_id: int):
    """Inspect attachments in a conversation."""
    print("=" * 70)
    print(f"INSPECTING CONVERSATION {conversation_id}")
    print("=" * 70)

    try:
        hs_client = HelpScoutClient()

        # Get conversation
        print("\nFetching conversation...")
        conv = hs_client.get_conversation(conversation_id)
        print(f"✓ Subject: {conv.get('subject')}")

        # Get threads
        print("\nFetching threads...")
        threads = hs_client.get_conversation_threads(conversation_id)
        print(f"✓ Found {len(threads)} thread(s)")

        # Check each thread for attachments
        for i, thread in enumerate(threads, 1):
            print(f"\n--- Thread {i} ---")
            print(f"  ID: {thread.get('id')}")
            print(f"  Type: {thread.get('type')}")
            print(f"  Created: {thread.get('createdAt')}")

            # Check for attachments in embedded data
            embedded = thread.get('_embedded', {})
            attachments = embedded.get('attachments', [])

            if attachments:
                print(f"  Attachments: {len(attachments)}")
                for j, att in enumerate(attachments, 1):
                    print(f"\n    Attachment {j}:")
                    print(f"      ID: {att.get('id')}")
                    print(f"      Filename: {att.get('filename')}")
                    print(f"      MIME Type: {att.get('mimeType')}")
                    print(f"      Size: {att.get('size')} bytes")

                    # Print full attachment object
                    print(f"\n      Full object:")
                    print(json.dumps(att, indent=8))
            else:
                print(f"  Attachments: None")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_conversation_attachments.py <conversation_id>")
        sys.exit(1)

    conv_id = int(sys.argv[1])
    sys.exit(0 if inspect_attachments(conv_id) else 1)
