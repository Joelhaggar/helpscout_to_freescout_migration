"""
Import Help Scout data from disk exports into FreeScout with attachments.

This script:
1. Reads extracted Help Scout data from disk
2. Uses pre-downloaded attachments from the attachment manifest
3. Creates/updates customers
4. Creates conversations with threads and attachments on first thread
5. Tracks import progress for resumability
6. Has NO rate limiting (local API)

Key limitation: FreeScout only allows attachments on the first thread
during conversation creation. All attachments are included in the first
thread, regardless of which thread they originally came from in Help Scout.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from api.freescout_client import FreeScoutClient
import time

class ExportImporter:
    """Import Help Scout data exports into FreeScout with attachments."""

    def __init__(self, export_dir: str = None):
        self.fs_client = FreeScoutClient()
        self.project_root = Path(__file__).parent
        self.export_dir = Path(export_dir) if export_dir else self.project_root / 'helpscout_export'
        self.attachments_dir = self.project_root / 'helpscout_attachments'
        self.import_progress_file = self.export_dir / 'import_progress.json'
        self.attachment_manifest_file = self.attachments_dir / 'manifest.json'

        if not self.export_dir.exists():
            raise FileNotFoundError(f"Export directory not found: {self.export_dir}")

        self.progress = self._load_progress()
        self.customer_map = {}  # Map HS customer ID -> FS customer ID
        self.attachment_manifest = self._load_attachment_manifest()

    def _load_progress(self) -> dict:
        """Load import progress."""
        if self.import_progress_file.exists():
            with open(self.import_progress_file, 'r') as f:
                return json.load(f)
        return {
            'started': datetime.now().isoformat(),
            'last_updated': None,
            'customers': {
                'total_imported': 0,
                'last_batch': 0,
                'complete': False
            },
            'conversations': {
                'total_imported': 0,
                'total_with_attachments': 0,
                'last_imported_id': None,
                'complete': False
            },
            'errors': []
        }

    def _save_progress(self):
        """Save import progress."""
        self.progress['last_updated'] = datetime.now().isoformat()
        with open(self.import_progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def _load_attachment_manifest(self) -> dict:
        """Load attachment manifest."""
        if self.attachment_manifest_file.exists():
            with open(self.attachment_manifest_file, 'r') as f:
                return json.load(f)
        return {'conversations': {}}

    def _get_attachments_for_conversation(self, conv_id: int) -> list:
        """Get all attachments for a conversation, organized by first thread."""
        conv_manifest = self.attachment_manifest.get('conversations', {}).get(str(conv_id), {})

        if not conv_manifest:
            return []

        # Get all attachments from all threads
        all_attachments = []
        for thread_id, attachments in conv_manifest.items():
            if isinstance(attachments, list):
                all_attachments.extend(attachments)

        return all_attachments

    def _prepare_attachments_for_import(self, attachments: list) -> list:
        """Prepare attachments for import (read files and encode if needed)."""
        prepared = []

        for att in attachments:
            local_path = att.get('local_path')
            if not local_path:
                continue

            full_path = self.project_root / local_path

            if not full_path.exists():
                print(f"    ⚠️  Attachment file missing: {local_path}")
                continue

            try:
                # Read file and prepare for upload
                with open(full_path, 'rb') as f:
                    file_content = f.read()

                prepared.append({
                    'filename': att.get('filename', 'attachment'),
                    'mimeType': att.get('mimeType', 'application/octet-stream'),
                    'content': file_content,
                    'size': len(file_content)
                })
            except Exception as e:
                print(f"    ✗ Failed to read attachment {local_path}: {e}")

        return prepared

    def import_customers(self):
        """Import customers from disk."""
        print("\n" + "="*70)
        print("IMPORTING CUSTOMERS")
        print("="*70)

        customers_dir = self.export_dir / 'customers'
        if not customers_dir.exists():
            print("✗ No customers directory found")
            return

        batch_files = sorted(customers_dir.glob('customers_batch_*.json'))
        start_batch = self.progress['customers']['last_batch']

        for batch_file in batch_files:
            # Extract batch number
            batch_num = int(batch_file.stem.split('_')[-1])

            if batch_num <= start_batch:
                continue

            print(f"\nImporting {batch_file.name}...", end='', flush=True)

            with open(batch_file, 'r') as f:
                customers = json.load(f)

            imported = 0
            for customer in customers:
                try:
                    hs_customer_id = customer.get('id')

                    # Extract email from _embedded.emails (Help Scout API structure)
                    email = None
                    emails = customer.get('_embedded', {}).get('emails', [])
                    if emails:
                        # emails is a list of dicts with 'value' field
                        email = emails[0].get('value') if isinstance(emails[0], dict) else emails[0]

                    if email:
                        existing = self.fs_client.search_customer_by_email(email)
                        if existing:
                            self.customer_map[hs_customer_id] = existing['id']
                            continue

                    # Create new customer
                    customer_data = {
                        'firstName': customer.get('firstName', 'Unknown'),
                        'lastName': customer.get('lastName', ''),
                        'email': email or f'no-email-{hs_customer_id}@migration.local'
                    }

                    fs_customer = self.fs_client.create_customer(customer_data)
                    self.customer_map[hs_customer_id] = fs_customer.get('id')
                    imported += 1

                except Exception as e:
                    self.progress['errors'].append({
                        'type': 'customer_import',
                        'hs_id': hs_customer_id,
                        'error': str(e)
                    })

            print(f" ✓ ({imported} new customers)")
            self.progress['customers']['total_imported'] += imported
            self.progress['customers']['last_batch'] = batch_num
            self._save_progress()

        self.progress['customers']['complete'] = True
        self._save_progress()
        print(f"\n✓ Customer import complete ({self.progress['customers']['total_imported']} total)")

    def import_conversations(self):
        """Import conversations from disk with attachments."""
        print("\n" + "="*70)
        print("IMPORTING CONVERSATIONS WITH ATTACHMENTS")
        print("="*70)

        conv_dir = self.export_dir / 'conversations'
        if not conv_dir.exists():
            print("✗ No conversations directory found")
            return

        # Find all conversation files
        conv_files = sorted(conv_dir.rglob('conversation_*.json'))
        last_imported = self.progress['conversations']['last_imported_id']

        print(f"Found {len(conv_files)} conversation files to import")

        imported = 0
        with_attachments = 0

        for i, conv_file in enumerate(conv_files, 1):
            try:
                with open(conv_file, 'r') as f:
                    hs_conv = json.load(f)

                hs_conv_id = hs_conv.get('id')

                # Skip if already imported
                if last_imported and hs_conv_id <= last_imported:
                    continue

                # Skip spam conversations
                if hs_conv.get('status') == 'spam':
                    continue

                # Skip conversations with Ignore or Low priority tags
                tags = hs_conv.get('tags', [])
                skip_tags = ['ignore', 'low priority']
                has_skip_tag = any(tag.get('tag', '').lower() in skip_tags for tag in tags)
                if has_skip_tag:
                    continue

                # Get/create customer - Try primaryCustomer first, then _embedded.customer
                hs_customer = hs_conv.get('primaryCustomer') or hs_conv.get('_embedded', {}).get('customer', {})
                hs_customer_id = hs_customer.get('id')

                if hs_customer_id in self.customer_map:
                    fs_customer_id = self.customer_map[hs_customer_id]
                else:
                    # Extract email and name
                    customer_email = None
                    customer_first_name = 'Unknown'
                    customer_last_name = ''

                    # Try primaryCustomer email field first
                    if 'email' in hs_customer:
                        customer_email = hs_customer.get('email')
                        customer_first_name = hs_customer.get('first', hs_customer.get('firstName', 'Unknown'))
                        customer_last_name = hs_customer.get('last', hs_customer.get('lastName', ''))
                    else:
                        # Try _embedded.emails (Help Scout API structure)
                        emails = hs_customer.get('_embedded', {}).get('emails', [])
                        if emails:
                            customer_email = emails[0].get('value') if isinstance(emails[0], dict) else emails[0]
                            customer_first_name = hs_customer.get('firstName', 'Unknown')
                            customer_last_name = hs_customer.get('lastName', '')

                    if customer_email:
                        existing = self.fs_client.search_customer_by_email(customer_email)
                        if existing:
                            fs_customer_id = existing['id']
                            self.customer_map[hs_customer_id] = fs_customer_id
                        else:
                            # Create new customer
                            new_customer = self.fs_client.create_customer({
                                'firstName': customer_first_name,
                                'lastName': customer_last_name,
                                'email': customer_email
                            })
                            fs_customer_id = new_customer.get('id')
                            self.customer_map[hs_customer_id] = fs_customer_id
                    else:
                        raise ValueError(f"No customer email found for conversation {hs_conv_id}")

                # Prepare conversation data
                threads = hs_conv.get('_embedded', {}).get('threads', [])

                # Filter to only message type threads
                message_threads = [t for t in threads if t.get('type') == 'message']

                # Skip conversations with no message threads
                if not message_threads:
                    self.progress['errors'].append({
                        'type': 'conversation_import',
                        'hs_id': hs_conv_id,
                        'error': 'No message threads found (only lineitem/note)'
                    })
                    continue

                # Get attachments for this conversation
                attachments_for_conv = self._get_attachments_for_conversation(hs_conv_id)
                has_attachments = len(attachments_for_conv) > 0

                if has_attachments:
                    prepared_attachments = self._prepare_attachments_for_import(attachments_for_conv)
                    if prepared_attachments:
                        print(f"  [{i:5d}] Conv {hs_conv_id}: Found {len(prepared_attachments)} attachments")
                        with_attachments += 1
                else:
                    prepared_attachments = None

                # Build conversation data with correct FreeScout API format
                conv_data = {
                    'subject': hs_conv.get('subject', '(No subject)'),
                    'mailboxId': 4,  # Support mailbox ID in FreeScout
                    'type': 'email',
                    'status': hs_conv.get('status', 'closed'),
                    'customer': {'id': fs_customer_id},  # FreeScout API requires 'customer' object
                    'user': 8,  # FreeScout API requires 'user' parameter for conversation creation
                    'createdAt': hs_conv.get('createdAt'),
                    'imported': True,
                    'threads': []
                }

                # Add threads
                for thread_idx, thread in enumerate(threads):
                    thread_data = {
                        'type': thread.get('type', 'message'),
                        'text': thread.get('body', thread.get('text', '')),
                        'createdAt': thread.get('createdAt'),
                        'imported': True
                    }

                    # Handle created_by
                    created_by = thread.get('createdBy', {})
                    if created_by.get('type') == 'customer':
                        thread_data['createdByCustomer'] = True
                    else:
                        thread_data['createdByUser'] = created_by.get('id')

                    # Add attachments ONLY to first thread
                    if thread_idx == 0 and has_attachments and prepared_attachments:
                        thread_data['attachments'] = prepared_attachments

                    conv_data['threads'].append(thread_data)

                # Create conversation
                fs_conv = self.fs_client.create_conversation(conv_data, imported=True)

                # Store Help Scout ID in custom field if available
                try:
                    self.fs_client.update_custom_fields(
                        fs_conv.get('id'),
                        [{'id': 1, 'value': str(hs_conv_id)}]
                    )
                except:
                    pass  # Custom fields might not be configured

                self.progress['conversations']['last_imported_id'] = hs_conv_id
                imported += 1

                if imported % 50 == 0:
                    print(f"  Imported {imported} conversations ({with_attachments} with attachments)...")
                    self._save_progress()

            except Exception as e:
                self.progress['errors'].append({
                    'type': 'conversation_import',
                    'hs_id': hs_conv_id,
                    'file': str(conv_file),
                    'error': str(e)
                })
                print(f"  ✗ Failed to import {conv_file.name}: {str(e)[:80]}")

        self.progress['conversations']['complete'] = True
        self.progress['conversations']['total_imported'] = imported
        self.progress['conversations']['total_with_attachments'] = with_attachments
        self._save_progress()

        print(f"\n✓ Conversation import complete:")
        print(f"  Total conversations: {imported}")
        print(f"  With attachments: {with_attachments}")

    def run(self, import_customers=True, import_conversations=True):
        """Run full import."""
        print(f"\n{'='*70}")
        print("HELP SCOUT DATA IMPORT TO FREESCOUT (WITH ATTACHMENTS)")
        print(f"{'='*70}")
        print(f"Import from: {self.export_dir}")
        print(f"Attachments from: {self.attachments_dir}")
        print(f"Attachments available: {len(self.attachment_manifest.get('conversations', {}))}")

        try:
            if import_customers:
                self.import_customers()

            if import_conversations:
                self.import_conversations()

            print(f"\n{'='*70}")
            print("✅ IMPORT COMPLETE")
            print(f"{'='*70}")
            print(f"Customers: {self.progress['customers']['total_imported']}")
            print(f"Conversations: {self.progress['conversations']['total_imported']}")
            print(f"With attachments: {self.progress['conversations']['total_with_attachments']}")
            print(f"Errors: {len(self.progress['errors'])}")

            if self.progress['errors']:
                print(f"\nFirst 5 errors:")
                for error in self.progress['errors'][:5]:
                    print(f"  - {error.get('type')}: {error.get('error')[:60]}")

        except KeyboardInterrupt:
            print("\n\n⚠️  Import interrupted by user")
            self._save_progress()
            print(f"Progress saved to {self.import_progress_file}")
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            self._save_progress()


if __name__ == '__main__':
    importer = ExportImporter()
    importer.run()
