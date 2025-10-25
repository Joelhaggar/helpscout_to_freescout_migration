"""
Test FreeScout conversation creation with threads.
Tests the conversation and thread API endpoints.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient, FreeScoutAPIError
import time


def test_create_conversation_with_threads():
    """Test creating a conversation with initial threads."""
    print("=" * 60)
    print("TEST: Create Conversation with Threads")
    print("=" * 60)

    try:
        client = FreeScoutClient()

        # First, get a mailbox ID
        print("\nFetching mailboxes...")
        mailboxes = client.get_mailboxes()
        if not mailboxes:
            print("✗ No mailboxes found. Cannot create conversation.")
            return None

        mailbox_id = mailboxes[0]['id']
        print(f"✓ Using mailbox: {mailboxes[0]['name']} (ID: {mailbox_id})")

        # Create or use existing customer
        timestamp = int(time.time())
        customer_email = f"test.customer.{timestamp}@example.com"

        # Try to find or create customer
        print("\nChecking for existing test customer...")
        existing_customer = client.search_customer_by_email(customer_email)

        if existing_customer:
            customer_id = existing_customer['id']
            print(f"✓ Using existing customer ID: {customer_id}")
        else:
            print("Creating new test customer...")
            customer_data = {
                "firstName": "Test",
                "lastName": "Conversation Customer",
                "email": customer_email
            }
            new_customer = client.create_customer(customer_data)
            customer_id = new_customer['id']
            print(f"✓ Created customer ID: {customer_id}")

        # Create conversation data with threads
        conversation_data = {
            "subject": f"Test Migration Conversation {timestamp}",
            "mailboxId": mailbox_id,
            "type": "email",
            "status": "active",
            "customer": {
                "id": customer_id,
                "email": customer_email,
                "first_name": "Test",
                "last_name": "Conversation Customer"
            },
            "threads": [
                {
                    "type": "customer",
                    "text": "This is a test message from a customer during migration testing.",
                    "createdBy": {
                        "type": "customer",
                        "email": customer_email
                    }
                }
            ]
        }

        print("\nCreating conversation:")
        print(f"  Subject: {conversation_data['subject']}")
        print(f"  Mailbox ID: {conversation_data['mailboxId']}")
        print(f"  Type: {conversation_data['type']}")
        print(f"  Status: {conversation_data['status']}")
        print(f"  Initial threads: {len(conversation_data['threads'])}")

        print("\nSending request to FreeScout...")
        created_conversation = client.create_conversation(conversation_data)

        print(f"\n✓ Conversation created successfully!")
        print(f"  Conversation ID: {created_conversation.get('id')}")
        print(f"  Number: {created_conversation.get('number')}")
        print(f"  Subject: {created_conversation.get('subject')}")
        print(f"  Status: {created_conversation.get('status')}")

        return created_conversation.get('id')

    except FreeScoutAPIError as e:
        print(f"\n✗ API Error: {e}")
        if e.status_code:
            print(f"  Status Code: {e.status_code}")
        if e.response:
            print(f"  Response: {e.response}")
        return None

    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_add_thread(conversation_id):
    """Test adding additional threads to a conversation."""
    print("\n" + "=" * 60)
    print("TEST: Add Thread to Conversation")
    print("=" * 60)

    if not conversation_id:
        print("✗ No conversation ID provided")
        return False

    try:
        client = FreeScoutClient()

        # Add an agent reply thread
        thread_data = {
            "type": "message",  # Agent reply
            "text": "Thank you for contacting us. This is an automated test response.",
            "user": 8  # Joel's user ID
        }

        print(f"\nAdding thread to conversation ID: {conversation_id}")
        print(f"  Type: {thread_data['type']}")
        print(f"  Text: {thread_data['text'][:50]}...")

        print("\nSending request...")
        created_thread = client.add_thread(conversation_id, thread_data)

        print(f"\n✓ Thread added successfully!")
        print(f"  Thread ID: {created_thread.get('id')}")

        # Add a note thread
        note_data = {
            "type": "note",
            "text": "Internal note: This is a test conversation from the migration tool.",
            "user": 8  # Joel's user ID
        }

        print(f"\nAdding note thread...")
        created_note = client.add_thread(conversation_id, note_data)
        print(f"✓ Note added successfully!")

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
        return False


def test_update_tags(conversation_id):
    """Test updating conversation tags."""
    print("\n" + "=" * 60)
    print("TEST: Update Conversation Tags")
    print("=" * 60)

    if not conversation_id:
        print("✗ No conversation ID provided")
        return False

    try:
        client = FreeScoutClient()

        tags = ["test-migration", "automated-test"]

        print(f"\nUpdating tags for conversation ID: {conversation_id}")
        print(f"  Tags: {', '.join(tags)}")

        client.update_conversation_tags(conversation_id, tags)

        print(f"\n✓ Tags updated successfully!")

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
        return False


def test_get_conversation(conversation_id):
    """Test retrieving a conversation with all its data."""
    print("\n" + "=" * 60)
    print("TEST: Retrieve Conversation")
    print("=" * 60)

    if not conversation_id:
        print("✗ No conversation ID provided")
        return False

    try:
        client = FreeScoutClient()

        print(f"\nFetching conversation ID: {conversation_id}")
        conversation = client.get_conversation(conversation_id)

        print(f"\n✓ Conversation retrieved successfully!")
        print(f"  ID: {conversation.get('id')}")
        print(f"  Number: {conversation.get('number')}")
        print(f"  Subject: {conversation.get('subject')}")
        print(f"  Status: {conversation.get('status')}")
        print(f"  Type: {conversation.get('type')}")

        # Show threads count if available
        threads = conversation.get('threads', [])
        if threads:
            print(f"  Threads: {len(threads)}")

        # Show tags if available
        tags = conversation.get('tags', [])
        if tags:
            print(f"  Tags: {', '.join(tags)}")

        return True

    except FreeScoutAPIError as e:
        print(f"\n✗ API Error: {e}")
        return False

    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        return False


def test_timestamp_preservation(conversation_id):
    """Test if FreeScout accepts custom timestamps in threads."""
    print("\n" + "=" * 60)
    print("TEST: Custom Timestamp Preservation")
    print("=" * 60)

    if not conversation_id:
        print("✗ No conversation ID provided")
        return False

    try:
        client = FreeScoutClient()

        # Try to create a thread with a custom timestamp
        custom_timestamp = "2023-01-15T10:30:00Z"
        thread_data = {
            "type": "customer",
            "text": f"[Originally sent: {custom_timestamp}] This is a test message with custom timestamp.",
            "customer": {
                "email": "timestamp.test@example.com"
            }
        }

        print(f"\nAttempting to create thread with custom timestamp:")
        print(f"  Timestamp: {custom_timestamp}")

        created_thread = client.add_thread(conversation_id, thread_data)

        # Check if timestamp was preserved
        returned_timestamp = created_thread.get('createdAt')
        print(f"\n✓ Thread created")
        print(f"  Returned timestamp: {returned_timestamp}")

        if returned_timestamp == custom_timestamp:
            print(f"  ✓ Custom timestamp preserved!")
            return True
        else:
            print(f"  ✗ Custom timestamp NOT preserved (used server time)")
            print(f"  ℹ Recommendation: Prepend timestamp to thread text")
            return False

    except FreeScoutAPIError as e:
        print(f"\n✗ API Error: {e}")
        if e.status_code:
            print(f"  Status Code: {e.status_code}")
        return False

    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        return False


def main():
    """Run all conversation tests."""
    print("\n" + "=" * 60)
    print("FREESCOUT CONVERSATION API TESTS")
    print("=" * 60)

    results = []
    conversation_id = None

    # Test 1: Create Conversation
    print("\n[1/5] Creating conversation with initial thread...")
    conversation_id = test_create_conversation_with_threads()
    results.append(("Create Conversation", conversation_id is not None))

    # Test 2: Add Threads
    print("\n[2/5] Adding additional threads...")
    result = test_add_thread(conversation_id)
    results.append(("Add Threads", result))

    # Test 3: Update Tags
    print("\n[3/5] Updating tags...")
    result = test_update_tags(conversation_id)
    results.append(("Update Tags", result))

    # Test 4: Get Conversation
    print("\n[4/5] Retrieving conversation...")
    result = test_get_conversation(conversation_id)
    results.append(("Get Conversation", result))

    # Test 5: Timestamp Preservation
    print("\n[5/5] Testing timestamp preservation...")
    result = test_timestamp_preservation(conversation_id)
    results.append(("Timestamp Preservation", result))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if conversation_id:
        print(f"\nℹ Test conversation ID: {conversation_id}")
        print("  (You may want to delete this test conversation manually)")

    if passed == total:
        print("\n✓ All conversation tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
