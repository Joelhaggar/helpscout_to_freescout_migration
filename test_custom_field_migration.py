"""
Test script to migrate a single conversation with Help Scout ID custom field.

This tests the custom field functionality with a fresh conversation.
"""
import json
from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient
from config.config import Config
from mapping.mappers import (
    map_customer_to_freescout,
    map_conversation_to_freescout,
    map_thread_to_freescout,
    map_status,
    map_user_id
)


def main():
    print('=' * 70)
    print('TEST CUSTOM FIELD MIGRATION')
    print('=' * 70)
    print()

    # Initialize clients
    hs_client = HelpScoutClient()
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    # Pick a test conversation from Help Scout
    test_hs_id = 3119294864  # First conversation from mapping

    print(f'Testing with Help Scout conversation: {test_hs_id}')
    print()

    try:
        # Fetch conversation from Help Scout
        print('1. Fetching conversation from Help Scout...')
        hs_conv = hs_client.get_conversation(test_hs_id)
        print(f'   ✓ Subject: {hs_conv.get("subject", "")[:60]}')
        print(f'   ✓ Status: {hs_conv.get("status")}')
        print()

        # Get customer
        print('2. Getting customer...')
        customer_data = hs_conv.get('primaryCustomer', {})
        customer_id = customer_data.get('id')

        if not customer_id:
            print('   ✗ No customer found')
            return 1

        # Fetch full customer data
        hs_customer = hs_client.get_customer(customer_id)
        print(f'   ✓ Customer: {hs_customer.get("firstName")} {hs_customer.get("lastName")}')

        # Create customer in FreeScout
        print('3. Creating customer in FreeScout...')
        fs_customer_data = map_customer_to_freescout(hs_customer)
        fs_customer = fs_client.create_customer(fs_customer_data)
        fs_customer_id = fs_customer['id']
        print(f'   ✓ Created customer ID: {fs_customer_id}')
        print()

        # Get customer email
        customer_email = hs_conv['primaryCustomer'].get('email')
        if not customer_email:
            emails = hs_customer.get('emails', [])
            if emails:
                customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')

        # Get threads
        print('4. Fetching threads...')
        hs_threads = hs_client.get_conversation_threads(test_hs_id)
        print(f'   ✓ Found {len(hs_threads)} threads')
        print()

        if not hs_threads:
            print('   ✗ No threads found')
            return 1

        # Create conversation in FreeScout
        print('5. Creating conversation in FreeScout...')

        # Prepare customer object
        customer_for_conversation = {
            "id": fs_customer_id,
            "email": customer_email,
            "first_name": hs_customer.get('firstName'),
            "last_name": hs_customer.get('lastName')
        }

        # Map first thread for conversation creation
        first_thread = hs_threads[0]
        fs_first_thread = map_thread_to_freescout(
            first_thread,
            customer_email=customer_email,
            attachments_data=[]
        )

        # Map conversation
        fs_conversation_data = map_conversation_to_freescout(
            hs_conv,
            customer_for_conversation,
            fs_first_thread
        )

        # Create conversation
        fs_conversation = fs_client.create_conversation(
            fs_conversation_data,
            imported=True
        )
        fs_conv_id = fs_conversation['id']
        fs_conv_number = fs_conversation.get('number')

        print(f'   ✓ Created conversation #{fs_conv_number} (ID: {fs_conv_id})')
        print()

        # Add remaining threads
        print('6. Adding remaining threads...')
        for i, hs_thread in enumerate(hs_threads[1:], start=2):
            fs_thread = map_thread_to_freescout(
                hs_thread,
                customer_email=customer_email,
                attachments_data=None
            )
            fs_client.add_thread(fs_conv_id, fs_thread, imported=True)
            print(f'   ✓ Added thread {i}/{len(hs_threads)}')
        print()

        # Update status after adding threads
        print('7. Updating conversation status...')
        expected_status = map_status(hs_conv.get('status'))
        final_updates = {
            'status': expected_status,
            'byUser': 8
        }

        # Re-apply assignee if needed
        assignee = hs_conv.get('assignee')
        if assignee and assignee.get('id'):
            fs_user_id = map_user_id(assignee['id'])
            if fs_user_id:
                final_updates['assignTo'] = fs_user_id

        fs_client.update_conversation(fs_conv_id, final_updates)
        print(f'   ✓ Status set to: {expected_status}')
        print()

        # NOW TEST THE CUSTOM FIELDS
        print('8. Setting Help Scout ID and Number custom fields...')
        hs_number = hs_conv.get('number')
        print(f'   Helpscout_ID (field 1): {test_hs_id}')
        print(f'   Helpscout_No (field 2): {hs_number}')
        print()

        try:
            result = fs_client.update_custom_fields(fs_conv_id, [
                {'id': 1, 'value': str(test_hs_id)},
                {'id': 2, 'value': str(hs_number)}
            ])

            print('   ✓ Custom fields updated!')
            print(f'   Response: {result}')
            print()

        except Exception as e:
            print(f'   ✗ Custom field update failed: {e}')
            print()

        # Verify the custom fields
        print('9. Verifying custom fields...')
        conv = fs_client.get_conversation(fs_conv_id)

        if 'customFields' in conv:
            print('   Custom fields in conversation:')
            for field in conv['customFields']:
                print(f'     - {field.get("name")}: {field.get("value")}')

            # Check if our values are there
            id_match = False
            no_match = False
            for field in conv['customFields']:
                if field.get('name') == 'Helpscout':
                    if field.get('value') == str(test_hs_id):
                        id_match = True
                elif field.get('name') == 'Helpscout_No':
                    if field.get('value') == str(hs_number):
                        no_match = True

            print()
            if id_match and no_match:
                print('   ✓✓ SUCCESS! Both custom fields are set correctly!')
            elif id_match:
                print('   ⚠ Helpscout_ID is correct, but Helpscout_No mismatch')
            elif no_match:
                print('   ⚠ Helpscout_No is correct, but Helpscout_ID mismatch')
            else:
                print('   ⚠ Both custom fields have mismatches')
        else:
            print('   ⚠ No custom fields found in conversation')

        print()
        print('=' * 70)
        print('TEST COMPLETE')
        print('=' * 70)
        print()
        print(f'View conversation in FreeScout:')
        print(f'  {Config.FREESCOUT_URL}/conversation/{fs_conv_id}')
        print()
        print(f'View conversation in Help Scout:')
        print(f'  https://secure.helpscout.net/conversation/{test_hs_id}')
        print()

        return 0

    except Exception as e:
        print(f'ERROR: {e}')
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
