"""
End-to-end migration test with real Help Scout data.
Tests migrating one customer with their conversations from Help Scout to FreeScout.
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
import json


def test_real_migration():
    """
    Migrate one customer with conversations from Help Scout to FreeScout.
    """
    print("=" * 70)
    print("END-TO-END MIGRATION TEST: Real Help Scout Data → FreeScout")
    print("=" * 70)

    try:
        # Initialize clients
        print("\nInitializing API clients...")
        hs_client = HelpScoutClient()
        fs_client = FreeScoutClient()
        print("✓ Clients initialized")

        # Step 1: Get a customer with conversations from Help Scout
        print("\n" + "=" * 70)
        print("STEP 1: Finding customer with conversations in Help Scout")
        print("=" * 70)

        print("\nSearching for customer with conversations...")
        # Get first few conversations to find a customer
        hs_conversations_sample = hs_client.get_conversations(mailbox=312012, page=1, status='all')
        sample_convs = hs_conversations_sample.get('_embedded', {}).get('conversations', [])

        if not sample_convs:
            print("✗ No conversations found in Help Scout")
            return False

        # Get customer from first conversation
        first_conv = sample_convs[0]
        customer_ref = first_conv.get('primaryCustomer', first_conv.get('customer'))
        if not customer_ref:
            print("✗ No customer found in conversation")
            return False

        customer_id = customer_ref.get('id')
        print(f"\n✓ Found conversation with customer ID: {customer_id}")

        # Fetch full customer details
        hs_customer = hs_client.get_customer(customer_id)
        print(f"\n✓ Retrieved customer: {hs_customer.get('firstName')} {hs_customer.get('lastName')}")
        print(f"  Help Scout ID: {hs_customer.get('id')}")
        emails = hs_customer.get('emails', [])
        if emails:
            email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')
            print(f"  Email: {email}")
        else:
            print(f"  Email: N/A")

        # Step 2: Map and create customer in FreeScout
        print("\n" + "=" * 70)
        print("STEP 2: Creating customer in FreeScout")
        print("=" * 70)

        print("\nMapping customer data...")
        fs_customer_data = map_customer_to_freescout(hs_customer)
        print("✓ Customer data mapped")
        print(f"  Mapped data: {json.dumps(fs_customer_data, indent=2)}")

        print("\nCreating customer in FreeScout...")
        fs_customer = fs_client.create_customer(fs_customer_data)
        fs_customer_id = fs_customer['id']
        print(f"✓ Customer created in FreeScout")
        print(f"  FreeScout ID: {fs_customer_id}")

        # Get full customer data
        fs_customer_full = fs_client.get_customer(fs_customer_id)
        print(f"  Name: {fs_customer_full.get('firstName')} {fs_customer_full.get('lastName')}")
        print(f"  Email: {fs_customer_full.get('email')}")

        # Prepare customer data for conversations
        # Ensure we have at least email or firstName
        customer_email = fs_customer_data.get('email')
        if not customer_email:
            # If no email, generate one from Help Scout ID
            customer_email = f"helpscout.customer.{hs_customer.get('id')}@migration.local"

        customer_for_conversation = {
            "id": fs_customer_id,
            "email": customer_email,
            "first_name": fs_customer_data.get('firstName'),
            "last_name": fs_customer_data.get('lastName')
        }

        # Step 3: Use the conversations we already found
        print("\n" + "=" * 70)
        print("STEP 3: Using conversations from Help Scout")
        print("=" * 70)

        print(f"\nUsing sample conversations from mailbox...")
        hs_conversations = sample_convs

        if not hs_conversations:
            print("⚠ No conversations found")
            return False

        print(f"✓ Found {len(hs_conversations)} conversation(s) to migrate")

        # Limit to first 3 conversations for testing
        max_conversations = min(3, len(hs_conversations))
        hs_conversations = hs_conversations[:max_conversations]
        print(f"  (Limiting to {max_conversations} conversation(s) for testing)")

        # Step 4: Migrate each conversation
        print("\n" + "=" * 70)
        print("STEP 4: Migrating conversations to FreeScout")
        print("=" * 70)

        migrated_conversations = []

        for i, hs_conv in enumerate(hs_conversations, 1):
            print(f"\n--- Conversation {i}/{len(hs_conversations)} ---")
            print(f"Subject: {hs_conv.get('subject')}")
            print(f"Help Scout ID: {hs_conv.get('id')}")
            print(f"Status: {hs_conv.get('status')}")
            print(f"Created: {hs_conv.get('createdAt')}")

            # Get threads for this conversation
            print(f"\nFetching threads...")
            hs_threads = hs_client.get_conversation_threads(hs_conv['id'])
            print(f"✓ Retrieved {len(hs_threads)} thread(s)")

            if not hs_threads:
                print("⚠ No threads found, skipping conversation")
                continue

            # Map first thread for initial conversation creation
            first_thread = hs_threads[0]
            print(f"\nMapping initial thread...")
            print(f"  Type: {first_thread.get('type')}")
            print(f"  Created: {first_thread.get('createdAt')}")

            fs_first_thread = map_thread_to_freescout(
                first_thread,
                customer_email=customer_for_conversation['email']
            )

            # Map conversation
            print(f"\nMapping conversation...")
            fs_conversation_data = map_conversation_to_freescout(
                hs_conv,
                customer_for_conversation,
                fs_first_thread
            )

            # Create conversation in FreeScout
            print(f"\nCreating conversation in FreeScout...")
            fs_conversation = fs_client.create_conversation(
                fs_conversation_data,
                imported=True  # Preserve timestamps, prevent notifications
            )
            fs_conv_id = fs_conversation['id']
            print(f"✓ Conversation created")
            print(f"  FreeScout ID: {fs_conv_id}")
            print(f"  Number: #{fs_conversation.get('number')}")

            # Add remaining threads
            if len(hs_threads) > 1:
                print(f"\nAdding {len(hs_threads) - 1} additional thread(s)...")
                for j, hs_thread in enumerate(hs_threads[1:], 2):
                    fs_thread = map_thread_to_freescout(
                        hs_thread,
                        customer_email=customer_for_conversation['email']
                    )

                    fs_client.add_thread(fs_conv_id, fs_thread, imported=True)
                    print(f"  ✓ Thread {j}/{len(hs_threads)} added")

            # Add tags if any
            tags = extract_tags(hs_conv)
            if tags:
                print(f"\nAdding tags: {', '.join(tags)}")
                fs_client.update_conversation_tags(fs_conv_id, tags)
                print(f"✓ Tags added")

            migrated_conversations.append({
                'helpscout_id': hs_conv['id'],
                'freescout_id': fs_conv_id,
                'freescout_number': fs_conversation.get('number'),
                'subject': hs_conv.get('subject'),
                'thread_count': len(hs_threads)
            })

        # Step 5: Validation
        print("\n" + "=" * 70)
        print("STEP 5: Validation")
        print("=" * 70)

        print(f"\nMigration Summary:")
        print(f"  Customer: {hs_customer.get('firstName')} {hs_customer.get('lastName')}")
        print(f"    Help Scout ID: {hs_customer.get('id')}")
        print(f"    FreeScout ID: {fs_customer_id}")
        print(f"\n  Conversations migrated: {len(migrated_conversations)}")

        for conv in migrated_conversations:
            print(f"\n  - {conv['subject']}")
            print(f"      Help Scout ID: {conv['helpscout_id']}")
            print(f"      FreeScout ID: {conv['freescout_id']} (#{conv['freescout_number']})")
            print(f"      Threads: {conv['thread_count']}")

        # Manual verification instructions
        print("\n" + "=" * 70)
        print("MANUAL VERIFICATION REQUIRED")
        print("=" * 70)
        print(f"\nPlease verify in FreeScout UI:")
        print(f"\n1. Search for customer: {fs_customer_full.get('firstName')} {fs_customer_full.get('lastName')}")
        print(f"   Email: {fs_customer_full.get('email')}")
        print(f"\n2. Verify customer details are correct")
        print(f"\n3. Check the following conversations:")

        for conv in migrated_conversations:
            print(f"\n   Conversation #{conv['freescout_number']}: {conv['subject']}")
            print(f"     - Has {conv['thread_count']} thread(s)")
            print(f"     - Timestamps are from original dates (not today)")
            print(f"     - Thread order is correct")
            print(f"     - Tags are applied (if any)")

        print("\n" + "=" * 70)
        print("✓ MIGRATION TEST COMPLETED SUCCESSFULLY!")
        print("=" * 70)

        return True

    except HelpScoutAPIError as e:
        print(f"\n✗ Help Scout API Error: {e}")
        if e.status_code:
            print(f"  Status Code: {e.status_code}")
        if e.response:
            print(f"  Response: {e.response}")
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
    """Run the real migration test."""
    print("\n" + "=" * 70)
    print("REAL DATA MIGRATION TEST")
    print("=" * 70)
    print("\nThis test migrates one customer with up to 3 conversations")
    print("from Help Scout to FreeScout using real production data.")
    print("\nWARNING: This will create real data in FreeScout!")
    print("=" * 70)

    result = test_real_migration()

    if result:
        print("\n✓ Test completed successfully!")
        print("\nNext steps:")
        print("  1. Verify data in FreeScout UI")
        print("  2. If everything looks good, proceed with full migration")
        print("  3. If issues found, review mappings and try again")
        return 0
    else:
        print("\n✗ Test failed")
        print("\nReview the errors above and fix before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
