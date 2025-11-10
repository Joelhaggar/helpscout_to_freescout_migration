"""
Download all Help Scout attachments to local storage.

This script:
1. Scans all extracted conversation JSON files
2. Identifies attachment URLs
3. Downloads attachments from Help Scout API
4. Stores them locally organized by conversation
5. Creates a manifest for quick import reference
6. Supports resumable downloads (tracks progress)

Directory structure:
  attachments/
    [conversation_id]/
      [thread_id]/
        [filename]  (the actual file)
    manifest.json   (mapping of conv_id -> thread_id -> attachments)
"""
import json
import os
import base64
from pathlib import Path
from datetime import datetime
import requests
from api.helpscout_client import HelpScoutClient
import time

class AttachmentDownloader:
    """Download and organize Help Scout attachments."""

    def __init__(self, export_dir: str = None):
        self.hs_client = HelpScoutClient()
        self.project_root = Path(__file__).parent
        self.export_dir = Path(export_dir) if export_dir else self.project_root / 'helpscout_export'
        self.attachments_dir = self.project_root / 'helpscout_attachments'
        self.manifest_file = self.attachments_dir / 'manifest.json'
        self.progress_file = self.attachments_dir / 'download_progress.json'

        # Create directories
        self.attachments_dir.mkdir(exist_ok=True)

        # Load progress
        self.progress = self._load_progress()
        self.manifest = self._load_manifest()

    def _load_progress(self) -> dict:
        """Load download progress."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'started': datetime.now().isoformat(),
            'last_updated': None,
            'conversations_processed': 0,
            'total_attachments_downloaded': 0,
            'total_attachments_failed': 0,
            'errors': []
        }

    def _save_progress(self):
        """Save download progress."""
        self.progress['last_updated'] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def _load_manifest(self) -> dict:
        """Load attachment manifest."""
        if self.manifest_file.exists():
            with open(self.manifest_file, 'r') as f:
                return json.load(f)
        return {
            'created': datetime.now().isoformat(),
            'conversations': {}
        }

    def _save_manifest(self):
        """Save attachment manifest."""
        with open(self.manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def download_file(self, url: str, local_path: Path) -> bool:
        """
        Download a file from URL to local path.

        Args:
            url: URL to download from (Help Scout API URL)
            local_path: Path to save file to

        Returns:
            True if successful, False if failed
        """
        try:
            # Add authentication header for Help Scout API URLs
            headers = {}
            if 'api.helpscout.net' in url:
                headers = self.hs_client._get_headers()

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Ensure directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle Help Scout API response format
            # The API returns JSON-wrapped responses with base64-encoded data
            file_content = response.content

            try:
                # Try to parse as JSON first
                json_response = response.json()
                if isinstance(json_response, dict) and 'data' in json_response:
                    # This is a JSON-wrapped response with base64 data
                    # Decode the base64 data to get the actual file content
                    file_content = base64.b64decode(json_response['data'])
            except (json.JSONDecodeError, ValueError, TypeError):
                # Not JSON or doesn't have 'data' field, use raw content as-is
                pass

            # Write file
            with open(local_path, 'wb') as f:
                f.write(file_content)

            return True
        except Exception as e:
            print(f"✗ Failed to download {url}: {e}")
            return False

    def process_conversation(self, conv_file: Path) -> dict:
        """
        Process a conversation file and download all attachments.

        Args:
            conv_file: Path to conversation JSON file

        Returns:
            Dictionary with attachment info for this conversation
        """
        try:
            with open(conv_file, 'r') as f:
                conv = json.load(f)

            conv_id = conv.get('id')
            conv_dir = self.attachments_dir / str(conv_id)
            conv_manifest = {}

            threads = conv.get('_embedded', {}).get('threads', [])

            for thread in threads:
                thread_id = thread.get('id')
                attachments = thread.get('_embedded', {}).get('attachments', [])

                if not attachments:
                    continue

                thread_dir = conv_dir / str(thread_id)
                thread_manifest = []

                for att in attachments:
                    att_id = att.get('id')
                    filename = att.get('filename', f'attachment_{att_id}')
                    download_url = att.get('_links', {}).get('data', {}).get('href')

                    if not download_url:
                        print(f"  ✗ No download URL for attachment {att_id}")
                        self.progress['total_attachments_failed'] += 1
                        continue

                    local_file = thread_dir / filename

                    # Skip if already downloaded
                    if local_file.exists():
                        print(f"  ✓ Already downloaded: {filename}")
                        thread_manifest.append({
                            'id': att_id,
                            'filename': filename,
                            'size': att.get('size'),
                            'mimeType': att.get('mimeType'),
                            'local_path': str(local_file.relative_to(self.project_root))
                        })
                        continue

                    # Download file
                    if self.download_file(download_url, local_file):
                        print(f"  ✓ Downloaded: {filename} ({local_file.stat().st_size} bytes)")
                        thread_manifest.append({
                            'id': att_id,
                            'filename': filename,
                            'size': att.get('size'),
                            'mimeType': att.get('mimeType'),
                            'local_path': str(local_file.relative_to(self.project_root))
                        })
                        self.progress['total_attachments_downloaded'] += 1
                    else:
                        self.progress['total_attachments_failed'] += 1

                    # Rate limit
                    time.sleep(0.1)

                if thread_manifest:
                    conv_manifest[str(thread_id)] = thread_manifest

            return conv_manifest

        except Exception as e:
            print(f"✗ Error processing {conv_file}: {e}")
            self.progress['errors'].append({
                'file': str(conv_file),
                'error': str(e)
            })
            return {}

    def run(self):
        """Download all attachments from extracted conversations."""
        print("=" * 70)
        print("HELP SCOUT ATTACHMENT DOWNLOADER")
        print("=" * 70)
        print(f"Download directory: {self.attachments_dir}\n")

        # Find all conversation files
        conv_dir = self.export_dir / 'conversations'
        if not conv_dir.exists():
            print("✗ No conversations directory found")
            return

        conv_files = sorted(conv_dir.rglob('conversation_*.json'))
        print(f"Found {len(conv_files)} conversation files\n")

        print("Downloading attachments...\n")

        for i, conv_file in enumerate(conv_files, 1):
            conv_id = int(conv_file.stem.split('_')[-1])

            # Skip if already processed
            if str(conv_id) in self.manifest['conversations']:
                print(f"[{i:5d}/{len(conv_files)}] Conversation {conv_id} - already processed")
                continue

            print(f"[{i:5d}/{len(conv_files)}] Processing conversation {conv_id}...")
            conv_manifest = self.process_conversation(conv_file)

            if conv_manifest:
                self.manifest['conversations'][str(conv_id)] = conv_manifest

            self.progress['conversations_processed'] += 1

            # Save progress every 50 conversations
            if i % 50 == 0:
                self._save_progress()
                self._save_manifest()
                print(f"  Progress saved...")

        # Final save
        self._save_progress()
        self._save_manifest()

        # Summary
        print(f"\n{'='*70}")
        print("DOWNLOAD COMPLETE")
        print(f"{'='*70}")
        print(f"Conversations processed: {self.progress['conversations_processed']}")
        print(f"Attachments downloaded: {self.progress['total_attachments_downloaded']}")
        print(f"Download failures: {self.progress['total_attachments_failed']}")
        print(f"Errors: {len(self.progress['errors'])}")
        print(f"\nAttachments saved to: {self.attachments_dir}")
        print(f"Manifest saved to: {self.manifest_file}")

        if self.progress['errors']:
            print(f"\nFirst 5 errors:")
            for error in self.progress['errors'][:5]:
                print(f"  - {error['file']}: {error['error']}")

if __name__ == '__main__':
    downloader = AttachmentDownloader()
    downloader.run()
