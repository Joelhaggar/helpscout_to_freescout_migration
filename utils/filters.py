"""
Filtering and utility functions for migration.
Helps determine which conversations should be migrated and prepares data.
"""
from typing import Dict, List, Tuple
from mapping.mappers import extract_tags


def is_spam_conversation(hs_conversation: Dict) -> bool:
    """
    Check if a Help Scout conversation is spam.

    Args:
        hs_conversation: Help Scout conversation dictionary

    Returns:
        True if conversation is spam, False otherwise
    """
    # Check status field
    status = hs_conversation.get('status', '').lower()
    if status == 'spam':
        return True

    # Check tags for spam
    tags = extract_tags(hs_conversation)
    if tags:
        tag_names_lower = [t.lower() for t in tags]
        if 'spam' in tag_names_lower:
            return True

    return False


def should_migrate_conversation(
    hs_conversation: Dict,
    skip_spam: bool = True,
    skip_statuses: List[str] = None
) -> tuple[bool, str]:
    """
    Determine if a conversation should be migrated.

    Args:
        hs_conversation: Help Scout conversation dictionary
        skip_spam: If True, skip conversations marked as spam (default True)
        skip_statuses: Optional list of statuses to skip (e.g., ['spam', 'deleted'])

    Returns:
        Tuple of (should_migrate: bool, reason: str)
        If should_migrate is False, reason explains why
    """
    # Check spam
    if skip_spam and is_spam_conversation(hs_conversation):
        return False, "Conversation is marked as spam"

    # Check specific statuses to skip
    if skip_statuses:
        status = hs_conversation.get('status', '').lower()
        if status in [s.lower() for s in skip_statuses]:
            return False, f"Conversation status is '{status}'"

    # Check if conversation has threads
    # Note: This requires fetching threads separately, so we can't check here
    # The caller should check for empty threads after fetching

    return True, ""


def filter_conversations(
    hs_conversations: List[Dict],
    skip_spam: bool = True,
    skip_statuses: List[str] = None,
    verbose: bool = False
) -> tuple[List[Dict], List[Dict]]:
    """
    Filter a list of conversations for migration.

    Args:
        hs_conversations: List of Help Scout conversation dictionaries
        skip_spam: If True, skip spam conversations (default True)
        skip_statuses: Optional list of statuses to skip
        verbose: If True, print filtering decisions

    Returns:
        Tuple of (conversations_to_migrate, skipped_conversations)
    """
    to_migrate = []
    skipped = []

    for conv in hs_conversations:
        should_migrate, reason = should_migrate_conversation(
            conv,
            skip_spam=skip_spam,
            skip_statuses=skip_statuses
        )

        if should_migrate:
            to_migrate.append(conv)
        else:
            skipped.append({
                'conversation': conv,
                'reason': reason
            })
            if verbose:
                print(f"  Skipping conversation {conv.get('id')}: {reason}")

    return to_migrate, skipped


def reorder_threads_for_attachments(threads: List[Dict]) -> Tuple[List[Dict], bool]:
    """
    Reorder threads to ensure thread with attachments is first.

    This is a workaround for FreeScout API limitation where attachments
    only work in the initial thread during conversation creation, but not
    when adding threads later via add_thread().

    Args:
        threads: List of Help Scout thread dictionaries

    Returns:
        Tuple of (reordered_threads, was_reordered)
        - reordered_threads: Threads with attachment thread moved to front if needed
        - was_reordered: True if threads were reordered, False otherwise
    """
    if not threads:
        return threads, False

    # Find first thread with attachments
    attachment_thread_index = None
    for i, thread in enumerate(threads):
        attachments = thread.get('_embedded', {}).get('attachments', [])
        if attachments:
            attachment_thread_index = i
            break

    # If no attachments or attachments already in first thread, no reordering needed
    if attachment_thread_index is None or attachment_thread_index == 0:
        return threads, False

    # Reorder: move attachment thread to front
    reordered = [threads[attachment_thread_index]] + threads[:attachment_thread_index] + threads[attachment_thread_index + 1:]
    return reordered, True


def count_threads_with_attachments(threads: List[Dict]) -> int:
    """
    Count how many threads have attachments.

    Args:
        threads: List of Help Scout thread dictionaries

    Returns:
        Number of threads that have one or more attachments
    """
    count = 0
    for thread in threads:
        attachments = thread.get('_embedded', {}).get('attachments', [])
        if attachments:
            count += 1
    return count
