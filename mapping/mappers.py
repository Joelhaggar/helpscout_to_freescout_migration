"""
Data mapping functions to transform Help Scout data to FreeScout format.
"""
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional


# Load mapping files
project_root = Path(__file__).parent.parent
user_mapping_file = project_root / 'config' / 'user_mapping.json'
mailbox_mapping_file = project_root / 'config' / 'mailbox_mapping.json'

# Load user mapping
with open(user_mapping_file, 'r') as f:
    user_mapping_data = json.load(f)
    USER_MAPPING = {int(k): int(v) for k, v in user_mapping_data['mapping'].items()}

# Load mailbox mapping
with open(mailbox_mapping_file, 'r') as f:
    mailbox_mapping_data = json.load(f)
    MAILBOX_MAPPING = {int(k): int(v) for k, v in mailbox_mapping_data['mapping'].items()}


def map_customer_to_freescout(hs_customer: Dict) -> Dict:
    """
    Map Help Scout customer to FreeScout format.

    Args:
        hs_customer: Help Scout customer dictionary

    Returns:
        FreeScout customer data dictionary
    """
    # Extract primary email
    emails = hs_customer.get('emails', [])
    primary_email = None
    if emails:
        primary_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')

    # Extract primary phone
    phones = hs_customer.get('phones', [])
    primary_phone = None
    if phones:
        primary_phone = phones[0] if isinstance(phones[0], str) else phones[0].get('value')

    # Build FreeScout customer data
    fs_customer = {
        "firstName": hs_customer.get('firstName', ''),
        "lastName": hs_customer.get('lastName', ''),
    }

    # At least one of email or phone is required
    if primary_email:
        fs_customer['email'] = primary_email
    if primary_phone:
        fs_customer['phone'] = primary_phone

    # Optional fields
    if hs_customer.get('organization'):
        fs_customer['organization'] = hs_customer['organization']

    if hs_customer.get('jobTitle'):
        fs_customer['jobTitle'] = hs_customer['jobTitle']

    if hs_customer.get('photoUrl'):
        fs_customer['photoUrl'] = hs_customer['photoUrl']

    if hs_customer.get('background'):
        fs_customer['background'] = hs_customer['background']

    # Store additional emails as notes or in a custom field if needed
    if len(emails) > 1:
        additional_emails = [e if isinstance(e, str) else e.get('value') for e in emails[1:]]
        if fs_customer.get('background'):
            fs_customer['background'] += f"\n\nAdditional emails: {', '.join(additional_emails)}"
        else:
            fs_customer['background'] = f"Additional emails: {', '.join(additional_emails)}"

    return fs_customer


def map_status(hs_status: str) -> str:
    """
    Map Help Scout conversation status to FreeScout status.

    Args:
        hs_status: Help Scout status (active, closed, pending, spam)

    Returns:
        FreeScout status
    """
    status_map = {
        'active': 'active',
        'closed': 'closed',
        'pending': 'pending',  # FreeScout supports pending status
        'spam': 'spam',
        'open': 'active'
    }
    return status_map.get(hs_status, 'active')


def map_conversation_type(hs_type: str) -> str:
    """
    Map Help Scout conversation type to FreeScout type.

    Args:
        hs_type: Help Scout type (email, chat, phone)

    Returns:
        FreeScout type
    """
    type_map = {
        'email': 'email',
        'chat': 'chat',
        'phone': 'phone'
    }
    return type_map.get(hs_type, 'email')


def map_thread_type(hs_thread: Dict) -> str:
    """
    Map Help Scout thread type to FreeScout thread type.

    Args:
        hs_thread: Help Scout thread dictionary

    Returns:
        FreeScout thread type (customer, message, note)
    """
    hs_type = hs_thread.get('type', 'message')

    # Help Scout thread types: message, customer, note, lineitem, etc.
    if hs_type == 'customer':
        return 'customer'
    elif hs_type == 'note':
        return 'note'
    elif hs_type in ['message', 'reply']:
        return 'message'  # Agent reply
    else:
        # Default to note for other types (lineitem, etc.)
        return 'note'


def map_user_id(hs_user_id: int) -> Optional[int]:
    """
    Map Help Scout user ID to FreeScout user ID.

    Args:
        hs_user_id: Help Scout user ID

    Returns:
        FreeScout user ID or None if not found
    """
    return USER_MAPPING.get(hs_user_id)


def map_mailbox_id(hs_mailbox_id: int) -> Optional[int]:
    """
    Map Help Scout mailbox ID to FreeScout mailbox ID.

    Args:
        hs_mailbox_id: Help Scout mailbox ID

    Returns:
        FreeScout mailbox ID or None if not found
    """
    return MAILBOX_MAPPING.get(hs_mailbox_id)


