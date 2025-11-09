"""
Migrate only the missing active/pending conversations from Help Scout to FreeScout.
This will fetch the 85 missing conversations from Help Scout API and migrate them.
"""
import json
import sys
from pathlib import Path
from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient
from config.config import Config
from mapping.mappers import (
    map_customer_to_freescout,
    map_conversation_to_freescout,
    map_thread_to_freescout,
    extract_tags,
    map_status
)

def main():
    print('=' * 70)
    print('MIGRATE MISSING CONVERSATIONS')
    print('=' * 70)
    print()

    # Load list of missing conversations
    missing_file = Path('missing_conversations.json')
    if not missing_file.exists():
        print('Error: missing_conversations.json not found')
        print('Run remigrate_missing.py first to identify missing conversations')
        return 1

    with open(missing_file, 'r') as f:
        missing = json.load(f)

    print(f'Found {len(missing)} missing conversations to migrate')
    print()

    # Initialize clients
    hs_client = HelpScoutClient()
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    # Load current mapping
    progress_file = Path('migration_progress.json')
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            progress = json.load(f)
    else:
        progress = {
            'conversation_mapping': {},
            'customer_mapping': {}
        }

    # Statistics
    stats = {
        'total': len(missing),
        'migrated': 0,
        'skipped': 0,
        'errors': 0
    }

    print('Starting migration...')
    print()

    for i, conv_info in enumerate(missing, 1):
        hs_id = conv_info['hs_id']
        print(f'[{i}/{len(missing)}] Migrating HS:{hs_id}...')

        try:
            # Fetch full conversation from Help Scout
            hs_conv = hs_client.get_conversation(hs_id)

            # Get customer
            customer_id = hs_conv.get('primaryCustomer', {}).get('id') or hs_conv.get('createdBy', {}).get('id')
            if not customer_id:
                print(f'  ✗ No customer found, skipping')
                stats['skipped'] += 1
                continue

            # Check if customer already exists in FreeScout
            if str(customer_id) in progress['customer_mapping']:
                fs_customer_id = progress['customer_mapping'][str(customer_id)]
            else:
                # Fetch customer from Help Scout
                hs_customer = hs_client.get_customer(customer_id)

                # Map and create customer in FreeScout
                fs_customer_data = map_customer_to_freescout(hs_customer)
                fs_customer = fs_client.create_customer(fs_customer_data)
                fs_customer_id = fs_customer['id']

                # Store mapping
                progress['customer_mapping'][str(customer_id)] = fs_customer_id

            # Fetch threads
            hs_threads = hs_client.get_conversation_threads(hs_id)

            if not hs_threads:
                print(f'  ✗ No threads found, skipping')
                stats['skipped'] += 1
                continue

            # Get customer email for threads
            customer_email = None
            if 'primaryCustomer' in hs_conv:
                # Try 'email' field first (in conversation objects)
                customer_email = hs_conv['primaryCustomer'].get('email')
                # If not found, try 'emails' array (in full customer objects)
                if not customer_email:
                    emails = hs_conv['primaryCustomer'].get('emails', [])
                    if emails:
                        customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')

            # Prepare customer object for conversation
            hs_customer_data = hs_conv.get('primaryCustomer', {})
            customer_for_conversation = {
                "id": fs_customer_id,
                "email": customer_email,
                "first_name": hs_customer_data.get('firstName'),
                "last_name": hs_customer_data.get('lastName')
            }

            # Map first thread
            fs_first_thread = map_thread_to_freescout(
                hs_threads[0],
                customer_email=customer_email,
                attachments_data=None  # Skip attachments for now
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
            print(f'  ✓ Created conversation #{fs_conversation.get("number")} (ID: {fs_conv_id})')

            # Add remaining threads
            for hs_thread in hs_threads[1:]:
                fs_thread = map_thread_to_freescout(
                    hs_thread,
                    customer_email=customer_email,
                    attachments_data=None
                )
                fs_client.add_thread(fs_conv_id, fs_thread, imported=True)

            # Add tags
            tags = extract_tags(hs_conv)
            if tags:
                fs_client.update_conversation_tags(fs_conv_id, tags)

            # Update status and assignee after adding threads
            final_updates = {}
            expected_status = map_status(hs_conv.get('status'))
            final_updates['status'] = expected_status

            if fs_conversation_data.get('assignTo'):
                final_updates['assignTo'] = fs_conversation_data['assignTo']

            final_updates['byUser'] = 8
            fs_client.update_conversation(fs_conv_id, final_updates)

            print(f'  ✓ Migrated {len(hs_threads)} threads, status: {expected_status}')

            # Store mapping
            progress['conversation_mapping'][str(hs_id)] = fs_conv_id
            stats['migrated'] += 1

        except Exception as e:
            stats['errors'] += 1
            # Print more details for debugging
            error_msg = str(e)
            if hasattr(e, 'response') and e.response:
                error_msg += f' | Response: {e.response[:200]}'
            print(f'  ✗ Error: {error_msg}')

        print()

    # Save progress
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)

    # Print summary
    print('=' * 70)
    print('MIGRATION SUMMARY')
    print('=' * 70)
    print(f'Total: {stats["total"]}')
    print(f'Migrated: {stats["migrated"]}')
    print(f'Skipped: {stats["skipped"]}')
    print(f'Errors: {stats["errors"]}')
    print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
