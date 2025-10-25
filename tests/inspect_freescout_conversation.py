"""
Inspect a FreeScout conversation and its attachments.
"""
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient


def inspect_conversation(conversation_id: int):
    """Inspect a conversation in FreeScout."""
    print("=" * 70)
    print(f"INSPECTING FREESCOUT CONVERSATION {conversation_id}")
    print("=" * 70)

    try:
        fs_client = FreeScoutClient()

        # Get conversation
        print("\nFetching conversation...")
        conv = fs_client.get_conversation(conversation_id)

        print(f"\nConversation #{conv.get('number')}")
        print(f"  Subject: {conv.get('subject')}")
        print(f"  Status: {conv.get('status')}")
        print(f"  Type: {conv.get('type')}")
        print(f"  Created: {conv.get('createdAt')}")

        # Get threads
        threads = conv.get('_embedded', {}).get('threads', [])
        print(f"\n✓ Found {len(threads)} thread(s)")

        # Check each thread for attachments
        for i, thread in enumerate(threads, 1):
            print(f"\n--- Thread {i} ---")
            print(f"  ID: {thread.get('id')}")
            print(f"  Type: {thread.get('type')}")
            print(f"  Created: {thread.get('createdAt')}")
            print(f"  Created By:")
            print(f"    Type: {thread.get('createdBy', {}).get('type')}")
            print(f"    Email: {thread.get('createdBy', {}).get('email')}")

            # Check for attachments in embedded data
            embedded = thread.get('_embedded', {})
            attachments = embedded.get('attachments', [])

            if attachments:
                print(f"  Attachments: {len(attachments)}")
                for j, att in enumerate(attachments, 1):
                    print(f"\n    Attachment {j}:")
                    print(f"      ID: {att.get('id')}")
                    print(f"      Filename: {att.get('fileName')}")
                    print(f"      MIME Type: {att.get('mimeType')}")
                    print(f"      Size: {att.get('size')} bytes")
                    print(f"      File URL: {att.get('fileUrl')}")

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
        print("Usage: python inspect_freescout_conversation.py <conversation_id>")
        print("Example: python inspect_freescout_conversation.py 40")
        sys.exit(1)

    conv_id = int(sys.argv[1])
    sys.exit(0 if inspect_conversation(conv_id) else 1)
