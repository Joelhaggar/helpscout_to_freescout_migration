"""
Debug attachment upload to FreeScout.
Test different formats to see what works.
"""
import sys
import base64
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient
import json


def test_attachment_formats():
    """Test different attachment formats in FreeScout."""
    print("=" * 70)
    print("ATTACHMENT FORMAT DEBUG TEST")
    print("=" * 70)

    try:
        # Initialize clients
        hs_client = HelpScoutClient()
        fs_client = FreeScoutClient()

        # Create a small test PDF file content
        # This is a minimal valid PDF file
        test_pdf_content = b"""%PDF-1.4
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
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000214 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
297
%%EOF
"""

        print("\nCreated test PDF content...")
        att_bytes = test_pdf_content
        print(f"✓ Test PDF: {len(att_bytes)} bytes")

        # Verify it's a PDF
        if att_bytes[:4] == b'%PDF':
            print("✓ Confirmed valid PDF file")
        else:
            print(f"⚠ Warning: File doesn't start with PDF header")
            print(f"  First 20 bytes: {att_bytes[:20]}")

        # Base64 encode
        encoded_data = base64.b64encode(att_bytes).decode('utf-8')
        print(f"✓ Base64 encoded: {len(encoded_data)} characters")
        print(f"  First 50 chars: {encoded_data[:50]}...")

        # Get test mailbox
        mailboxes = fs_client.get_mailboxes()
        mailbox_id = mailboxes[0]['id']

        # Create test customer
        import time
        timestamp = int(time.time())
        customer_email = f"attachment.test.{timestamp}@example.com"

        print(f"\nCreating test customer...")
        customer_data = {
            "firstName": "Attachment",
            "lastName": "Test",
            "email": customer_email
        }
        customer = fs_client.create_customer(customer_data)
        customer_id = customer['id']
        print(f"✓ Created customer ID: {customer_id}")

        # Create conversation with attachment in initial thread
        print("\nCreating conversation with attachment...")

        # Print the exact payload we're sending
        thread_with_attachment = {
            "type": "customer",
            "text": "Test message with PDF attachment",
            "customer": {"email": customer_email},
            "attachments": [
                {
                    "fileName": "test_invoice.pdf",
                    "mimeType": "application/pdf",
                    "data": encoded_data
                }
            ]
        }

        conversation_data = {
            "subject": "Attachment Format Test",
            "mailboxId": mailbox_id,
            "type": "email",
            "status": "active",
            "customer": {
                "id": customer_id,
                "email": customer_email,
                "first_name": "Attachment",
                "last_name": "Test"
            },
            "threads": [thread_with_attachment]
        }

        print("\nThread attachment data:")
        print(f"  fileName: test_invoice.pdf")
        print(f"  mimeType: application/pdf")
        print(f"  data length: {len(encoded_data)} chars")
        print(f"  data sample: {encoded_data[:80]}...")

        print("\nSending to FreeScout...")
        conversation = fs_client.create_conversation(conversation_data)
        conv_id = conversation['id']

        print(f"\n✓ Conversation created: #{conversation.get('number')} (ID: {conv_id})")

        # Retrieve conversation to check attachment
        print("\nRetrieving conversation to verify attachment...")
        conv_full = fs_client.get_conversation(conv_id)
        threads = conv_full.get('_embedded', {}).get('threads', [])

        if threads:
            first_thread = threads[0]
            attachments = first_thread.get('_embedded', {}).get('attachments', [])

            if attachments:
                print(f"✓ Found {len(attachments)} attachment(s)")
                for att in attachments:
                    print(f"\n  Attachment details:")
                    print(f"    ID: {att.get('id')}")
                    print(f"    fileName: {att.get('fileName')}")
                    print(f"    mimeType: {att.get('mimeType')}")
                    print(f"    size: {att.get('size')} bytes")

                    # Get the full attachment object
                    print(f"\n  Full attachment object:")
                    print(json.dumps(att, indent=4))
            else:
                print("✗ No attachments found in thread!")
                print(f"\n  Thread data:")
                print(json.dumps(first_thread, indent=4))
        else:
            print("✗ No threads found!")

        print(f"\n{'=' * 70}")
        print("MANUAL VERIFICATION")
        print("=" * 70)
        print(f"\nConversation #{conversation.get('number')}")
        print(f"Please check in FreeScout UI:")
        print(f"  1. Does the attachment show correctly?")
        print(f"  2. Can you download it as a PDF?")
        print(f"  3. Does the downloaded file open correctly?")

        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    sys.exit(0 if test_attachment_formats() else 1)
