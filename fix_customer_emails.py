"""
Fix customer records with @migration.local placeholder emails.

This script directly updates customer email addresses in FreeScout
by extracting real emails from Help Scout.
"""
import json
import time
from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient

def get_customers_with_bad_emails():
    """Get all customers with @migration.local emails."""
    fs_client = FreeScoutClient()
    bad_customers = []
    page = 1

    print("Fetching all customers...")

    while True:
        response = fs_client.get_customers(page=page, page_size=50)
        customers = response.get('_embedded', {}).get('customers', [])

        if not customers:
            break

        for customer in customers:
            email = customer.get('email', '')
            if '@migration.local' in email:
                bad_customers.append({
                    'fs_id': customer.get('id'),
                    'fs_email': email,
                    'name': f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
                    'helpscout_id': None  # We'll extract this from conversations
                })

        page_info = response.get('page', {})
        if page >= page_info.get('totalPages', 1):
            break

        page += 1

    return bad_customers

def find_helpscout_id_for_customer(fs_client, hs_client, fs_customer_id, customer_email):
    """Find Help Scout customer ID by checking conversations."""
    try:
        # Search conversations for this customer
        response = fs_client.get_conversations(page=1, page_size=50)
        conversations = response.get('_embedded', {}).get('conversations', [])

        for conv in conversations:
            if conv.get('customer', {}).get('id') == fs_customer_id:
                # Found a conversation for this customer
                custom_fields = conv.get('customFields', [])
                for field in custom_fields:
                    if field.get('name') == 'Helpscout':
                        return field.get('value')
        return None
    except:
        return None

def extract_real_email_from_helpscout(hs_client, hs_customer_id):
    """Extract real email from Help Scout customer."""
    try:
        hs_customer = hs_client.get_customer(hs_customer_id)

        # Try customer emails first
        emails = hs_customer.get('emails', [])
        if emails:
            real_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')
            if real_email and '@migration.local' not in real_email:
                return real_email

        return None
    except:
        return None

def fix_customer_emails():
    """Fix all customers with @migration.local emails."""
    fs_client = FreeScoutClient()
    hs_client = HelpScoutClient()

    # Get all bad customers
    bad_customers = get_customers_with_bad_emails()
    print(f"\nFound {len(bad_customers)} customers with @migration.local emails\n")

    fixes = []
    errors = []

    for i, customer in enumerate(bad_customers, 1):
        try:
            fs_id = customer['fs_id']

            # Try to find Help Scout ID by searching conversations
            # This is a backup—ideally Help Scout ID would be in a custom field
            hs_id = None

            # Search for a conversation with this customer
            page = 1
            found = False
            while page <= 20 and not found:  # Check first 1000 conversations
                response = fs_client.get_conversations(page=page, page_size=50)
                conversations = response.get('_embedded', {}).get('conversations', [])

                if not conversations:
                    break

                for conv in conversations:
                    if conv.get('customer', {}).get('id') == fs_id:
                        custom_fields = conv.get('customFields', [])
                        for field in custom_fields:
                            if field.get('name') == 'Helpscout':
                                hs_id = field.get('value')
                                found = True
                                break
                        if found:
                            break

                if found:
                    break
                page += 1

            if not hs_id:
                errors.append({
                    'fs_id': fs_id,
                    'reason': 'Could not find Help Scout ID'
                })
                print(f"✗ [{i:4d}/{len(bad_customers)}] FS:{fs_id:5d} | NO HS ID FOUND")
                continue

            # Get Help Scout customer
            hs_conv = hs_client.get_conversation(hs_id)
            hs_customer_id = hs_conv.get('_embedded', {}).get('customer', {}).get('id')

            if not hs_customer_id:
                errors.append({
                    'fs_id': fs_id,
                    'reason': 'No customer in Help Scout conversation'
                })
                print(f"✗ [{i:4d}/{len(bad_customers)}] FS:{fs_id:5d} | NO HS CUSTOMER")
                continue

            # Extract real email from Help Scout
            hs_customer = hs_client.get_customer(hs_customer_id)
            real_email = None

            emails = hs_customer.get('emails', [])
            if emails:
                real_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')

            if not real_email or '@migration.local' in real_email:
                errors.append({
                    'fs_id': fs_id,
                    'reason': 'No real email in Help Scout'
                })
                print(f"✗ [{i:4d}/{len(bad_customers)}] FS:{fs_id:5d} | NO REAL EMAIL")
                continue

            # Update FreeScout customer
            try:
                fs_client.update_customer(fs_id, {'email': real_email})

                fixes.append({
                    'fs_id': fs_id,
                    'old_email': customer['fs_email'],
                    'new_email': real_email
                })

                print(f"✓ [{i:4d}/{len(bad_customers)}] FS:{fs_id:5d} | {real_email}")

            except Exception as e:
                errors.append({
                    'fs_id': fs_id,
                    'reason': f'Update failed: {str(e)}'
                })
                print(f"✗ [{i:4d}/{len(bad_customers)}] FS:{fs_id:5d} | UPDATE FAILED: {str(e)[:30]}")

        except Exception as e:
            errors.append({
                'fs_id': customer['fs_id'],
                'reason': str(e)
            })
            print(f"✗ [{i:4d}/{len(bad_customers)}] FS:{customer['fs_id']:5d} | ERROR: {str(e)[:40]}")

        # Rate limit
        time.sleep(0.2)

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Successfully fixed: {len(fixes)}/{len(bad_customers)}")
    print(f"Errors: {len(errors)}")

    if errors:
        print(f"\nFirst 10 errors:")
        for error in errors[:10]:
            print(f"  FS:{error['fs_id']} - {error['reason']}")

    # Save results
    with open('customer_email_fix_results.json', 'w') as f:
        json.dump({
            'total_fixed': len(fixes),
            'total_errors': len(errors),
            'fixed': fixes,
            'errors': errors
        }, f, indent=2)

    print(f"\nResults saved to customer_email_fix_results.json")

if __name__ == '__main__':
    fix_customer_emails()
