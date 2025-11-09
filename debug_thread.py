"""Debug script to inspect a failing conversation"""
from api.helpscout_client import HelpScoutClient
from mapping.mappers import map_thread_to_freescout
import json

hs_client = HelpScoutClient()

# Test with the first conversation that failed
hs_id = 3119109492

print(f'Fetching HS:{hs_id}...')
hs_conv = hs_client.get_conversation(hs_id)
print(f'Conversation status: {hs_conv.get("status")}')
print(f'Subject: {hs_conv.get("subject")}')

# Get customer email
customer_email = None
if 'primaryCustomer' in hs_conv:
    emails = hs_conv['primaryCustomer'].get('emails', [])
    if emails:
        customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')

print(f'Customer email: {customer_email}')

# Get threads
hs_threads = hs_client.get_conversation_threads(hs_id)
print(f'\nFound {len(hs_threads)} threads')

# Map the second thread (first one goes in conversation creation)
if len(hs_threads) > 1:
    print('\n=== Second Thread (the one that fails) ===')
    hs_thread = hs_threads[1]
    print(f'Type: {hs_thread.get("type")}')
    print(f'Created At: {hs_thread.get("createdAt")}')
    print(f'Created By: {hs_thread.get("createdBy")}')

    fs_thread = map_thread_to_freescout(
        hs_thread,
        customer_email=customer_email,
        attachments_data=None
    )

    print('\n=== Mapped FreeScout Thread ===')
    print(json.dumps(fs_thread, indent=2))
