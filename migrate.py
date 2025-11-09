"""
Full migration orchestrator for Help Scout to FreeScout.
Migrates all customers and conversations with progress tracking and error handling.
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.helpscout_client import HelpScoutClient, HelpScoutAPIError
from api.freescout_client import FreeScoutClient, FreeScoutAPIError
from mapping.mappers import (
    map_customer_to_freescout,
    map_conversation_to_freescout,
    map_thread_to_freescout,
    extract_tags,
    map_status
)
from utils.filters import (
    is_spam_conversation,
    filter_conversations,
    reorder_threads_for_attachments,
    count_threads_with_attachments
)


class MigrationOrchestrator:
    """Orchestrates the full migration from Help Scout to FreeScout."""

    def __init__(
        self,
        skip_spam: bool = True,
        max_conversations: int = None,
        resume_from: str = None,
        exclude_tags: List[str] = None,
        status_filter: str = 'all',
        exclude_status: List[str] = None,
        incremental: bool = False,
        modified_since: str = None
    ):
        """
        Initialize migration orchestrator.

        Args:
            skip_spam: Skip conversations marked as spam (default True)
            max_conversations: Optional limit on number of conversations to migrate
            resume_from: Optional path to resume file to continue previous migration
            exclude_tags: List of tags to exclude from migration (e.g., ['low-priority', 'spam'])
            status_filter: Filter by conversation status (active, closed, all, etc.)
            exclude_status: List of statuses to exclude (e.g., ['spam', 'closed'])
            incremental: If True, only sync conversations modified since last sync
            modified_since: Explicit ISO 8601 datetime to sync from (overrides incremental)
        """
        self.skip_spam = skip_spam
        self.max_conversations = max_conversations
        self.resume_from = resume_from
        self.exclude_tags = exclude_tags or []
        self.status_filter = status_filter
        self.exclude_status = exclude_status or []
        self.incremental = incremental
        self.modified_since_override = modified_since

        # Initialize clients
        self.hs_client = HelpScoutClient()
        self.fs_client = FreeScoutClient()

        # Migration state
        self.stats = {
            'customers_migrated': 0,
            'customers_skipped': 0,
            'conversations_migrated': 0,
            'conversations_updated': 0,  # NEW: track updates to existing conversations
            'conversations_skipped': 0,
            'threads_migrated': 0,
            'threads_added_to_existing': 0,  # NEW: track threads added to existing conversations
            'attachments_migrated': 0,
            'errors': [],
            'last_sync_time': None,
            'migration_start_time': None,
            'migration_end_time': None
        }

        # ID mappings (Help Scout ID -> FreeScout ID)
        self.customer_mapping = {}  # HS Customer ID -> FS Customer ID
        self.conversation_mapping = {}  # HS Conversation ID -> FS Conversation ID

        # Track processed conversations to avoid duplicates
        self.processed_hs_conversation_ids = set()

        # Cache of existing Help Scout IDs in FreeScout (from custom fields)
        # Changed from set to dict: HS ID -> FS Conversation object
        self.existing_helpscout_ids_in_freescout = {}

        # Progress file
        self.progress_file = project_root / 'migration_progress.json'

        # Load resume data if provided
        if resume_from and Path(resume_from).exists():
            self._load_progress(resume_from)

    def _load_progress(self, progress_file: str):
        """Load previous migration progress."""
        print(f"\nLoading progress from: {progress_file}")
        with open(progress_file, 'r') as f:
            data = json.load(f)
            loaded_stats = data.get('stats', {})
            # Merge loaded stats with defaults, ensuring new fields exist
            self.stats.update(loaded_stats)
            # Ensure all stat fields exist (for backward compatibility)
            for key in ['conversations_updated', 'threads_added_to_existing']:
                if key not in self.stats:
                    self.stats[key] = 0

            self.customer_mapping = {int(k): int(v) for k, v in data.get('customer_mapping', {}).items()}
            self.conversation_mapping = {int(k): int(v) for k, v in data.get('conversation_mapping', {}).items()}

            # Load processed conversation IDs
            processed_ids = data.get('processed_conversation_ids', [])
            self.processed_hs_conversation_ids = set(processed_ids)

        print(f"✓ Loaded progress:")
        print(f"  Conversations migrated: {self.stats['conversations_migrated']}")
        print(f"  Processed IDs tracked: {len(self.processed_hs_conversation_ids)}")
        if self.stats.get('last_sync_time'):
            print(f"  Last sync: {self.stats['last_sync_time']}")

    def _save_progress(self):
        """Save current migration progress."""
        data = {
            'stats': self.stats,
            'customer_mapping': self.customer_mapping,
            'conversation_mapping': self.conversation_mapping,
            'processed_conversation_ids': list(self.processed_hs_conversation_ids),
            'timestamp': datetime.now().isoformat()
        }
        with open(self.progress_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _build_existing_helpscout_ids_cache(self):
        """
        Build a cache of Help Scout IDs that already exist in FreeScout.
        Checks the Helpscout custom field on all existing conversations.
        Stores full conversation objects for use in incremental updates.
        """
        print("\n🔍 Checking for existing migrated conversations in FreeScout...")
        print("   (This prevents duplicates even if migration_progress.json is cleared)")

        page = 1
        total_found = 0

        try:
            while True:
                response = self.fs_client.get_conversations(page=page, page_size=50, status='all')
                conversations = response.get('_embedded', {}).get('conversations', [])

                if not conversations:
                    break

                for conv in conversations:
                    custom_fields = conv.get('customFields', [])
                    for field in custom_fields:
                        if field.get('name') == 'Helpscout' and field.get('value'):
                            try:
                                hs_id = int(field.get('value'))
                                # Store full conversation object, not just ID
                                self.existing_helpscout_ids_in_freescout[hs_id] = conv
                                total_found += 1
                            except (ValueError, TypeError):
                                pass  # Invalid Help Scout ID, skip

                # Check if there are more pages
                page_info = response.get('page', {})
                if page >= page_info.get('totalPages', 1):
                    break

                page += 1

        except Exception as e:
            print(f"   ⚠ Warning: Could not check existing conversations: {e}")
            print(f"   Will rely on migration_progress.json only")
            return

        if total_found > 0:
            print(f"   ✓ Found {total_found} already-migrated conversations in FreeScout")
        else:
            print(f"   ✓ No existing migrated conversations found (clean start)")
        print()

    def _create_thread_signature(self, thread: Dict) -> str:
        """
        Create a unique signature for a thread to detect duplicates.
        Uses timestamp + thread type + body to create unique identifier.

        Args:
            thread: Thread dictionary (Help Scout or FreeScout format)

        Returns:
            Unique signature string
        """
        created_at = thread.get('createdAt', '')
        thread_type = thread.get('type', '')
        # Handle both Help Scout (body) and FreeScout (text) formats
        body = thread.get('body', thread.get('text', ''))
        # Handle None body values safely
        if body is None:
            body = ''
        # Use first 200 chars of body + timestamp + type for signature
        return f"{created_at}:{thread_type}:{body[:200]}"

    def _get_new_threads(
        self,
        hs_threads: List[Dict],
        fs_threads: List[Dict]
    ) -> List[Dict]:
        """
        Identify Help Scout threads that don't exist in FreeScout.

        Args:
            hs_threads: List of Help Scout thread dicts
            fs_threads: List of FreeScout thread dicts

        Returns:
            List of NEW Help Scout threads to migrate
        """
        # Build set of existing thread signatures from FreeScout
        existing_signatures = {
            self._create_thread_signature(t) for t in fs_threads
        }

        # Find threads not in FreeScout
        new_threads = []
        for hs_thread in hs_threads:
            sig = self._create_thread_signature(hs_thread)
            if sig not in existing_signatures:
                new_threads.append(hs_thread)

        return new_threads

    def _update_existing_conversation(
        self,
        hs_conv: Dict,
        fs_conv: Dict
    ) -> bool:
        """
        Update an existing FreeScout conversation with new threads from Help Scout.

        Args:
            hs_conv: Help Scout conversation dict
            fs_conv: FreeScout conversation dict (from cache)

        Returns:
            True if update succeeded, False otherwise
        """
        conv_id = hs_conv.get('id')
        fs_conv_id = fs_conv.get('id')
        conv_subject = hs_conv.get('subject', '(No Subject)')

        print(f"\n  Updating existing conversation: {conv_subject} (HS ID: {conv_id}, FS ID: {fs_conv_id})")

        try:
            # 1. Get Help Scout threads (fetch early for email fallback and customer extraction)
            hs_threads = self.hs_client.get_conversation_threads(conv_id)
            if not hs_threads:
                print(f"    ⊘ No threads in Help Scout")
                return False

            # 2. Get customer info for thread creation
            customer_ref = hs_conv.get('primaryCustomer', hs_conv.get('customer'))
            if not customer_ref:
                # Try to extract customer email from threads if customer object is missing
                customer_email_from_threads = None
                for thread in hs_threads:
                    if thread.get('type') == 'customer':
                        created_by = thread.get('createdBy', {})
                        if created_by.get('email'):
                            customer_email_from_threads = created_by.get('email')
                            break

                if not customer_email_from_threads:
                    print(f"    ✗ No customer found and no email in threads")
                    return False

                # Create minimal customer object from thread data
                hs_customer = {
                    'id': None,
                    'emails': [customer_email_from_threads],
                    'firstName': None,
                    'lastName': None
                }
                customer_email = customer_email_from_threads
                customer_id = None
            else:
                # Handle both dict and non-dict customer references
                if isinstance(customer_ref, dict):
                    customer_id = customer_ref.get('id')
                else:
                    # If customer_ref is just an ID
                    customer_id = customer_ref

                if not customer_id:
                    print(f"    ✗ No customer ID found")
                    return False

                hs_customer = self.hs_client.get_customer(customer_id)
                if not hs_customer:
                    print(f"    ✗ Could not fetch customer data")
                    return False

                # Extract customer email (with thread fallback)
                customer_email = None
                emails = hs_customer.get('emails', [])
                if emails:
                    customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')
                else:
                    # Try to find email in threads (customer threads first, then any thread with email)
                    # First check customer-type threads
                    for thread in hs_threads:
                        if thread.get('type') == 'customer':
                            created_by = thread.get('createdBy', {})
                            if created_by.get('email'):
                                customer_email = created_by['email']
                                break

                    # If customer thread has no email, check all other threads
                    if not customer_email:
                        for thread in hs_threads:
                            created_by = thread.get('createdBy', {})
                            if created_by.get('email') and 'nowhere' not in created_by.get('email', '').lower():
                                customer_email = created_by['email']
                                break

                if not customer_email:
                    customer_email = f"helpscout.customer.{customer_id}@migration.local"

            # 3. Get FreeScout threads
            fs_threads = self.fs_client.get_conversation_threads(fs_conv_id)

            # 4. Identify new threads
            new_threads = self._get_new_threads(hs_threads, fs_threads)

            if not new_threads:
                print(f"    ⊘ No new threads to migrate (already up to date)")
                self.stats['conversations_skipped'] += 1
                return False

            print(f"    → Found {len(new_threads)} new threads to migrate")

            # 5. Add new threads (WITHOUT attachments - FreeScout API limitation)
            threads_added = 0
            for hs_thread in new_threads:
                # Skip attachment handling for add_thread (API limitation)
                fs_thread = map_thread_to_freescout(
                    hs_thread,
                    customer_email=customer_email,
                    attachments_data=None  # Attachments don't work in add_thread
                )

                self.fs_client.add_thread(fs_conv_id, fs_thread, imported=True)
                threads_added += 1
                self.stats['threads_migrated'] += 1
                self.stats['threads_added_to_existing'] += 1

            # 6. Update conversation status if it changed
            hs_status = map_status(hs_conv.get('status'))
            fs_status = fs_conv.get('status')

            if hs_status != fs_status:
                print(f"    → Updating status: {fs_status} → {hs_status}")
                update_data = {
                    'status': hs_status,
                    'byUser': 8  # Required by FreeScout API
                }

                # Re-apply assignee if it changed
                hs_assignee = hs_conv.get('assignee')
                if hs_assignee and hs_assignee.get('id'):
                    # Try to map the user ID (basic implementation)
                    fs_user_id = hs_assignee.get('id')  # In real scenario, map HS user to FS user
                    if fs_user_id:
                        update_data['assignTo'] = fs_user_id

                self.fs_client.update_conversation(fs_conv_id, update_data)

            print(f"    ✓ Updated conversation with {threads_added} new threads")
            self.stats['conversations_updated'] += 1

            return True

        except (HelpScoutAPIError, FreeScoutAPIError) as e:
            print(f"    ✗ API Error: {e}")
            self.stats['errors'].append({
                'type': 'conversation_update',
                'conversation_id': conv_id,
                'freescout_id': fs_conv_id,
                'error': str(e)
            })
            return False

        except Exception as e:
            import traceback
            print(f"    ✗ Unexpected Error: {e}")
            print(f"    Debug: {traceback.format_exc()}")
            self.stats['errors'].append({
                'type': 'conversation_update',
                'conversation_id': conv_id,
                'freescout_id': fs_conv_id,
                'error': str(e)
            })
            return False

    def _get_or_create_customer(self, hs_customer: Dict, customer_email: str) -> Optional[int]:
        """
        Get or create a customer in FreeScout.

        Args:
            hs_customer: Help Scout customer dictionary
            customer_email: Customer email address

        Returns:
            FreeScout customer ID, or None if failed
        """
        hs_customer_id = hs_customer.get('id')

        # Check if already migrated
        if hs_customer_id in self.customer_mapping:
            return self.customer_mapping[hs_customer_id]

        try:
            # Map customer data
            fs_customer_data = map_customer_to_freescout(hs_customer)
            fs_customer_data['email'] = customer_email

            # Check if customer already exists in FreeScout
            existing_customer = self.fs_client.search_customer_by_email(customer_email)
            if existing_customer:
                fs_customer_id = existing_customer['id']
                print(f"  ✓ Found existing customer: {customer_email} (ID: {fs_customer_id})")
            else:
                # Create new customer
                fs_customer = self.fs_client.create_customer(fs_customer_data)
                fs_customer_id = fs_customer['id']
                print(f"  ✓ Created customer: {customer_email} (ID: {fs_customer_id})")
                self.stats['customers_migrated'] += 1

            # Store mapping
            self.customer_mapping[hs_customer_id] = fs_customer_id
            return fs_customer_id

        except FreeScoutAPIError as e:
            print(f"  ✗ Failed to create customer: {e}")
            self.stats['errors'].append({
                'type': 'customer_creation',
                'customer_id': hs_customer_id,
                'error': str(e)
            })
            return None

    def _migrate_conversation(self, hs_conv: Dict) -> bool:
        """
        Migrate a single conversation from Help Scout to FreeScout.

        Args:
            hs_conv: Help Scout conversation dictionary

        Returns:
            True if migration succeeded, False otherwise
        """
        conv_id = hs_conv.get('id')
        conv_subject = hs_conv.get('subject', '(No Subject)')

        print(f"\n  Conversation: {conv_subject} (ID: {conv_id})")

        try:
            # Check if already processed in this run
            if conv_id in self.processed_hs_conversation_ids:
                print(f"    ⊘ Skipping - already processed in this run")
                self.stats['conversations_skipped'] += 1
                return False

            # Check if conversation exists in FreeScout - UPDATE it instead of skipping
            if conv_id in self.existing_helpscout_ids_in_freescout:
                # Conversation already exists - update it with new threads
                fs_conv = self.existing_helpscout_ids_in_freescout[conv_id]
                result = self._update_existing_conversation(hs_conv, fs_conv)
                if result:
                    self.processed_hs_conversation_ids.add(conv_id)
                return result

            # Check for spam
            if self.skip_spam and is_spam_conversation(hs_conv):
                print(f"    ⊘ Skipping - marked as spam")
                self.stats['conversations_skipped'] += 1
                return False

            # Get threads first (may contain customer email if customer object missing)
            hs_threads = self.hs_client.get_conversation_threads(conv_id)
            if not hs_threads:
                print(f"    ⊘ Skipping - no threads")
                self.stats['conversations_skipped'] += 1
                return False

            # Get customer (or create placeholder if missing)
            customer_ref = hs_conv.get('primaryCustomer', hs_conv.get('customer'))
            if not customer_ref:
                # Try to extract customer email from threads to use as customer identifier
                customer_email_from_threads = None
                for thread in hs_threads:
                    if thread.get('type') == 'customer':
                        created_by = thread.get('createdBy', {})
                        if created_by.get('email'):
                            customer_email_from_threads = created_by.get('email')
                            break

                if not customer_email_from_threads:
                    print(f"    ✗ No customer found and no email in threads")
                    self.stats['conversations_skipped'] += 1
                    return False

                # Create minimal customer object from thread data
                hs_customer = {
                    'id': None,
                    'emails': [customer_email_from_threads],
                    'firstName': None,
                    'lastName': None
                }
            else:
                customer_id = customer_ref.get('id')
                hs_customer = self.hs_client.get_customer(customer_id)

            # Handle attachments - reorder threads if needed
            attachment_count = count_threads_with_attachments(hs_threads)
            if attachment_count > 0:
                if attachment_count > 1:
                    print(f"    ⚠ {attachment_count} threads with attachments (only first will migrate)")

                hs_threads, was_reordered = reorder_threads_for_attachments(hs_threads)
                if was_reordered:
                    print(f"    ↻ Reordered threads for attachment migration")

            # Extract customer email
            customer_email = None
            emails = hs_customer.get('emails', [])
            if emails:
                customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')
            else:
                # Try to find email in threads (customer threads first, then any thread with email)
                # First check customer-type threads
                for thread in hs_threads:
                    if thread.get('type') == 'customer':
                        created_by = thread.get('createdBy', {})
                        if created_by.get('email'):
                            customer_email = created_by['email']
                            break

                # If customer thread has no email, check all other threads
                if not customer_email:
                    for thread in hs_threads:
                        created_by = thread.get('createdBy', {})
                        if created_by.get('email') and 'nowhere' not in created_by.get('email', '').lower():
                            customer_email = created_by['email']
                            break

            if not customer_email:
                customer_email = f"helpscout.customer.{customer_id}@migration.local"

            # Get or create customer in FreeScout
            fs_customer_id = self._get_or_create_customer(hs_customer, customer_email)
            if not fs_customer_id:
                print(f"    ✗ Customer creation failed")
                self.stats['conversations_skipped'] += 1
                return False

            # Prepare customer data for conversation
            customer_for_conversation = {
                "id": fs_customer_id,
                "email": customer_email,
                "first_name": hs_customer.get('firstName'),
                "last_name": hs_customer.get('lastName')
            }

            # Map first thread with attachments if present
            first_thread_attachments = hs_threads[0].get('_embedded', {}).get('attachments', [])
            attachments_data = None

            if first_thread_attachments:
                attachments_data = []
                total_size = 0

                for att in first_thread_attachments:
                    att_id = att.get('id')
                    filename = att.get('filename')
                    mime_type = att.get('mimeType')
                    att_size = att.get('size', 0)  # Size in bytes

                    # Check individual attachment size limit (40MB per attachment)
                    if att_size > 40 * 1024 * 1024:
                        print(f"      ⚠ Attachment {filename} too large ({att_size / 1024 / 1024:.1f}MB), skipping")
                        self.stats['errors'].append({
                            'type': 'attachment_too_large',
                            'conversation_id': conv_id,
                            'filename': filename,
                            'size_mb': att_size / 1024 / 1024
                        })
                        continue

                    try:
                        att_bytes = self.hs_client.download_attachment(conv_id, att_id)
                        att_bytes_size = len(att_bytes)
                        total_size += att_bytes_size

                        # Check total request size (45MB limit)
                        if total_size > 45 * 1024 * 1024:
                            print(f"      ⚠ Total attachment size exceeds limit, stopping at {total_size / 1024 / 1024:.1f}MB")
                            break

                        attachments_data.append({
                            'filename': filename,
                            'mimeType': mime_type,
                            'data_bytes': att_bytes
                        })
                        self.stats['attachments_migrated'] += 1
                    except Exception as e:
                        print(f"      ⚠ Failed to download attachment {filename}: {e}")
                        self.stats['errors'].append({
                            'type': 'attachment_download_failed',
                            'conversation_id': conv_id,
                            'filename': filename,
                            'error': str(e)
                        })

            fs_first_thread = map_thread_to_freescout(
                hs_threads[0],
                customer_email=customer_email,
                attachments_data=attachments_data if attachments_data else None
            )

            # Map conversation
            fs_conversation_data = map_conversation_to_freescout(
                hs_conv,
                customer_for_conversation,
                fs_first_thread
            )

            # Create conversation in FreeScout
            fs_conversation = self.fs_client.create_conversation(
                fs_conversation_data,
                imported=True
            )
            fs_conv_id = fs_conversation['id']
            print(f"    ✓ Created conversation #{fs_conversation.get('number')} (ID: {fs_conv_id})")

            self.stats['threads_migrated'] += 1  # First thread

            # Add remaining threads (attachments won't work in add_thread due to API limitation)
            for hs_thread in hs_threads[1:]:
                # Map thread WITHOUT attachments (FreeScout API limitation)
                fs_thread = map_thread_to_freescout(
                    hs_thread,
                    customer_email=customer_email,
                    attachments_data=None  # Attachments don't work in add_thread
                )

                self.fs_client.add_thread(fs_conv_id, fs_thread, imported=True)
                self.stats['threads_migrated'] += 1

            # Add tags
            tags = extract_tags(hs_conv)
            if tags:
                self.fs_client.update_conversation_tags(fs_conv_id, tags)

            # Update status and assignee after adding all threads
            # FreeScout auto-changes status based on last thread, so we need to fix it
            # Always update since we don't fetch the current status after adding threads
            final_updates = {}
            expected_status = map_status(hs_conv.get('status'))
            final_updates['status'] = expected_status

            # Re-apply assignee if it was set (might have been cleared)
            if fs_conversation_data.get('assignTo'):
                final_updates['assignTo'] = fs_conversation_data['assignTo']

            # Always update to ensure correct status
            final_updates['byUser'] = 8  # FreeScout requires byUser for updates
            self.fs_client.update_conversation(fs_conv_id, final_updates)

            # Set Help Scout ID and Number custom fields (requires Custom Fields module)
            try:
                hs_number = hs_conv.get('number')
                self.fs_client.update_custom_fields(fs_conv_id, [
                    {'id': 1, 'value': str(conv_id)},  # Helpscout_ID (conversation ID)
                    {'id': 2, 'value': str(hs_number) if hs_number else ''}  # Helpscout_No (ticket number)
                ])
            except Exception as e:
                # Don't fail migration if custom field update fails
                print(f"    ⚠ Could not set custom fields: {e}")

            print(f"    ✓ Migrated {len(hs_threads)} threads")
            self.stats['conversations_migrated'] += 1

            # Store conversation mapping and mark as processed
            self.conversation_mapping[conv_id] = fs_conv_id
            self.processed_hs_conversation_ids.add(conv_id)

            return True

        except (HelpScoutAPIError, FreeScoutAPIError) as e:
            print(f"    ✗ API Error: {e}")
            self.stats['errors'].append({
                'type': 'conversation_migration',
                'conversation_id': conv_id,
                'error': str(e)
            })
            return False

        except Exception as e:
            print(f"    ✗ Unexpected Error: {e}")
            self.stats['errors'].append({
                'type': 'conversation_migration',
                'conversation_id': conv_id,
                'error': str(e)
            })
            return False

    def migrate_all(self, mailbox_id: int = None):
        """
        Migrate all conversations from Help Scout to FreeScout using streaming/chunked processing.
        Processes one page at a time to reduce memory usage and enable crash recovery.

        Args:
            mailbox_id: Optional Help Scout mailbox ID to filter by
        """
        print("=" * 70)
        print("HELP SCOUT → FREESCOUT FULL MIGRATION")
        print("=" * 70)
        print(f"\nSettings:")
        print(f"  Status filter: {self.status_filter}")
        if self.exclude_status:
            print(f"  Exclude statuses: {', '.join(self.exclude_status)}")
        print(f"  Skip spam: {self.skip_spam}")
        if self.exclude_tags:
            print(f"  Exclude tags: {', '.join(self.exclude_tags)}")
        if self.max_conversations:
            print(f"  Max conversations: {self.max_conversations}")
        if mailbox_id:
            print(f"  Mailbox ID: {mailbox_id}")
        print("=" * 70)

        try:
            # Build cache of existing migrated conversations in FreeScout
            self._build_existing_helpscout_ids_cache()

            # Set migration start time
            if not self.stats.get('migration_start_time'):
                self.stats['migration_start_time'] = datetime.now().isoformat()

            # Determine modified_since parameter for incremental sync
            modified_since_param = None
            if self.modified_since_override:
                modified_since_param = self.modified_since_override
                print(f"\n  Incremental sync: Modified since {modified_since_param}")
            elif self.incremental and self.stats.get('last_sync_time'):
                modified_since_param = self.stats['last_sync_time']
                print(f"\n  Incremental sync: Modified since last sync ({modified_since_param})")
            elif self.incremental:
                print(f"\n  ⚠️ Incremental sync requested but no previous sync found")
                print(f"     Performing full sync instead")

            # Build status filter
            api_status = 'active' if self.skip_spam else self.status_filter

            print(f"\nFetching and migrating conversations (streaming mode)...")
            print(f"  API-level filters: status={api_status}, exclude_tags={self.exclude_tags or 'none'}")
            print("=" * 70)

            # Build query filters
            filters = {}
            query_parts = []

            if self.exclude_tags:
                for tag in self.exclude_tags:
                    query_parts.append(f'NOT tag:"{tag}"')

            if query_parts:
                filters['query'] = f'({" AND ".join(query_parts)})'

            # Create cache directory
            cache_dir = project_root / 'helpscout_cache'
            cache_dir.mkdir(exist_ok=True)

            # Streaming pagination - process page by page
            page = 1
            total_pages = None
            total_elements = None
            conversations_migrated_this_run = 0
            start_time = time.time()
            pages_cached = 0
            pages_fetched = 0

            while True:
                cache_file = cache_dir / f'conversations_page_{page:04d}.json'

                # Check if cache exists for this page
                if cache_file.exists():
                    print(f"\n📄 Page {page} - loading from cache...", end='', flush=True)
                    with open(cache_file, 'r') as f:
                        page_conversations = json.load(f)
                    pages_cached += 1
                    print(f" ({len(page_conversations)} conversations)")
                else:
                    print(f"\n📄 Page {page} - fetching from API...", end='', flush=True)
                    response = self.hs_client.get_conversations(
                        mailbox=mailbox_id,
                        status=api_status,
                        page=page,
                        modified_since=modified_since_param,
                        **filters
                    )

                    page_conversations = response.get('_embedded', {}).get('conversations', [])

                    if not page_conversations:
                        print(" (empty, done)")
                        break

                    # Save to cache
                    with open(cache_file, 'w') as f:
                        json.dump(page_conversations, f, indent=2)
                    pages_fetched += 1

                    # Get pagination info
                    page_info = response.get('page', {})
                    total_pages = page_info.get('totalPages', 1)
                    total_elements = page_info.get('totalElements', 0)

                    print(f" ({len(page_conversations)} conversations, page {page}/{total_pages})")

                if not page_conversations:
                    break

                # Filter out excluded statuses (client-side)
                if self.exclude_status:
                    page_conversations = [
                        c for c in page_conversations
                        if c.get('status') not in self.exclude_status
                    ]

                # Filter out already processed conversations
                page_conversations = [
                    c for c in page_conversations
                    if c.get('id') not in self.processed_hs_conversation_ids
                ]

                # Filter conversations (spam check, etc)
                to_migrate, skipped = filter_conversations(
                    page_conversations,
                    skip_spam=self.skip_spam,
                    verbose=False
                )

                # Migrate conversations from this page
                for hs_conv in to_migrate:
                    conversations_migrated_this_run += 1

                    # Check max limit
                    if self.max_conversations and conversations_migrated_this_run > self.max_conversations:
                        print(f"\n✓ Reached max conversations limit ({self.max_conversations})")
                        break

                    print(f"  [{conversations_migrated_this_run}] ", end='')
                    self._migrate_conversation(hs_conv)

                    # Save progress every 10 conversations
                    if conversations_migrated_this_run % 10 == 0:
                        self._save_progress()
                        elapsed = time.time() - start_time
                        rate = conversations_migrated_this_run / elapsed if elapsed > 0 else 0
                        print(f"\n    💾 Progress saved ({self.stats['conversations_migrated']} total). Rate: {rate:.2f} conv/sec")

                # Check if we've hit max limit
                if self.max_conversations and conversations_migrated_this_run >= self.max_conversations:
                    break

                # Move to next page
                # Check if there's a next page (either from API response or cache)
                next_cache = cache_dir / f'conversations_page_{page+1:04d}.json'
                if total_pages and page >= total_pages:
                    # We fetched from API and know there are no more pages
                    break
                elif not cache_file.exists() and not next_cache.exists():
                    # We fetched from API and this was the last page
                    break
                elif cache_file.exists() and not next_cache.exists():
                    # We loaded from cache and there's no next cached page
                    # Continue to fetch from API
                    pass

                page += 1

            # Final progress save with sync time
            self.stats['last_sync_time'] = datetime.now().isoformat()
            self.stats['migration_end_time'] = datetime.now().isoformat()
            self._save_progress()

            # Print summary
            elapsed = time.time() - start_time
            print(f"\n{'=' * 70}")
            print("MIGRATION COMPLETE")
            print("=" * 70)
            print(f"\nSummary:")
            print(f"  Customers migrated: {self.stats['customers_migrated']}")
            print(f"  Conversations migrated: {self.stats['conversations_migrated']}")
            print(f"  Conversations updated: {self.stats['conversations_updated']}")
            print(f"  Conversations skipped: {self.stats['conversations_skipped']}")
            print(f"  Threads migrated: {self.stats['threads_migrated']}")
            print(f"  Threads added to existing: {self.stats['threads_added_to_existing']}")
            print(f"  Attachments migrated: {self.stats['attachments_migrated']}")
            print(f"  Errors: {len(self.stats['errors'])}")
            print(f"\nCache Performance:")
            print(f"  Pages loaded from cache: {pages_cached}")
            print(f"  Pages fetched from API: {pages_fetched}")
            print(f"  Cache directory: {cache_dir}")
            print(f"\nTime elapsed: {elapsed/60:.1f} minutes")
            print(f"Progress saved to: {self.progress_file}")

            if self.stats['errors']:
                print(f"\n{'=' * 70}")
                print("ERRORS ENCOUNTERED")
                print("=" * 70)
                for error in self.stats['errors'][:10]:  # Show first 10 errors
                    print(f"\n  Type: {error['type']}")
                    if 'conversation_id' in error:
                        print(f"  Conversation ID: {error['conversation_id']}")
                    if 'customer_id' in error:
                        print(f"  Customer ID: {error['customer_id']}")
                    if 'filename' in error:
                        print(f"  Filename: {error['filename']}")
                    if 'size_mb' in error:
                        print(f"  Size: {error['size_mb']:.1f}MB")
                    if 'error' in error:
                        print(f"  Error: {error['error']}")

                if len(self.stats['errors']) > 10:
                    print(f"\n  ... and {len(self.stats['errors']) - 10} more errors")
                    print(f"  Check {self.progress_file} for full error list")

        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            self._save_progress()
            return False

        return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Migrate Help Scout data to FreeScout')
    parser.add_argument(
        '--mailbox',
        type=int,
        help='Help Scout mailbox ID to migrate (default: all mailboxes)'
    )
    parser.add_argument(
        '--max-conversations',
        type=int,
        help='Maximum number of conversations to migrate (for testing)'
    )
    parser.add_argument(
        '--include-spam',
        action='store_true',
        help='Include spam conversations (default: skip spam)'
    )
    parser.add_argument(
        '--exclude-tags',
        type=str,
        help='Comma-separated list of tags to exclude (e.g., "low-priority,internal-testing")'
    )
    parser.add_argument(
        '--status',
        type=str,
        default='all',
        choices=['active', 'closed', 'spam', 'all', 'pending', 'open'],
        help='Filter by conversation status (default: all)'
    )
    parser.add_argument(
        '--exclude-status',
        type=str,
        help='Comma-separated list of statuses to exclude (e.g., "spam,closed")'
    )
    parser.add_argument(
        '--resume',
        type=str,
        help='Resume from previous migration progress file'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Incremental sync: only migrate conversations modified since last sync'
    )
    parser.add_argument(
        '--modified-since',
        type=str,
        help='Only sync conversations modified since this datetime (ISO 8601, e.g., "2025-10-20T00:00:00Z")'
    )

    args = parser.parse_args()

    # Parse exclude_tags
    exclude_tags_list = None
    if args.exclude_tags:
        exclude_tags_list = [tag.strip() for tag in args.exclude_tags.split(',')]

    # Parse exclude_status
    exclude_status_list = None
    if args.exclude_status:
        exclude_status_list = [status.strip() for status in args.exclude_status.split(',')]

    print("\n" + "=" * 70)
    print("HELP SCOUT → FREESCOUT MIGRATION")
    print("=" * 70)
    print("\nThis will migrate all data from Help Scout to FreeScout.")
    print("Data includes: customers, conversations, threads, tags, and attachments.")
    print("\nWARNING: This will create data in FreeScout!")
    print("=" * 70)

    if not args.resume:
        response = input("\nContinue with migration? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("\n✗ Migration cancelled")
            return 1

    # Initialize orchestrator
    orchestrator = MigrationOrchestrator(
        skip_spam=not args.include_spam,
        max_conversations=args.max_conversations,
        resume_from=args.resume,
        exclude_tags=exclude_tags_list,
        status_filter=args.status,
        exclude_status=exclude_status_list,
        incremental=args.incremental,
        modified_since=args.modified_since
    )

    # Run migration
    result = orchestrator.migrate_all(mailbox_id=args.mailbox)

    if result:
        print("\n✓ Migration completed successfully!")
        return 0
    else:
        print("\n✗ Migration failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
