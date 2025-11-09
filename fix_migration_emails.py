"""
Fix @migration.local placeholder emails by extracting real emails from Help Scout
"""
import json
from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient

hs_client = HelpScoutClient()
fs_client = FreeScoutClient()

print("=" * 90)
print("FIXING @migration.local PLACEHOLDER EMAILS")
print("=" * 90)

# Get all conversations with @migration.local emails
migration_convs = []
page = 1

while page <= 20:
    response = fs_client.get_conversations(page=page, page_size=100)
    conversations = response.get('_embedded', {}).get('conversations', [])
    
    if not conversations:
        break
    
    for conv in conversations:
        email = conv.get('customer', {}).get('email', '')
        if 'migration.local' in email:
            migration_convs.append(conv)
    
    page += 1

print(f"\nFound {len(migration_convs)} conversations with @migration.local emails")

# Try to fix each one
fixed = 0
skipped = 0
failed = 0

for i, conv in enumerate(migration_convs, 1):
    fs_id = conv.get('id')
    old_email = conv.get('customer', {}).get('email', '')
    customer_id = conv.get('customer', {}).get('id')
    
    # Get Help Scout ID from custom field
    custom_fields = conv.get('customFields', [])
    hs_id_field = next((f for f in custom_fields if f.get('name') == 'Helpscout'), None)
    hs_id = int(hs_id_field.get('value')) if hs_id_field else None
    
    if not hs_id:
        print(f"\n[{i}/{len(migration_convs)}] FS {fs_id}: No Help Scout ID found - SKIPPED")
        skipped += 1
        continue
    
    try:
        # Fetch Help Scout conversation
        hs_conv = hs_client.get_conversation(hs_id, embed='threads')
        threads = hs_conv.get('_embedded', {}).get('threads', [])
        
        # Try to extract real email
        new_email = None
        
        # Check customer-type threads first
        for thread in threads:
            if thread.get('type') == 'customer':
                created_by = thread.get('createdBy', {})
                if created_by.get('email'):
                    new_email = created_by['email']
                    break
        
        # Check other threads
        if not new_email:
            for thread in threads:
                created_by = thread.get('createdBy', {})
                if created_by.get('email') and 'nowhere' not in created_by.get('email', '').lower():
                    new_email = created_by['email']
                    break
        
        if new_email and new_email != old_email:
            # Update the customer in FreeScout
            customer_data = {'email': new_email}
            fs_client.update_customer(customer_id, customer_data)
            
            print(f"[{i}/{len(migration_convs)}] FS {fs_id}: {old_email} → {new_email} ✓")
            fixed += 1
        else:
            print(f"[{i}/{len(migration_convs)}] FS {fs_id}: No real email found - SKIPPED")
            skipped += 1
    
    except Exception as e:
        print(f"[{i}/{len(migration_convs)}] FS {fs_id}: ERROR - {str(e)[:60]}")
        failed += 1

print(f"\n" + "=" * 90)
print(f"RESULTS:")
print(f"=" * 90)
print(f"  Fixed:    {fixed}")
print(f"  Skipped:  {skipped}")
print(f"  Failed:   {failed}")
print(f"  Total:    {len(migration_convs)}")

