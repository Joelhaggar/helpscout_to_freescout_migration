"""Debug script - test new email extraction logic"""
from api.helpscout_client import HelpScoutClient

hs_client = HelpScoutClient()

hs_id = 3119109492
hs_conv = hs_client.get_conversation(hs_id)

# New logic
customer_email = None
if 'primaryCustomer' in hs_conv:
    # Try 'email' field first (in conversation objects)
    customer_email = hs_conv['primaryCustomer'].get('email')
    # If not found, try 'emails' array (in full customer objects)
    if not customer_email:
        emails = hs_conv['primaryCustomer'].get('emails', [])
        if emails:
            customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')

print(f'Customer email: {customer_email}')
