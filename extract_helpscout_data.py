"""
Extract all Help Scout data (conversations, customers, attachments) to disk.

This script:
1. Extracts all conversations with full details (threads, attachments)
2. Extracts all customers
3. Saves everything in an organized directory structure
4. Tracks progress for incremental extraction
5. Avoids caching old data

Directory structure:
  helpscout_export/
    metadata.json               - Export metadata (timestamp, counts, etc)
    customers/
      customers_batch_001.json  - 50 customers per file
      customers_batch_002.json
      ...
    conversations/
      YEAR/MONTH/DAY/
        conversation_<id>.json  - Full conversation with threads
        conversation_<id>.json
      ...
    extraction_progress.json    - Tracks what's been extracted
"""
import json
import os
from pathlib import Path
from datetime import datetime
from api.helpscout_client import HelpScoutClient
import time

class HelpScoutExporter:
    """Extract Help Scout data to organized file structure."""

    def __init__(self):
        self.hs_client = HelpScoutClient()
        self.project_root = Path(__file__).parent
        self.export_dir = self.project_root / 'helpscout_export'
        self.progress_file = self.export_dir / 'extraction_progress.json'

        # Create directories
        self.export_dir.mkdir(exist_ok=True)
        (self.export_dir / 'customers').mkdir(exist_ok=True)
        (self.export_dir / 'conversations').mkdir(exist_ok=True)

        # Load progress
        self.progress = self._load_progress()

    def _load_progress(self) -> dict:
        """Load extraction progress."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'started': datetime.now().isoformat(),
            'last_updated': None,
            'customers': {
                'total_fetched': 0,
                'last_page': 0,
                'complete': False
            },
            'conversations': {
                'total_fetched': 0,
                'last_id': None,
                'complete': False
            },
            'errors': []
        }

    def _save_progress(self):
        """Save extraction progress."""
        self.progress['last_updated'] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def extract_customers(self):
        """Extract all customers from Help Scout."""
        print("\n" + "="*70)
        print("EXTRACTING CUSTOMERS")
        print("="*70)

        start_page = self.progress['customers']['last_page']
        if start_page > 0:
            print(f"Resuming from page {start_page + 1}...")

        page = start_page + 1
        batch_num = (self.progress['customers']['total_fetched'] // 50) + 1
        batch_customers = []
        total_customers = 0

        while True:
            try:
                print(f"  Fetching page {page}...", end='', flush=True)
                response = self.hs_client.get_customers(page=page, page_size=50)

                customers = response.get('_embedded', {}).get('customers', [])
                if not customers:
                    print(" (empty, done)")
                    break

                batch_customers.extend(customers)
                total_customers += len(customers)
                print(f" ({len(customers)} customers)")

                # Save batch when we have 50
                if len(batch_customers) >= 50:
                    self._save_customer_batch(batch_num, batch_customers[:50])
                    batch_customers = batch_customers[50:]
                    batch_num += 1
                    self.progress['customers']['total_fetched'] += 50

                # Check pagination
                page_info = response.get('page', {})
                if page >= page_info.get('totalPages', 1):
                    break

                page += 1
                self.progress['customers']['last_page'] = page - 1
                self._save_progress()
                time.sleep(0.5)  # Rate limit

            except Exception as e:
                print(f" ERROR: {e}")
                self.progress['errors'].append({
                    'type': 'customer_extraction',
                    'page': page,
                    'error': str(e)
                })
                self._save_progress()
                break

        # Save remaining customers
        if batch_customers:
            self._save_customer_batch(batch_num, batch_customers)
            self.progress['customers']['total_fetched'] += len(batch_customers)

        self.progress['customers']['complete'] = True
        self._save_progress()

        print(f"\n✓ Extracted {self.progress['customers']['total_fetched']} customers")

    def _save_customer_batch(self, batch_num: int, customers: list):
        """Save a batch of customers."""
        batch_file = self.export_dir / 'customers' / f'customers_batch_{batch_num:03d}.json'
        with open(batch_file, 'w') as f:
            json.dump(customers, f, indent=2)
        print(f"    → Saved {batch_file.name}")

    def extract_conversations(self):
        """Extract all conversations with full details."""
        print("\n" + "="*70)
        print("EXTRACTING CONVERSATIONS")
        print("="*70)

        last_id = self.progress['conversations']['last_id']
        page = 1
        total_fetched = 0
        errors = 0

        while True:
            try:
                print(f"  Fetching page {page}...", end='', flush=True)
                response = self.hs_client.get_conversations(page=page, page_size=50)

                conversations = response.get('_embedded', {}).get('conversations', [])
                if not conversations:
                    print(" (empty, done)")
                    break

                print(f" ({len(conversations)} conversations)")

                for conv in conversations:
                    conv_id = conv.get('id')

                    # Skip if already extracted
                    if last_id and conv_id <= last_id:
                        continue

                    try:
                        # Fetch full conversation with threads
                        full_conv = self.hs_client.get_conversation(conv_id, embed='threads')

                        # Save to date-organized structure
                        created_at = full_conv.get('createdAt', datetime.now().isoformat())
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

                        conv_dir = self.export_dir / 'conversations' / f'{dt.year}/{dt.month:02d}/{dt.day:02d}'
                        conv_dir.mkdir(parents=True, exist_ok=True)

                        conv_file = conv_dir / f'conversation_{conv_id}.json'
                        with open(conv_file, 'w') as f:
                            json.dump(full_conv, f, indent=2)

                        self.progress['conversations']['last_id'] = conv_id
                        total_fetched += 1

                        if total_fetched % 10 == 0:
                            print(f"    Saved {total_fetched} conversations")
                            self._save_progress()

                        time.sleep(0.5)  # Rate limit

                    except Exception as e:
                        errors += 1
                        self.progress['errors'].append({
                            'type': 'conversation_extraction',
                            'conversation_id': conv_id,
                            'error': str(e)
                        })
                        print(f"    ✗ Failed to extract conversation {conv_id}: {e}")

                # Check pagination
                page_info = response.get('page', {})
                if page >= page_info.get('totalPages', 1):
                    break

                page += 1
                self._save_progress()

            except Exception as e:
                print(f" ERROR: {e}")
                self.progress['errors'].append({
                    'type': 'page_fetch',
                    'page': page,
                    'error': str(e)
                })
                break

        self.progress['conversations']['complete'] = True
        self.progress['conversations']['total_fetched'] = total_fetched
        self._save_progress()

        print(f"\n✓ Extracted {total_fetched} conversations ({errors} errors)")

    def create_manifest(self):
        """Create export manifest."""
        print("\n" + "="*70)
        print("CREATING MANIFEST")
        print("="*70)

        # Count files
        customer_files = list((self.export_dir / 'customers').glob('*.json'))
        conv_files = list((self.export_dir / 'conversations').rglob('*.json'))

        manifest = {
            'export_date': datetime.now().isoformat(),
            'export_location': str(self.export_dir),
            'summary': {
                'total_customers': self.progress['customers']['total_fetched'],
                'total_conversations': self.progress['conversations']['total_fetched'],
                'customer_files': len(customer_files),
                'conversation_files': len(conv_files),
                'total_errors': len(self.progress['errors'])
            },
            'status': {
                'customers_complete': self.progress['customers']['complete'],
                'conversations_complete': self.progress['conversations']['complete']
            }
        }

        manifest_file = self.export_dir / 'manifest.json'
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)

        print(f"\nManifest Summary:")
        print(f"  Customers: {manifest['summary']['total_customers']}")
        print(f"  Conversations: {manifest['summary']['total_conversations']}")
        print(f"  Files: {len(customer_files) + len(conv_files)}")
        print(f"  Errors: {manifest['summary']['total_errors']}")

    def run(self, extract_customers=True, extract_conversations=True):
        """Run full extraction."""
        print(f"\n{'='*70}")
        print("HELP SCOUT DATA EXTRACTION")
        print(f"{'='*70}")
        print(f"Export directory: {self.export_dir}")

        try:
            if extract_customers:
                self.extract_customers()

            if extract_conversations:
                self.extract_conversations()

            self.create_manifest()

            print(f"\n{'='*70}")
            print("✅ EXTRACTION COMPLETE")
            print(f"{'='*70}")

        except KeyboardInterrupt:
            print("\n\n⚠️  Extraction interrupted by user")
            self._save_progress()
            print(f"Progress saved to {self.progress_file}")
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            self._save_progress()


if __name__ == '__main__':
    exporter = HelpScoutExporter()
    exporter.run()
