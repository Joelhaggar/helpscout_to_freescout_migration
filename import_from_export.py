"""
Import Help Scout data from disk exports into FreeScout.

This script:
1. Reads extracted Help Scout data from disk
2. Creates/updates customers
3. Creates conversations with threads and attachments
4. Tracks import progress for resumability
5. Has NO rate limiting (local API)
"""
import json
import os
from pathlib import Path
from datetime import datetime
from api.freescout_client import FreeScoutClient
import time

class ExportImporter:
    """Import Help Scout data exports into FreeScout."""

    def __init__(self, export_dir: str = None):
        self.fs_client = FreeScoutClient()
        self.project_root = Path(__file__).parent
        self.export_dir = Path(export_dir) if export_dir else self.project_root / 'helpscout_export'
        self.import_progress_file = self.export_dir / 'import_progress.json'

        if not self.export_dir.exists():
            raise FileNotFoundError(f"Export directory not found: {self.export_dir}")

        self.progress = self._load_progress()
        self.customer_map = {}  # Map HS customer ID -> FS customer ID

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

                    # Check if customer already exists in FreeScout
                    email = customer.get('emails', [None])[0] if customer.get('emails') else None
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
        """Import conversations from disk."""
        print("\n" + "="*70)
        print("IMPORTING CONVERSATIONS")
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
        for i, conv_file in enumerate(conv_files, 1):
            try:
                with open(conv_file, 'r') as f:
                    hs_conv = json.load(f)

                hs_conv_id = hs_conv.get('id')

                # Skip if already imported
                if last_imported and hs_conv_id <= last_imported:
                    continue

                # Get/create customer
                hs_customer = hs_conv.get('_embedded', {}).get('customer', {})
                hs_customer_id = hs_customer.get('id')

                if hs_customer_id in self.customer_map:
                    fs_customer_id = self.customer_map[hs_customer_id]
                else:
                    # Try to find existing customer by email
                    customer_email = hs_customer.get('emails', [None])[0]
                    if customer_email:
                        existing = self.fs_client.search_customer_by_email(customer_email)
                        if existing:
                            fs_customer_id = existing['id']
                            self.customer_map[hs_customer_id] = fs_customer_id
                        else:
                            # Create new customer
                            new_customer = self.fs_client.create_customer({
                                'firstName': hs_customer.get('firstName', 'Unknown'),
                                'lastName': hs_customer.get('lastName', ''),
                                'email': customer_email
                            })
                            fs_customer_id = new_customer.get('id')
                            self.customer_map[hs_customer_id] = fs_customer_id
                    else:
                        raise ValueError(f"No customer email found for conversation {hs_conv_id}")

                # Prepare conversation data
                threads = hs_conv.get('_embedded', {}).get('threads', [])

                conv_data = {
                    'subject': hs_conv.get('subject', '(No subject)'),
                    'mailboxId': 1,  # TODO: Map this from config
                    'type': 'email',
                    'status': hs_conv.get('status', 'closed'),
                    'customerId': fs_customer_id,
                    'createdAt': hs_conv.get('createdAt'),
                    'imported': True,
                    'threads': []
                }

                # Add threads
                for thread in threads:
                    thread_data = {
                        'type': thread.get('type', 'message'),
                        'text': thread.get('text', ''),
                        'createdAt': thread.get('createdAt'),
                        'imported': True
                    }

                    # Handle created_by
                    created_by = thread.get('createdBy', {})
                    if created_by.get('type') == 'customer':
                        thread_data['createdByCustomer'] = True
                    else:
                        thread_data['createdByUser'] = created_by.get('id')

                    # Add attachments if present
                    attachments = thread.get('_embedded', {}).get('attachments', [])
                    if attachments:
                        thread_data['attachments'] = attachments

                    conv_data['threads'].append(thread_data)

                # Create conversation
                fs_conv = self.fs_client.create_conversation(conv_data, imported=True)

                # Store Help Scout ID in custom field if available
                self.fs_client.update_custom_fields(
                    fs_conv.get('id'),
                    [{'id': 1, 'value': str(hs_conv_id)}]
                )

                self.progress['conversations']['last_imported_id'] = hs_conv_id
                imported += 1

                if imported % 50 == 0:
                    print(f"  Imported {imported} conversations...")
                    self._save_progress()

            except Exception as e:
                self.progress['errors'].append({
                    'type': 'conversation_import',
                    'hs_id': hs_conv_id,
                    'file': str(conv_file),
                    'error': str(e)
                })
                print(f"  ✗ Failed to import {conv_file.name}: {e}")

        self.progress['conversations']['complete'] = True
        self.progress['conversations']['total_imported'] = imported
        self._save_progress()

        print(f"\n✓ Conversation import complete ({imported} conversations)")

    def run(self, import_customers=True, import_conversations=True):
        """Run full import."""
        print(f"\n{'='*70}")
        print("HELP SCOUT DATA IMPORT TO FREESCOUT")
        print(f"{'='*70}")
        print(f"Import from: {self.export_dir}")

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
            print(f"Errors: {len(self.progress['errors'])}")

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
