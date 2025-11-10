"""
Test import of most recent 300 conversations into FreeScout.

This script imports only the 300 most recent conversations to verify:
1. Customers are created/mapped correctly
2. Conversation statuses are preserved
3. Assignment looks correct
4. Attachments are included (if available)

Does NOT import the full dataset - for verification only.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from api.freescout_client import FreeScoutClient
from mapping.mappers import map_customer_to_freescout, map_conversation_to_freescout, map_thread_to_freescout, map_status, map_user_id, extract_tags
import time

class TestImporter:
    """Test import of recent conversations only."""

    def __init__(self, export_dir: str = None):
        self.fs_client = FreeScoutClient()
        self.project_root = Path(__file__).parent
        self.export_dir = Path(export_dir) if export_dir else self.project_root / 'helpscout_export'
        self.attachments_dir = self.project_root / 'helpscout_attachments'
        self.attachment_manifest_file = self.attachments_dir / 'manifest.json'

        if not self.export_dir.exists():
            raise FileNotFoundError(f"Export directory not found: {self.export_dir}")

        self.customer_map = {}  # Map HS customer ID -> FS customer ID
        self.attachment_manifest = self._load_attachment_manifest()
        self.test_results = {
            'total_imported': 0,
            'with_attachments': 0,
            'errors': [],
            'imported_conversations': []
        }

    def _load_attachment_manifest(self) -> dict:
        """Load attachment manifest."""
        if self.attachment_manifest_file.exists():
            with open(self.attachment_manifest_file, 'r') as f:
                return json.load(f)
        return {'conversations': {}}

    def _get_most_recent_300_conversations(self):
        """Find the 300 most recent conversations."""
        conv_dir = self.export_dir / 'conversations'
        if not conv_dir.exists():
            return []

        # Collect all conversation files with their timestamps
        conv_files = []
        for conv_file in conv_dir.rglob('conversation_*.json'):
            with open(conv_file, 'r') as f:
                conv_data = json.load(f)
            created_at = conv_data.get('createdAt', '')
            conv_files.append((conv_file, created_at, conv_data.get('id')))

        # Sort by creation date, most recent first
        conv_files.sort(key=lambda x: x[1], reverse=True)

        return [f[0] for f in conv_files[:300]]

    def _get_attachments_for_conversation(self, conv_id: int) -> list:
        """Get all attachments for a conversation."""
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
        """Prepare attachments for import (read files as raw bytes for mapper to encode)."""
        prepared = []

        for att in attachments:
            local_path = att.get('local_path')
            if not local_path:
                continue

            full_path = self.project_root / local_path

            if not full_path.exists():
                continue

            try:
                with open(full_path, 'rb') as f:
                    file_content = f.read()

                # Return raw bytes - mapper will handle base64 encoding
                # Use the format expected by map_thread_to_freescout()
                prepared.append({
                    'filename': att.get('filename', 'attachment'),
                    'mimeType': att.get('mimeType', 'application/octet-stream'),
                    'data_bytes': file_content  # Raw bytes, not base64 encoded
                })
            except Exception as e:
                pass  # Skip files that can't be read

        return prepared

    def import_test_conversations(self):
        """Import only the most recent 300 conversations."""
        print("\n" + "="*70)
        print("TEST IMPORT: MOST RECENT 300 CONVERSATIONS")
        print("="*70)

        conv_files = self._get_most_recent_300_conversations()
        print(f"\nFound {len(conv_files)} most recent conversation files\n")

        imported = 0
        with_attachments = 0

        for i, conv_file in enumerate(conv_files, 1):
            try:
                with open(conv_file, 'r') as f:
                    hs_conv = json.load(f)

                hs_conv_id = hs_conv.get('id')

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

                if hs_customer_id and hs_customer_id in self.customer_map:
                    fs_customer_id = self.customer_map[hs_customer_id]
                else:
                    # Extract email and name
                    customer_email = None
                    customer_name_first = 'Unknown'
                    customer_name_last = ''

                    # Try primaryCustomer email field first (from conversation)
                    if 'email' in hs_customer:
                        customer_email = hs_customer.get('email')
                        customer_name_first = hs_customer.get('first', hs_customer.get('firstName', 'Unknown'))
                        customer_name_last = hs_customer.get('last', hs_customer.get('lastName', ''))
                    else:
                        # Try _embedded.emails (Help Scout API structure)
                        emails = hs_customer.get('_embedded', {}).get('emails', []) if hs_customer else []
                        if emails:
                            customer_email = emails[0].get('value') if isinstance(emails[0], dict) else emails[0]
                            customer_name_first = hs_customer.get('firstName', 'Unknown') if hs_customer else 'Unknown'
                            customer_name_last = hs_customer.get('lastName', '') if hs_customer else ''

                    # If no email from customer, try to extract from first thread
                    if not customer_email:
                        threads = hs_conv.get('_embedded', {}).get('threads', [])
                        if threads:
                            first_thread = threads[0]
                            created_by = first_thread.get('createdBy', {})
                            customer_email = created_by.get('email', '')
                            if customer_email:
                                # Extract name from creator if available
                                customer_name_first = created_by.get('name', 'Unknown')
                                customer_name_last = ''

                    # Create or find customer
                    if customer_email and '@migration.local' not in customer_email:
                        existing = self.fs_client.search_customer_by_email(customer_email)
                        if existing:
                            fs_customer_id = existing['id']
                            if hs_customer_id:
                                self.customer_map[hs_customer_id] = fs_customer_id
                        else:
                            # Create new customer
                            new_customer = self.fs_client.create_customer({
                                'firstName': customer_name_first,
                                'lastName': customer_name_last,
                                'email': customer_email
                            })
                            fs_customer_id = new_customer.get('id')
                            if hs_customer_id:
                                self.customer_map[hs_customer_id] = fs_customer_id
                    else:
                        # Create with fallback email using conversation ID as unique identifier
                        fallback_email = f'no-email-conv-{hs_conv_id}@migration.local'
                        new_customer = self.fs_client.create_customer({
                            'firstName': customer_name_first,
                            'lastName': customer_name_last,
                            'email': fallback_email
                        })
                        fs_customer_id = new_customer.get('id')
                        if hs_customer_id:
                            self.customer_map[hs_customer_id] = fs_customer_id

                # Prepare conversation data
                threads = hs_conv.get('_embedded', {}).get('threads', [])

                # Filter to only message type threads
                message_threads = [t for t in threads if t.get('type') == 'message']

                # Skip conversations with no message threads
                if not message_threads:
                    self.test_results['errors'].append({
                        'hs_id': hs_conv_id,
                        'error': 'No message threads found (only lineitem/note)'
                    })
                    continue

                # Get attachments FROM THE FIRST MESSAGE THREAD only (following migrate.py pattern)
                first_thread_attachments = message_threads[0].get('_embedded', {}).get('attachments', [])
                prepared_attachments = None

                if first_thread_attachments:
                    # Use the manifest to get local paths for these attachments
                    conv_manifest = self.attachment_manifest.get('conversations', {}).get(str(hs_conv_id), {})
                    first_thread_id = str(message_threads[0].get('id'))
                    thread_attachments_from_manifest = conv_manifest.get(first_thread_id, [])

                    if thread_attachments_from_manifest:
                        prepared_attachments = self._prepare_attachments_for_import(thread_attachments_from_manifest)
                        if prepared_attachments:
                            with_attachments += 1

                has_attachments = prepared_attachments is not None

                # Get customer email for thread mapping
                customer_email = None
                if customer_email is None and hs_customer:
                    emails = hs_customer.get('_embedded', {}).get('emails', []) if hs_customer.get('_embedded') else hs_customer.get('emails', [])
                    if emails:
                        customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')

                # Build first thread with mapper - INCLUDING attachments in the initial thread (ONLY place they work)
                first_message_thread = message_threads[0]
                initial_thread_data = map_thread_to_freescout(
                    first_message_thread,
                    customer_email=customer_email,
                    attachments_data=prepared_attachments  # Include attachments in initial thread ONLY
                )

                # Build conversation data using the proper mapper function
                # Prepare customer data with all required fields
                customer_for_conversation = {
                    'id': fs_customer_id,
                    'email': customer_email,
                    'first_name': hs_customer.get('firstName'),
                    'last_name': hs_customer.get('lastName')
                }

                conv_data = map_conversation_to_freescout(
                    hs_conv,
                    customer_for_conversation,
                    initial_thread_data
                )

                # Create conversation (attachments are included in initial thread)
                fs_conv = self.fs_client.create_conversation(conv_data, imported=True)

                # Add remaining message threads (WITHOUT attachments - FreeScout API limitation)
                for remaining_thread in message_threads[1:]:
                    thread_data = map_thread_to_freescout(remaining_thread, customer_email=customer_email)
                    self.fs_client.add_thread(fs_conv.get('id'), thread_data, imported=True)

                # Update status and assignment after adding threads
                # FreeScout may auto-change status based on last thread, so we re-apply correct status
                final_updates = {}
                expected_status = map_status(hs_conv.get('status'))
                final_updates['status'] = expected_status

                # Re-apply assignee if it was set (might have been cleared when threads added)
                if conv_data.get('assignTo'):
                    final_updates['assignTo'] = conv_data['assignTo']

                # Always include byUser for updates
                final_updates['byUser'] = 8

                # Apply final updates
                self.fs_client.update_conversation(fs_conv.get('id'), final_updates)

                # Store Help Scout ID and conversation number in custom fields
                try:
                    hs_number = hs_conv.get('number', '')
                    self.fs_client.update_custom_fields(
                        fs_conv.get('id'),
                        [
                            {'id': 1, 'value': str(hs_conv_id)},  # Helpscout_ID
                            {'id': 2, 'value': str(hs_number) if hs_number else ''}  # Helpscout_No
                        ]
                    )
                except:
                    pass

                # Record this conversation for verification
                self.test_results['imported_conversations'].append({
                    'hs_id': hs_conv_id,
                    'fs_id': fs_conv.get('id'),
                    'customer_email': hs_customer.get('_embedded', {}).get('emails', [{}])[0].get('value', 'no-email') if hs_customer.get('_embedded', {}).get('emails') else 'no-email',
                    'status': hs_conv.get('status', 'closed'),
                    'subject': hs_conv.get('subject', '(No subject)')[:50],
                    'has_attachments': has_attachments
                })

                imported += 1

                if imported % 50 == 0:
                    print(f"  [{imported:3d}/300] Imported {imported} conversations ({with_attachments} with attachments)...")

            except Exception as e:
                self.test_results['errors'].append({
                    'hs_id': hs_conv_id,
                    'error': str(e)[:100]
                })
                print(f"  ✗ Failed to import conversation {hs_conv_id}: {str(e)[:60]}")

        self.test_results['total_imported'] = imported
        self.test_results['with_attachments'] = with_attachments

        print(f"\n{'='*70}")
        print("TEST IMPORT COMPLETE")
        print(f"{'='*70}")
        print(f"Conversations imported: {imported}")
        print(f"With attachments: {with_attachments}")
        print(f"Errors: {len(self.test_results['errors'])}")

        if self.test_results['errors']:
            print(f"\nFirst 5 errors:")
            for error in self.test_results['errors'][:5]:
                print(f"  HS:{error['hs_id']} - {error['error']}")

        return self.test_results

    def show_sample_results(self):
        """Show sample of imported conversations for verification."""
        print(f"\n{'='*70}")
        print("SAMPLE RESULTS (First 10 imported conversations)")
        print(f"{'='*70}\n")

        for conv in self.test_results['imported_conversations'][:10]:
            email = conv['customer_email'] if conv['customer_email'] != 'no-email' else 'no-email (Facebook)'
            att = '📎' if conv['has_attachments'] else '  '
            print(f"{att} FS:{conv['fs_id']:5d} | {conv['status']:7s} | {email:30s} | {conv['subject']}")

        print(f"\nTotal imported for inspection: {len(self.test_results['imported_conversations'])}")


if __name__ == '__main__':
    try:
        importer = TestImporter()
        results = importer.import_test_conversations()
        importer.show_sample_results()

        # Save results
        with open('test_import_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to test_import_results.json")

    except KeyboardInterrupt:
        print("\n\nTest import interrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
