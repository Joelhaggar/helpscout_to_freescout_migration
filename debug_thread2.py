"""Debug script to inspect a failing conversation - more details"""
from api.helpscout_client import HelpScoutClient
import json

hs_client = HelpScoutClient()

# Test with the first conversation that failed
hs_id = 3119109492

print(f'Fetching HS:{hs_id}...')
hs_conv = hs_client.get_conversation(hs_id)

print('\n=== Full Conversation ===')
print(json.dumps(hs_conv, indent=2)[:2000])

print('\n\n=== Primary Customer ===')
primary_customer = hs_conv.get('primaryCustomer')
if primary_customer:
    print(json.dumps(primary_customer, indent=2))
else:
    print('NO PRIMARY CUSTOMER')

print('\n\n=== Created By ===')
created_by = hs_conv.get('createdBy')
if created_by:
    print(json.dumps(created_by, indent=2))
else:
    print('NO CREATED BY')