def map_conversation_to_freescout(
    hs_conversation: Dict,
    fs_customer_data: Dict,
    initial_thread: Dict = None
) -> Dict:
    """
    Map Help Scout conversation to FreeScout format.

    Args:
        hs_conversation: Help Scout conversation dictionary
        fs_customer_data: FreeScout customer data (with id, email, first_name, last_name)
        initial_thread: Optional initial thread data (if not provided, will be empty)

    Returns:
        FreeScout conversation data dictionary
    """
    # Get mailbox ID - could be nested in 'mailbox' object or direct 'mailboxId' field
    mailbox_id = hs_conversation.get('mailboxId')
    if not mailbox_id and hs_conversation.get('mailbox'):
        mailbox_id = hs_conversation.get('mailbox', {}).get('id')

    fs_conversation = {
        "subject": hs_conversation.get('subject', '(No Subject)'),
        "mailboxId": map_mailbox_id(mailbox_id),
        "type": map_conversation_type(hs_conversation.get('type', 'email')),
        "status": map_status(hs_conversation.get('status', 'active')),
        "customer": fs_customer_data,
        "createdAt": hs_conversation.get('createdAt'),
        "threads": []
    }

    # Add closed timestamp if applicable
    if hs_conversation.get('closedAt'):
        fs_conversation['closedAt'] = hs_conversation['closedAt']

    # Add assigned user if exists
    assignee = hs_conversation.get('assignee')
    if assignee and assignee.get('id'):
        fs_user_id = map_user_id(assignee['id'])
        if fs_user_id:
            fs_conversation['assignTo'] = fs_user_id  # FreeScout uses 'assignTo' not 'assignedTo'

    # Add initial thread if provided
    if initial_thread:
        fs_conversation['threads'].append(initial_thread)

    return fs_conversation


def map_thread_to_freescout(
    hs_thread: Dict,
    customer_email: str = None,
    attachments_data: List[Dict] = None
) -> Dict:
    """
    Map Help Scout thread to FreeScout format.

    Args:
        hs_thread: Help Scout thread dictionary
        customer_email: Customer email (required for customer threads)
        attachments_data: Optional list of downloaded attachment data dicts
                         Each dict should have: {filename, mimeType, data_bytes}

    Returns:
        FreeScout thread data dictionary
    """
    thread_type = map_thread_type(hs_thread)

    # Get thread body - for line items, use action.text
    body = hs_thread.get('body', '')
    if not body and hs_thread.get('type') == 'lineitem':
        # Line items have action text instead of body
        action = hs_thread.get('action', {})
        body = action.get('text', '')

        # If it's markdown (like workflow names), keep it as-is
        # FreeScout will render it properly

    fs_thread = {
        "type": thread_type,
        "text": body if body else '(System action)',  # Fallback for empty line items
        "createdAt": hs_thread.get('createdAt')
    }

    # Add attachments if provided
    if attachments_data:
        fs_attachments = []
        for att_data in attachments_data:
            # Base64 encode the attachment data
            encoded_data = base64.b64encode(att_data['data_bytes']).decode('utf-8')
            fs_attachments.append({
                "fileName": att_data['filename'],
                "mimeType": att_data['mimeType'],
                "data": encoded_data
            })
        fs_thread['attachments'] = fs_attachments

    # Set created by based on thread type
    if thread_type == 'customer':
        # Customer thread
        fs_thread['customer'] = {"email": customer_email}
    else:
        # Agent thread (message or note)
        created_by = hs_thread.get('createdBy', {})
        hs_user_id = created_by.get('id')

        if hs_user_id:
            fs_user_id = map_user_id(hs_user_id)
            if fs_user_id:
                fs_thread['user'] = fs_user_id
            else:
                # User not found in mapping, use default (admin)
                fs_thread['user'] = 8  # Default to Joel
        else:
            fs_thread['user'] = 8  # Default to Joel

    return fs_thread


def extract_tags(hs_conversation: Dict) -> List[str]:
    """
    Extract tag names from Help Scout conversation.

    Args:
        hs_conversation: Help Scout conversation dictionary

    Returns:
        List of tag names
    """
    tags = hs_conversation.get('tags', [])
    if not tags:
        return []

    # Tags can be strings or objects with 'tag' property
    tag_names = []
    for tag in tags:
        if isinstance(tag, str):
            tag_names.append(tag)
        elif isinstance(tag, dict):
            tag_names.append(tag.get('tag', tag.get('name', '')))

    return [t for t in tag_names if t]  # Filter empty strings
