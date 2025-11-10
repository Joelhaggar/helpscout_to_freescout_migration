"""
Fix all conversations with @migration.local placeholder emails.

This script:
1. Identifies ALL conversations with @migration.local emails
2. Extracts real emails from Help Scout threads
3. Creates/finds customers with real emails
4. Reassigns conversations to correct customers

Priority: Active conversations are fixed first.
"""
import json
import time
import sys
from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient
from config.config import Config

def get_all_bad_email_conversations():
    """Get all conversations with @migration.local emails."""
    fs_client = FreeScoutClient()
    all_bad_email_convs = []
    page = 1

    print("Collecting all conversations with placeholder emails...")

    while True:
        response = fs_client.get_conversations(page=page, page_size=50)
        conversations = response.get('_embedded', {}).get('conversations', [])

        if not conversations:
            break

        for conv in conversations:
            email = conv.get('customer', {}).get('email', '')

            if '@migration.local' in email:
                custom_fields = conv.get('customFields', [])
                helpscout_id = None

                for field in custom_fields:
                    if field.get('name') == 'Helpscout':
                        helpscout_id = field.get('value')
                        break

                if helpscout_id:
                    all_bad_email_convs.append({
                        'fs_id': conv.get('id'),
                        'fs_customer_id': conv.get('customer', {}).get('id'),
                        'fs_email': email,
                        'status': conv.get('status', 'unknown'),
                        'helpscout_id': helpscout_id,
                        'subject': conv.get('subject', '')[:50]
                    })

        page_info = response.get('page', {})
        if page >= page_info.get('totalPages', 1):
            break

        page += 1

    return all_bad_email_convs

def extract_real_email(hs_client, hs_id):
    """Extract real email from Help Scout conversation."""
    try:
        hs_conv = hs_client.get_conversation(hs_id, embed='threads')
        threads = hs_conv.get('_embedded', {}).get('threads', [])
        hs_customer = hs_conv.get('_embedded', {}).get('customer', {})

        # Try customer emails first
        emails = hs_customer.get('emails', [])
        if emails:
            real_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')
            if real_email and '@migration.local' not in real_email:
                return real_email

        # Check threads for email
        for thread in threads:
            created_by = thread.get('createdBy', {})
            thread_email = created_by.get('email', '')
            if thread_email and 'nowhere' not in thread_email.lower() and '@migration.local' not in thread_email:
                return thread_email

        return None
    except Exception as e:
        return None

