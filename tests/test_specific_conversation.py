"""
Migrate a specific conversation by ID from Help Scout to FreeScout.
Useful for testing and verifying specific conversations.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.helpscout_client import HelpScoutClient, HelpScoutAPIError
from api.freescout_client import FreeScoutClient, FreeScoutAPIError
from mapping.mappers import (
    map_customer_to_freescout,
    map_conversation_to_freescout,
    map_thread_to_freescout,
    extract_tags
)
from utils.filters import (
    reorder_threads_for_attachments,
    count_threads_with_attachments
)
import json


def migrate_specific_conversation(conversation_id: int):
    """
    Migrate a specific conversation by Help Scout ID.

    Args:
        conversation_id: Help Scout conversation ID
    """
    print("=" * 70)
    print(f"MIGRATING SPECIFIC CONVERSATION: {conversation_id}")
    print("=" * 70)

    try:
        # Initialize clients
        print("\nInitializing API clients...")
        hs_client = HelpScoutClient()
        fs_client = FreeScoutClient()
        print("✓ Clients initialized")

        # Fetch conversation from Help Scout
        print(f"\n{'=' * 70}")
        print("STEP 1: Fetching conversation from Help Scout")
        print("=" * 70)

        print(f"\nFetching conversation {conversation_id}...")
        hs_conv = hs_client.get_conversation(conversation_id)

        print(f"\n✓ Retrieved conversation:")
        print(f"  ID: {hs_conv.get('id')}")
        print(f"  Number: #{hs_conv.get('number')}")
        print(f"  Subject: {hs_conv.get('subject')}")
        print(f"  Status: {hs_conv.get('status')}")
        print(f"  Type: {hs_conv.get('type')}")
        print(f"  Created: {hs_conv.get('createdAt')}")
        print(f"  Mailbox ID: {hs_conv.get('mailboxId')}")

        # Check for spam
        tags = extract_tags(hs_conv)
        if 'spam' in [t.lower() for t in tags]:
            print(f"\n⚠️  WARNING: This conversation is tagged as spam!")
            print(f"  Tags: {', '.join(tags)}")
            response = input("\n  Continue anyway? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("\n✗ Migration cancelled by user")
                return False

        if tags:
            print(f"  Tags: {', '.join(tags)}")

        # Get customer
        print(f"\n{'=' * 70}")
        print("STEP 2: Fetching customer from Help Scout")
        print("=" * 70)

        customer_ref = hs_conv.get('primaryCustomer', hs_conv.get('customer'))
        if not customer_ref:
            print("✗ No customer found in conversation")
            return False

        customer_id = customer_ref.get('id')
        print(f"\nFetching customer {customer_id}...")
        hs_customer = hs_client.get_customer(customer_id)

        print(f"\n✓ Retrieved customer:")
        print(f"  ID: {hs_customer.get('id')}")
        print(f"  Name: {hs_customer.get('firstName')} {hs_customer.get('lastName')}")
        emails = hs_customer.get('emails', [])
        if emails:
            email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')
            print(f"  Email: {email}")

        # Get threads first to extract email if needed
        print(f"\n{'=' * 70}")
        print("STEP 3: Fetching threads to extract customer email")
        print("=" * 70)

        print(f"\nFetching threads...")
        hs_threads = hs_client.get_conversation_threads(conversation_id)
        print(f"✓ Retrieved {len(hs_threads)} thread(s)")

        # Check for attachments and reorder if needed
        attachment_count = count_threads_with_attachments(hs_threads)
        if attachment_count > 0:
            print(f"\n⚠️  ATTACHMENT HANDLING")
            print(f"  Found {attachment_count} thread(s) with attachments")

            if attachment_count > 1:
                print(f"  ⚠ WARNING: Multiple threads have attachments!")
                print(f"    Due to FreeScout API limitations, only attachments from")
                print(f"    the FIRST thread will be preserved correctly.")

            hs_threads, was_reordered = reorder_threads_for_attachments(hs_threads)
            if was_reordered:
                print(f"  ✓ Reordered threads to move attachment thread to position #1")
                print(f"    (This ensures attachments migrate correctly)")

        # Extract customer email from threads if not in customer record
        customer_email = None
        emails = hs_customer.get('emails', [])
        if emails:
            customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')
        else:
            # Try to find email in customer threads
            print("No email in customer record, checking threads...")
            for thread in hs_threads:
                if thread.get('type') == 'customer':
                    created_by = thread.get('createdBy', {})
                    if created_by.get('email'):
                        customer_email = created_by['email']
                        print(f"✓ Found customer email in thread: {customer_email}")
                        break

        if not customer_email:
            # Still no email, generate placeholder
            customer_email = f"helpscout.customer.{hs_customer.get('id')}@migration.local"
            print(f"⚠ No email found, using placeholder: {customer_email}")

        # Create/find customer in FreeScout
        print(f"\n{'=' * 70}")
        print("STEP 4: Creating/finding customer in FreeScout")
        print("=" * 70)

        print("\nMapping customer data...")
        fs_customer_data = map_customer_to_freescout(hs_customer)
        fs_customer_data['email'] = customer_email  # Override with extracted email

        # Check if customer exists
        print(f"\nSearching for existing customer with email: {customer_email}")
        existing_customer = fs_client.search_customer_by_email(customer_email)
        if existing_customer:
            fs_customer_id = existing_customer['id']
            print(f"✓ Found existing customer ID: {fs_customer_id}")
        else:
            print("Customer not found, creating new...")
            fs_customer = fs_client.create_customer(fs_customer_data)
            fs_customer_id = fs_customer['id']
            print(f"✓ Created customer ID: {fs_customer_id}")

        # Get full customer data
        fs_customer_full = fs_client.get_customer(fs_customer_id)

        # Prepare customer data for conversation
        customer_for_conversation = {
            "id": fs_customer_id,
            "email": customer_email,
            "first_name": fs_customer_data.get('firstName'),
            "last_name": fs_customer_data.get('lastName')
        }

        # Display thread details
        print(f"\n{'=' * 70}")
        print("STEP 5: Thread Details")
        print("=" * 70)

        if not hs_threads:
            print("⚠ No threads found")
            return False

        print(f"\nDisplaying {len(hs_threads)} threads:")
        for i, thread in enumerate(hs_threads, 1):
            print(f"\n  Thread {i}:")
            print(f"    Type: {thread.get('type')}")
            print(f"    Created: {thread.get('createdAt')}")
            print(f"    Created By: {thread.get('createdBy', {}).get('type')}")
            body_preview = thread.get('body', '')[:100].replace('\n', ' ')
            print(f"    Body: {body_preview}...")

        # Create conversation in FreeScout
        print(f"\n{'=' * 70}")
        print("STEP 5: Creating conversation in FreeScout")
        print("=" * 70)

        # Map first thread with attachments if present
        print(f"\nMapping initial thread...")

        # Check for attachments in first thread
        first_thread_attachments = hs_threads[0].get('_embedded', {}).get('attachments', [])
        attachments_data = None

        if first_thread_attachments:
            print(f"  Downloading {len(first_thread_attachments)} attachment(s)...")
            attachments_data = []
            for att in first_thread_attachments:
                att_id = att.get('id')
                filename = att.get('filename')
                mime_type = att.get('mimeType')
                size = att.get('size', 0)

                print(f"    Downloading: {filename} ({size} bytes)")
                try:
                    att_bytes = hs_client.download_attachment(conversation_id, att_id)
                    attachments_data.append({
                        'filename': filename,
                        'mimeType': mime_type,
                        'data_bytes': att_bytes
                    })
                    print(f"    ✓ Downloaded {len(att_bytes)} bytes")
                except Exception as e:
                    print(f"    ✗ Failed to download: {e}")

        fs_first_thread = map_thread_to_freescout(
            hs_threads[0],
            customer_email=customer_email,
            attachments_data=attachments_data if attachments_data else None
        )

        # Map conversation
        print(f"Mapping conversation...")
        fs_conversation_data = map_conversation_to_freescout(
            hs_conv,
            customer_for_conversation,
            fs_first_thread
        )

        print(f"\nCreating conversation in FreeScout...")
        print(f"  Subject: {fs_conversation_data['subject']}")
        print(f"  Status: {fs_conversation_data['status']}")
        print(f"  Type: {fs_conversation_data['type']}")
        print(f"  Created: {fs_conversation_data['createdAt']}")
        print(f"  Mailbox: {fs_conversation_data['mailboxId']}")

        fs_conversation = fs_client.create_conversation(
            fs_conversation_data,
            imported=True
        )
        fs_conv_id = fs_conversation['id']

        print(f"\n✓ Conversation created!")
        print(f"  FreeScout ID: {fs_conv_id}")
        print(f"  Number: #{fs_conversation.get('number')}")

        # Add remaining threads
        if len(hs_threads) > 1:
            print(f"\n{'=' * 70}")
            print(f"STEP 6: Adding {len(hs_threads) - 1} additional threads")
            print("=" * 70)

            for i, hs_thread in enumerate(hs_threads[1:], 2):
                print(f"\n  Adding thread {i}/{len(hs_threads)}...")
                print(f"    Type: {hs_thread.get('type')}")
                print(f"    Created: {hs_thread.get('createdAt')}")

                # Check for attachments (warn if found since they won't migrate)
                attachments = hs_thread.get('_embedded', {}).get('attachments', [])
                if attachments:
                    print(f"    ⚠️  WARNING: Thread has {len(attachments)} attachment(s)")
                    print(f"       These attachments will NOT be migrated due to FreeScout API limitation")
                    print(f"       Attachments should have been reordered to the first thread")

                # Map thread WITHOUT attachments (they don't work in add_thread anyway)
                fs_thread = map_thread_to_freescout(
                    hs_thread,
                    customer_email=customer_email,
                    attachments_data=None  # Never pass attachments to add_thread
                )

                fs_client.add_thread(fs_conv_id, fs_thread, imported=True)
                print(f"    ✓ Added")

        # Add tags
        if tags:
            print(f"\n{'=' * 70}")
            print(f"STEP 7: Adding tags")
            print("=" * 70)

            print(f"\nAdding tags: {', '.join(tags)}")
            fs_client.update_conversation_tags(fs_conv_id, tags)
            print(f"✓ Tags added")

        # Summary
        print(f"\n{'=' * 70}")
        print("MIGRATION COMPLETE!")
        print("=" * 70)

        print(f"\nHelp Scout Conversation {conversation_id} → FreeScout Conversation {fs_conv_id} (#{fs_conversation.get('number')})")
        print(f"\nDetails:")
        print(f"  Subject: {hs_conv.get('subject')}")
        print(f"  Customer: {hs_customer.get('firstName')} {hs_customer.get('lastName')}")
        print(f"  Threads migrated: {len(hs_threads)}")
        print(f"  Tags: {', '.join(tags) if tags else 'None'}")
        print(f"  Status: {hs_conv.get('status')} → {fs_conversation_data['status']}")

        print(f"\n{'=' * 70}")
        print("VERIFICATION")
        print("=" * 70)
        print(f"\nPlease check FreeScout conversation #{fs_conversation.get('number')}:")
        print(f"  1. Open FreeScout and navigate to conversation #{fs_conversation.get('number')}")
        print(f"  2. Verify subject matches: \"{hs_conv.get('subject')}\"")
        print(f"  3. Check that {len(hs_threads)} threads are present")
        print(f"  4. Verify timestamps are from {hs_conv.get('createdAt')[:10]} (not today)")
        print(f"  5. Confirm tags are applied: {', '.join(tags) if tags else 'None'}")
        print(f"  6. Check that content is readable and properly formatted")

        return True

    except HelpScoutAPIError as e:
        print(f"\n✗ Help Scout API Error: {e}")
        if e.status_code:
            print(f"  Status Code: {e.status_code}")
        return False

    except FreeScoutAPIError as e:
        print(f"\n✗ FreeScout API Error: {e}")
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
    """Main entry point."""
    if len(sys.argv) < 2:
        print("\nUsage: python test_specific_conversation.py <conversation_id>")
        print("\nExample: python test_specific_conversation.py 3119109492")
        print("\nTo find conversation IDs, check Help Scout or use the listConversations.py script.")
        return 1

    try:
        conversation_id = int(sys.argv[1])
    except ValueError:
        print(f"✗ Invalid conversation ID: {sys.argv[1]}")
        print("  Conversation ID must be a number")
        return 1

    print("\n" + "=" * 70)
    print("SPECIFIC CONVERSATION MIGRATION TEST")
    print("=" * 70)
    print(f"\nConversation ID: {conversation_id}")
    print("\nThis will migrate ONE conversation from Help Scout to FreeScout.")
    print("=" * 70)

    result = migrate_specific_conversation(conversation_id)

    if result:
        print("\n✓ Migration completed successfully!")
        return 0
    else:
        print("\n✗ Migration failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
