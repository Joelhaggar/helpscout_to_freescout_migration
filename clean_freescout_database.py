#!/usr/bin/env python3
"""
Delete ALL conversations and customers from FreeScout.

WARNING: This is a destructive operation and cannot be undone!
Use this to prepare for a clean migration.
"""
import time
from api.freescout_client import FreeScoutClient
from config.config import Config


def delete_all_conversations(fs_client: FreeScoutClient, mailbox_id: int):
    """Delete all conversations from a mailbox."""
    print('=' * 70)
    print('DELETING ALL CONVERSATIONS')
    print('=' * 70)
    print()

    page = 1
    total_deleted = 0

    while True:
        print(f'Fetching page {page}...')

        # Get conversations (25 per page)
        conversations = fs_client.get_conversations(
            mailbox_id=mailbox_id,
            status='all',
            page=page
        )

        if not conversations:
            print('No more conversations found.')
            break

        print(f'  Found {len(conversations)} conversations on page {page}')

        # Delete each conversation
        for conv in conversations:
            conv_id = conv['id']
            conv_number = conv.get('number', 'N/A')
            subject = conv.get('subject', 'No subject')[:50]

            try:
                fs_client.delete_conversation(conv_id)
                total_deleted += 1
                print(f'  ✓ Deleted #{conv_number} (ID: {conv_id}): {subject}')

                # Rate limiting - avoid overwhelming the API
                time.sleep(0.1)

            except Exception as e:
                print(f'  ✗ Failed to delete #{conv_number} (ID: {conv_id}): {e}')

        # Don't increment page - after deletion, next batch will be on page 1
        # But add a small delay between pages
        time.sleep(0.5)

    print()
    print(f'Total conversations deleted: {total_deleted}')
    print()


def delete_all_customers(fs_client: FreeScoutClient):
    """Delete all customers."""
    print('=' * 70)
    print('DELETING ALL CUSTOMERS')
    print('=' * 70)
    print()

    page = 1
    total_deleted = 0

    while True:
        print(f'Fetching customers page {page}...')

        try:
            # Get customers (25 per page)
            customers = fs_client.get_customers(page=page)

            if not customers:
                print('No more customers found.')
                break

            print(f'  Found {len(customers)} customers on page {page}')

            # Delete each customer
            for customer in customers:
                customer_id = customer['id']
                email = customer.get('emails', [{}])[0] if customer.get('emails') else 'No email'
                name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()

                try:
                    fs_client.delete_customer(customer_id)
                    total_deleted += 1
                    print(f'  ✓ Deleted customer {customer_id}: {name} ({email})')

                    # Rate limiting
                    time.sleep(0.1)

                except Exception as e:
                    print(f'  ✗ Failed to delete customer {customer_id}: {e}')

            # Don't increment page - similar to conversations
            time.sleep(0.5)

        except Exception as e:
            print(f'Error fetching customers: {e}')
            break

    print()
    print(f'Total customers deleted: {total_deleted}')
    print()


def main():
    print()
    print('=' * 70)
    print('CLEAN FREESCOUT DATABASE')
    print('=' * 70)
    print()
    print('WARNING: This will delete ALL conversations and customers!')
    print(f'FreeScout URL: {Config.FREESCOUT_URL}')
    print()
    print('This operation CANNOT be undone!')
    print()

    # Require explicit confirmation
    response = input('Type "DELETE ALL" to confirm: ')
    if response != "DELETE ALL":
        print('Aborted.')
        return 1

    print()
    print('Starting cleanup...')
    print()

    # Initialize FreeScout client
    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    # Delete all conversations first (they reference customers)
    delete_all_conversations(fs_client, Config.FREESCOUT_MAILBOX_ID)

    # Then delete all customers
    delete_all_customers(fs_client)

    print('=' * 70)
    print('CLEANUP COMPLETE')
    print('=' * 70)
    print()
    print('FreeScout database is now clean and ready for migration.')
    print()

    return 0


if __name__ == '__main__':
    exit(main())
