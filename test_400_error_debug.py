"""
Debug script to capture the actual FreeScout API error responses.
This will show us exactly what the API is rejecting.
"""
import json
import os
from pathlib import Path
from api.freescout_client import FreeScoutClient, FreeScoutAPIError

def test_single_conversation():
    """Test with a single conversation to capture error details."""
    fs_client = FreeScoutClient()
    project_root = Path(__file__).parent
    export_dir = project_root / 'helpscout_export'
    
    # Find the first conversation file
    conv_dir = export_dir / 'conversations'
    conv_files = list(conv_dir.rglob('conversation_*.json'))[:1]
    
    if not conv_files:
        print("No conversation files found")
        return
    
    conv_file = conv_files[0]
    print(f"Testing with: {conv_file}\n")
    
    with open(conv_file, 'r') as f:
        hs_conv = json.load(f)
    
    hs_conv_id = hs_conv.get('id')
    
    # Step 1: Create customer
    print("=" * 70)
    print("STEP 1: CREATE CUSTOMER")
    print("=" * 70)
    
    hs_customer = hs_conv.get('primaryCustomer') or hs_conv.get('_embedded', {}).get('customer', {})
    customer_email = hs_customer.get('email', f'no-email-conv-{hs_conv_id}@migration.local')
    customer_name_first = hs_customer.get('first', hs_customer.get('firstName', 'Unknown'))
    customer_name_last = hs_customer.get('last', hs_customer.get('lastName', ''))
    
    customer_data = {
        'firstName': customer_name_first,
        'lastName': customer_name_last,
        'email': customer_email
    }
    
    print(f"Customer data: {json.dumps(customer_data, indent=2)}\n")
    
    try:
        customer = fs_client.create_customer(customer_data)
        print(f"Created customer: {customer}\n")
        fs_customer_id = customer.get('id')
    except FreeScoutAPIError as e:
        print(f"ERROR: {e}")
        print(f"Status: {e.status_code}")
        print(f"Response: {e.response}\n")
        return
    
    # Step 2: Prepare conversation data with threads
    print("=" * 70)
    print("STEP 2: PREPARE CONVERSATION DATA")
    print("=" * 70)
    
    threads = hs_conv.get('_embedded', {}).get('threads', [])
    message_threads = [t for t in threads if t.get('type') == 'message']
    
    if not message_threads:
        # Fall back to customer-type threads
        message_threads = [t for t in threads if t.get('type') in ['message', 'customer']]
    
    print(f"Total threads: {len(threads)}")
    print(f"Message-type threads: {len(message_threads)}\n")
    
    if not message_threads:
        print("No message threads found - showing all thread types:")
        for i, t in enumerate(threads[:3]):
            print(f"  Thread {i}: type={t.get('type')}, has_text={bool(t.get('text'))}")
        return
    
    conv_data = {
        'subject': hs_conv.get('subject', '(No subject)'),
        'mailboxId': 1,
        'type': 'email',
        'status': hs_conv.get('status', 'closed'),
        'customerId': fs_customer_id,
        'createdAt': hs_conv.get('createdAt'),
        'imported': True,
        'threads': []
    }
    
    # Add first message thread
    first_thread = message_threads[0]
    print(f"First message thread data:")
    print(f"  type: {first_thread.get('type')}")
    print(f"  has text: {bool(first_thread.get('text'))}")
    print(f"  text length: {len(first_thread.get('text', ''))}")
    print(f"  has body: {bool(first_thread.get('body'))}")
    print(f"  createdBy type: {first_thread.get('createdBy', {}).get('type')}")
    print(f"  createdAt: {first_thread.get('createdAt')}\n")
    
    thread_data = {
        'type': first_thread.get('type', 'message'),
        'text': first_thread.get('text') or first_thread.get('body', ''),
        'createdAt': first_thread.get('createdAt'),
        'imported': True
    }
    
    # Handle created_by
    created_by = first_thread.get('createdBy', {})
    if created_by.get('type') == 'customer':
        thread_data['createdByCustomer'] = True
    else:
        thread_data['createdByUser'] = created_by.get('id')
    
    conv_data['threads'].append(thread_data)
    
    print("Conversation data to send:")
    print(json.dumps(conv_data, indent=2, default=str))
    print("\n")
    
    # Step 3: Create conversation
    print("=" * 70)
    print("STEP 3: CREATE CONVERSATION")
    print("=" * 70)
    print(f"Sending conversation creation request...\n")
    
    try:
        fs_conv = fs_client.create_conversation(conv_data, imported=True)
        print(f"SUCCESS: Created conversation {fs_conv}")
    except FreeScoutAPIError as e:
        print(f"FAILED with 400 error!")
        print(f"Status: {e.status_code}")
        print(f"Message: {e}")
        print(f"\nResponse body:")
        print(e.response)
        
        # Try to parse as JSON if possible
        try:
            error_data = json.loads(e.response)
            print(f"\nParsed error details:")
            print(json.dumps(error_data, indent=2))
        except:
            pass


if __name__ == '__main__':
    test_single_conversation()
