"""
Test timestamp preservation with imported flag.
This test verifies that FreeScout properly preserves historical timestamps
when using the imported=True parameter.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient, FreeScoutAPIError
from datetime import datetime
import time


def test_timestamp_preservation():
    """
    Test creating a conversation with historical timestamps using imported=True.
    """
    print("=" * 70)
    print("TEST: Timestamp Preservation with imported=True")
    print("=" * 70)

    try:
        client = FreeScoutClient()

        # Get mailbox
        mailboxes = client.get_mailboxes()
        if not mailboxes:
            print("✗ No mailboxes found")
            return False

        mailbox_id = mailboxes[0]['id']
        print(f"\n✓ Using mailbox: {mailboxes[0]['name']} (ID: {mailbox_id})")

        # Create test customer
        timestamp = int(time.time())
        customer_email = f"timestamp.test.{timestamp}@example.com"

        print("\nCreating test customer...")
        customer_data = {
            "firstName": "Historical",
            "lastName": "Test",
            "email": customer_email
        }
        customer = client.create_customer(customer_data)
        customer_id = customer['id']
        print(f"✓ Created customer ID: {customer_id}")

        # Create conversation with historical timestamp
        print("\nCreating conversation with historical timestamp...")

        # Conversation from January 15, 2023
        conv_created_at = "2023-01-15T10:30:00Z"

        # Initial thread from same time
        initial_thread_created_at = "2023-01-15T10:30:00Z"

        conversation_data = {
            "subject": "Test: Historical Conversation from Jan 2023",
            "mailboxId": mailbox_id,
            "type": "email",
            "status": "closed",
            "createdAt": conv_created_at,  # Set historical timestamp
            "closedAt": "2023-01-16T15:00:00Z",  # Closed next day
            "customer": {
                "id": customer_id,
                "email": customer_email,
                "first_name": "Historical",
                "last_name": "Test"
            },
            "threads": [{
                "type": "customer",
                "text": "Hello, I need help with my account.",
                "createdAt": initial_thread_created_at,  # Historical timestamp
                "customer": {"email": customer_email}
            }]
        }

        print(f"  Conversation timestamp: {conv_created_at}")
        print(f"  Initial thread timestamp: {initial_thread_created_at}")
        print(f"  imported=True (prevents notifications)")

        created_conv = client.create_conversation(conversation_data, imported=True)
        conversation_id = created_conv['id']

        print(f"\n✓ Created conversation ID: {conversation_id}")
        print(f"  Returned createdAt: {created_conv.get('createdAt')}")

        # Add more threads with historical timestamps
        print("\nAdding agent reply thread (Jan 15, 2023 14:20)...")
        thread_2_data = {
            "type": "message",
            "text": "Hi! I'd be happy to help you.",
            "createdAt": "2023-01-15T14:20:00Z",
            "user": 8  # Joel
        }
        thread_2 = client.add_thread(conversation_id, thread_2_data, imported=True)
        print(f"✓ Thread added - Returned createdAt: {thread_2.get('createdAt')}")

        # Customer reply next day
        print("\nAdding customer reply (Jan 16, 2023 09:15)...")
        thread_3_data = {
            "type": "customer",
            "text": "It says 'Invalid password' but I'm sure it's correct.",
            "createdAt": "2023-01-16T09:15:00Z",
            "customer": {"email": customer_email}
        }
        thread_3 = client.add_thread(conversation_id, thread_3_data, imported=True)
        print(f"✓ Thread added - Returned createdAt: {thread_3.get('createdAt')}")

        # Agent solution
        print("\nAdding agent solution (Jan 16, 2023 11:45)...")
        thread_4_data = {
            "type": "message",
            "text": "I've reset your password. Check your email.",
            "createdAt": "2023-01-16T11:45:00Z",
            "user": 8  # Joel
        }
        thread_4 = client.add_thread(conversation_id, thread_4_data, imported=True)
        print(f"✓ Thread added - Returned createdAt: {thread_4.get('createdAt')}")

        # Internal note
        print("\nAdding internal note (Jan 16, 2023 11:50)...")
        note_data = {
            "type": "note",
            "text": "Account was locked due to failed login attempts.",
            "createdAt": "2023-01-16T11:50:00Z",
            "user": 8  # Joel
        }
        note = client.add_thread(conversation_id, note_data, imported=True)
        print(f"✓ Note added - Returned createdAt: {note.get('createdAt')}")

        # Retrieve conversation to verify
        print("\n" + "=" * 70)
        print("VERIFICATION: Checking timestamps in database")
        print("=" * 70)

        conversation = client.get_conversation(conversation_id)

        print(f"\nConversation #{conversation.get('number')}")
        print(f"Subject: {conversation.get('subject')}")
        print(f"Status: {conversation.get('status')}")
        print(f"Created At: {conversation.get('createdAt')}")
        print(f"Closed At: {conversation.get('closedAt')}")

        # Verify timestamps
        expected_created_at = "2023-01-15T10:30:00Z"
        actual_created_at = conversation.get('createdAt')

        print("\n" + "=" * 70)
        print("TIMESTAMP VERIFICATION")
        print("=" * 70)

        if actual_created_at == expected_created_at:
            print(f"\n✓ SUCCESS: Conversation timestamp preserved!")
            print(f"  Expected: {expected_created_at}")
            print(f"  Actual:   {actual_created_at}")
        else:
            print(f"\n✗ FAILED: Timestamp not preserved")
            print(f"  Expected: {expected_created_at}")
            print(f"  Actual:   {actual_created_at}")
            return False

        # Check thread timestamps
        print(f"\n{'=' * 70}")
        print("MANUAL VERIFICATION REQUIRED")
        print("=" * 70)
        print(f"\nConversation ID: {conversation_id}")
        print(f"Conversation Number: #{conversation.get('number')}")
        print(f"\nPlease verify in FreeScout UI:")
        print(f"1. Navigate to conversation #{conversation.get('number')}")
        print(f"2. Check that conversation created date shows: Jan 15, 2023 10:30 AM")
        print(f"3. Check that threads show dates from Jan 15-16, 2023")
        print(f"4. Verify timeline is in correct chronological order")
        print(f"\nExpected thread timestamps:")
        print(f"  - Thread 1: Jan 15, 2023 10:30 AM (initial customer message)")
        print(f"  - Thread 2: Jan 15, 2023 02:20 PM (agent reply)")
        print(f"  - Thread 3: Jan 16, 2023 09:15 AM (customer reply)")
        print(f"  - Thread 4: Jan 16, 2023 11:45 AM (agent solution)")
        print(f"  - Note:     Jan 16, 2023 11:50 AM (internal note)")

        return True

    except FreeScoutAPIError as e:
        print(f"\n✗ API Error: {e}")
        if e.status_code:
            print(f"  Status Code: {e.status_code}")
        if e.response:
            print(f"  Response: {e.response}")
        return False

    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the timestamp preservation test."""
    print("\n" + "=" * 70)
    print("FREESCOUT TIMESTAMP PRESERVATION TEST")
    print("=" * 70)
    print("\nThis test verifies that FreeScout preserves historical timestamps")
    print("when using the imported=True parameter for migrations.")
    print("=" * 70)

    result = test_timestamp_preservation()

    if result:
        print("\n" + "=" * 70)
        print("✓ TIMESTAMP PRESERVATION TEST PASSED!")
        print("=" * 70)
        print("\nThe API successfully accepted historical timestamps.")
        print("Manual verification in UI recommended to confirm display.")
        return 0
    else:
        print("\n" + "=" * 70)
        print("✗ TIMESTAMP PRESERVATION TEST FAILED")
        print("=" * 70)
        print("\nTimestamps were not preserved. Migration may lose date information.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
