"""
Test adding an attachment via add_thread() method.
"""
import sys
import base64
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient
import time


def test_add_thread_attachment():
    """Test adding a thread with attachment to existing conversation."""
    print("=" * 70)
    print("TEST: Adding Thread with Attachment")
    print("=" * 70)

    try:
        fs_client = FreeScoutClient()

        # Create test PDF
        test_pdf = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
174
%%EOF
"""

        encoded_pdf = base64.b64encode(test_pdf).decode('utf-8')
        print(f"\nTest PDF size: {len(test_pdf)} bytes")
        print(f"Base64 encoded: {len(encoded_pdf)} chars")

        # Get mailbox
        mailboxes = fs_client.get_mailboxes()
        mailbox_id = mailboxes[0]['id']

        # Create test customer
        timestamp = int(time.time())
        customer_email = f"addthread.test.{timestamp}@example.com"

        print(f"\nCreating test customer...")
        customer = fs_client.create_customer({
            "firstName": "AddThread",
            "lastName": "Test",
            "email": customer_email
        })
        customer_id = customer['id']
        print(f"✓ Customer ID: {customer_id}")

        # Create conversation WITHOUT attachment
        print("\nCreating conversation without attachment...")
        conv_data = {
            "subject": "Test: Add Thread Attachment",
            "mailboxId": mailbox_id,
            "type": "email",
            "status": "active",
            "customer": {
                "id": customer_id,
                "email": customer_email,
                "first_name": "AddThread",
                "last_name": "Test"
            },
            "threads": [{
                "type": "customer",
                "text": "Initial message without attachment",
                "customer": {"email": customer_email}
            }]
        }

        conversation = fs_client.create_conversation(conv_data)
        conv_id = conversation['id']
        print(f"✓ Conversation #{conversation.get('number')} created (ID: {conv_id})")

        # Add thread WITH attachment
        print("\nAdding thread with attachment...")
        thread_data = {
            "type": "customer",
            "text": "Reply with PDF attachment",
            "customer": {"email": customer_email},
            "attachments": [
                {
                    "fileName": "addthread_test.pdf",
                    "mimeType": "application/pdf",
                    "data": encoded_pdf
                }
            ]
        }

        print(f"  Attachment data:")
        print(f"    fileName: addthread_test.pdf")
        print(f"    mimeType: application/pdf")
        print(f"    data length: {len(encoded_pdf)} chars")

        thread = fs_client.add_thread(conv_id, thread_data)
        print(f"✓ Thread added (ID: {thread.get('id')})")

        # Retrieve conversation to check attachment
        print("\nRetrieving conversation to verify...")
        conv_full = fs_client.get_conversation(conv_id)
        threads = conv_full.get('_embedded', {}).get('threads', [])

        print(f"✓ Found {len(threads)} threads")

        # Check second thread for attachment
        if len(threads) >= 2:
            second_thread = threads[1]
            attachments = second_thread.get('_embedded', {}).get('attachments', [])

            if attachments:
                print(f"\n✓ Found {len(attachments)} attachment(s) in second thread")
                for att in attachments:
                    print(f"\n  Attachment:")
                    print(f"    ID: {att.get('id')}")
                    print(f"    fileName: {att.get('fileName')}")
                    print(f"    mimeType: {att.get('mimeType')}")
                    print(f"    size: {att.get('size')} bytes")
                    print(f"    fileUrl: {att.get('fileUrl')}")

                    # Check if size matches
                    if att.get('size') == len(test_pdf):
                        print(f"\n  ✓ Size matches original PDF!")
                    else:
                        print(f"\n  ⚠ Size mismatch: expected {len(test_pdf)}, got {att.get('size')}")
                        print(f"     This suggests the file might be incorrectly stored")
            else:
                print("\n✗ No attachments found in second thread!")
        else:
            print(f"\n✗ Expected 2 threads, found {len(threads)}")

        print(f"\n{'=' * 70}")
        print("MANUAL VERIFICATION")
        print("=" * 70)
        print(f"\nConversation #{conversation.get('number')}")
        print(f"Please check:")
        print(f"  1. Open the conversation in FreeScout UI")
        print(f"  2. Check the second thread has the attachment")
        print(f"  3. Try to download and open the PDF")

        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    sys.exit(0 if test_add_thread_attachment() else 1)
