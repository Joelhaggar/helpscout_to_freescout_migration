"""
Test timestamp preservation workaround.
Creates a conversation with multiple threads showing different historical dates.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient, FreeScoutAPIError
from datetime import datetime
import time


def format_timestamp_for_display(iso_timestamp):
    """Convert ISO timestamp to human-readable format."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime("%B %d, %Y at %I:%M %p UTC")
    except:
        return iso_timestamp


def test_timestamp_workaround():
    """
    Create a conversation with threads from different dates to verify
    the timestamp workaround displays correctly.
    """
    print("=" * 70)
    print("TEST: Timestamp Workaround for Historical Conversations")
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
            "lastName": "Conversation Test",
            "email": customer_email
        }
        customer = client.create_customer(customer_data)
        customer_id = customer['id']
        print(f"✓ Created customer ID: {customer_id}")

        # Simulate a conversation from 2023 with multiple threads
        print("\nCreating conversation with historical timestamps...")

        # Thread 1: Initial customer message from January 2023
        original_timestamp_1 = "2023-01-15T10:30:00Z"
        thread_1_text = f"[Originally sent: {format_timestamp_for_display(original_timestamp_1)}]\n\nHello, I need help with my account. I can't log in."

        conversation_data = {
            "subject": "Historical Test: Account Login Issue (Jan 2023)",
            "mailboxId": mailbox_id,
            "type": "email",
            "status": "closed",  # Old conversation, now closed
            "customer": {
                "id": customer_id,
                "email": customer_email,
                "first_name": "Historical",
                "last_name": "Conversation Test"
            },
            "threads": [{
                "type": "customer",
                "text": thread_1_text,
                "customer": {"email": customer_email}
            }]
        }

        created_conv = client.create_conversation(conversation_data)
        conversation_id = created_conv['id']
        print(f"✓ Created conversation ID: {conversation_id}")

        # Thread 2: Agent reply from January 2023 (same day)
        original_timestamp_2 = "2023-01-15T14:20:00Z"
        thread_2_text = f"[Originally sent: {format_timestamp_for_display(original_timestamp_2)}]\n\nHi there! I'd be happy to help. Can you tell me what error message you're seeing?"

        print(f"\nAdding agent reply thread (from {format_timestamp_for_display(original_timestamp_2)})...")
        client.add_thread(conversation_id, {
            "type": "message",
            "text": thread_2_text,
            "user": 8  # Joel
        })
        print("✓ Thread added")

        # Thread 3: Customer reply from January 2023 (next day)
        original_timestamp_3 = "2023-01-16T09:15:00Z"
        thread_3_text = f"[Originally sent: {format_timestamp_for_display(original_timestamp_3)}]\n\nIt says 'Invalid password' but I'm sure my password is correct."

        print(f"\nAdding customer reply (from {format_timestamp_for_display(original_timestamp_3)})...")
        client.add_thread(conversation_id, {
            "type": "customer",
            "text": thread_3_text,
            "customer": {"email": customer_email}
        })
        print("✓ Thread added")

        # Thread 4: Agent solution from January 2023
        original_timestamp_4 = "2023-01-16T11:45:00Z"
        thread_4_text = f"[Originally sent: {format_timestamp_for_display(original_timestamp_4)}]\n\nI've reset your password. Please check your email for a reset link. You should be able to log in within 5 minutes."

        print(f"\nAdding agent solution (from {format_timestamp_for_display(original_timestamp_4)})...")
        client.add_thread(conversation_id, {
            "type": "message",
            "text": thread_4_text,
            "user": 8  # Joel
        })
        print("✓ Thread added")

        # Thread 5: Customer confirmation from January 2023
        original_timestamp_5 = "2023-01-16T12:10:00Z"
        thread_5_text = f"[Originally sent: {format_timestamp_for_display(original_timestamp_5)}]\n\nThat worked! I'm able to log in now. Thank you so much!"

        print(f"\nAdding customer confirmation (from {format_timestamp_for_display(original_timestamp_5)})...")
        client.add_thread(conversation_id, {
            "type": "customer",
            "text": thread_5_text,
            "customer": {"email": customer_email}
        })
        print("✓ Thread added")

        # Add an internal note
        original_timestamp_6 = "2023-01-16T12:15:00Z"
        note_text = f"[Originally sent: {format_timestamp_for_display(original_timestamp_6)}]\n\nInternal note: Customer's account had been locked due to multiple failed login attempts. Reset resolved the issue."

        print(f"\nAdding internal note (from {format_timestamp_for_display(original_timestamp_6)})...")
        client.add_thread(conversation_id, {
            "type": "note",
            "text": note_text,
            "user": 8  # Joel
        })
        print("✓ Note added")

        # Retrieve and display the conversation
        print("\n" + "=" * 70)
        print("VERIFICATION: Retrieving conversation to check display")
        print("=" * 70)

        conversation = client.get_conversation(conversation_id)

        print(f"\nConversation #{conversation.get('number')} - {conversation.get('subject')}")
        print(f"Status: {conversation.get('status')}")
        print(f"Created: {conversation.get('createdAt')}")
        print("\nThreads (showing text preview):")
        print("-" * 70)

        # Note: The API may not return threads in get_conversation
        # Check if threads are included
        threads = conversation.get('threads', [])
        if threads:
            for i, thread in enumerate(threads, 1):
                thread_type = thread.get('type', 'unknown')
                text = thread.get('body', thread.get('text', ''))[:100]
                created = thread.get('createdAt', 'N/A')
                print(f"\n[{i}] Type: {thread_type}")
                print(f"    FreeScout timestamp: {created}")
                print(f"    Text preview: {text}...")
        else:
            print("⚠ Threads not included in conversation response")
            print("  (This is OK - they exist but API may not return them here)")

        # Summary
        print("\n" + "=" * 70)
        print("TEST RESULTS")
        print("=" * 70)
        print(f"\n✓ Successfully created conversation with 6 threads")
        print(f"✓ Each thread has original timestamp prepended to text")
        print(f"✓ Timeline preserved: Jan 15-16, 2023")
        print(f"\nConversation ID: {conversation_id}")
        print(f"Conversation Number: #{conversation.get('number')}")
        print(f"\n{'=' * 70}")
        print("MANUAL VERIFICATION REQUIRED")
        print("=" * 70)
        print(f"\n1. Open FreeScout in your browser")
        print(f"2. Navigate to conversation #{conversation.get('number')}")
        print(f"3. Verify that each thread shows:")
        print(f"   - '[Originally sent: Month DD, YYYY at HH:MM AM/PM UTC]' prefix")
        print(f"   - Thread content is readable and properly formatted")
        print(f"   - Timeline makes sense even though FreeScout timestamps are today")
        print(f"\n4. Check if the format is acceptable for your needs")
        print(f"\nℹ If format needs adjustment, we can modify the timestamp prefix format.")

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
    """Run the timestamp workaround test."""
    print("\n" + "=" * 70)
    print("TIMESTAMP PRESERVATION WORKAROUND TEST")
    print("=" * 70)
    print("\nThis test creates a realistic conversation with threads from 2023")
    print("to verify the timestamp workaround displays correctly.")
    print("=" * 70)

    result = test_timestamp_workaround()

    if result:
        print("\n✓ Test completed successfully!")
        print("\nNext step: Manually verify in FreeScout UI")
        return 0
    else:
        print("\n✗ Test failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