def fix_conversations(convs, priority_status=None):
    """Fix conversations by reassigning to customers with real emails."""
    fs_client = FreeScoutClient()
    hs_client = HelpScoutClient()

    # Sort by status if priority given
    if priority_status:
        convs = sorted(
            convs,
            key=lambda x: (x['status'] not in priority_status, x['fs_id'])
        )

    fixes = []
    errors = []

    print(f"\nFixing {len(convs)} conversations with placeholder emails...\n")

    for i, conv in enumerate(convs, 1):
        try:
            # Extract real email
            real_email = extract_real_email(hs_client, conv['helpscout_id'])

            if real_email:
                # Check if customer with this email already exists
                existing_customer = fs_client.search_customer_by_email(real_email)

                if existing_customer:
                    target_customer_id = existing_customer['id']
                    action = 'REASSIGN_TO_EXISTING'
                else:
                    # Create new customer
                    try:
                        hs_conv = hs_client.get_conversation(conv['helpscout_id'])
                        hs_customer = hs_conv.get('_embedded', {}).get('customer', {})

                        new_customer = fs_client.create_customer({
                            'firstName': hs_customer.get('firstName', 'Unknown'),
                            'lastName': hs_customer.get('lastName', ''),
                            'email': real_email
                        })
                        target_customer_id = new_customer.get('id')
                        action = 'CREATE_AND_REASSIGN'
                    except Exception as e:
                        errors.append({
                            'fs_id': conv['fs_id'],
                            'reason': f'Failed to create customer: {str(e)}'
                        })
                        continue

                # Reassign conversation
                try:
                    fs_client.update_conversation(conv['fs_id'], {
                        'byUser': 8,  # Joel Haggar
                        'customerId': target_customer_id
                    })

                    fixes.append({
                        'fs_id': conv['fs_id'],
                        'old_email': conv['fs_email'],
                        'new_email': real_email,
                        'action': action,
                        'status': conv['status']
                    })

                    status_symbol = '✓' if action == 'REASSIGN_TO_EXISTING' else '✨'
                    print(f"{status_symbol} [{i:4d}/{len(convs)}] FS:{conv['fs_id']:5d} | {conv['status']:7s} | {real_email[:40]}")

                except Exception as e:
                    errors.append({
                        'fs_id': conv['fs_id'],
                        'reason': f'Failed to reassign: {str(e)}'
                    })
            else:
                errors.append({
                    'fs_id': conv['fs_id'],
                    'reason': 'No real email found in Help Scout'
                })
                print(f"✗ [{i:4d}/{len(convs)}] FS:{conv['fs_id']:5d} | {conv['status']:7s} | NO EMAIL FOUND")

        except Exception as e:
            errors.append({
                'fs_id': conv['fs_id'],
                'reason': str(e)
            })
            print(f"✗ [{i:4d}/{len(convs)}] FS:{conv['fs_id']:5d} | ERROR: {str(e)[:40]}")

        # Rate limit
        time.sleep(0.15)

    return fixes, errors

def main():
    """Main execution."""
    print("=" * 70)
    print("FreeScout Email Fix Script")
    print("=" * 70)

    # Get all conversations with bad emails
    all_convs = get_all_bad_email_conversations()

    # Group by status
    by_status = {}
    for conv in all_convs:
        status = conv['status']
        by_status[status] = by_status.get(status, 0) + 1

    print(f"\nFound {len(all_convs)} conversations with @migration.local emails:")
    for status in sorted(by_status.keys()):
        print(f"  {status:10s}: {by_status[status]:4d}")

    # Fix in priority order: active/pending first, then closed
    priority_convs = [c for c in all_convs if c['status'] in ['active', 'pending']]
    closed_convs = [c for c in all_convs if c['status'] == 'closed']

    all_fixes = []
    all_errors = []

    if priority_convs:
        print(f"\n{'='*70}")
        print(f"PRIORITY: Fixing {len(priority_convs)} ACTIVE/PENDING conversations")
        print(f"{'='*70}")
        fixes, errors = fix_conversations(priority_convs)
        all_fixes.extend(fixes)
        all_errors.extend(errors)

    if closed_convs:
        print(f"\n{'='*70}")
        print(f"SECONDARY: Fixing {len(closed_convs)} CLOSED conversations")
        print(f"{'='*70}")
        fixes, errors = fix_conversations(closed_convs)
        all_fixes.extend(fixes)
        all_errors.extend(errors)

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")

    by_action = {}
    by_status = {}
    for fix in all_fixes:
        by_action[fix['action']] = by_action.get(fix['action'], 0) + 1
        by_status[fix['status']] = by_status.get(fix['status'], 0) + 1

    print(f"\nSuccessfully fixed: {len(all_fixes)}/{len(all_convs)}")

    if by_action:
        print(f"\nBy Action:")
        for action, count in sorted(by_action.items()):
            print(f"  {action}: {count}")

    if by_status:
        print(f"\nBy Status:")
        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")

    if all_errors:
        print(f"\nErrors: {len(all_errors)}")
        for error in all_errors[:10]:
            print(f"  FS:{error['fs_id']} - {error['reason'][:50]}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more")

    # Save results
    results = {
        'total_fixed': len(all_fixes),
        'total_errors': len(all_errors),
        'fixed': all_fixes,
        'errors': all_errors
    }

    with open('email_fix_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to email_fix_results.json")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
