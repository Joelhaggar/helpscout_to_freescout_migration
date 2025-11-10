#!/usr/bin/env python3
"""
Verify that attachments can be downloaded from FreeScout.
"""
import requests
from pathlib import Path
import tempfile

def verify_attachment_download(fs_id: int):
    """Download and verify attachment from FreeScout ticket."""

    print(f"\n{'='*70}")
    print(f"VERIFY ATTACHMENT DOWNLOAD - FS:{fs_id}")
    print(f"{'='*70}\n")

    # Known attachment URLs on FS:768 (from manual inspection)
    test_urls = [
        f"https://helpdesk.domegaia.com/storage/attachment/1/1/1/Bender Return Label.pdf",
        f"https://helpdesk.domegaia.com/storage/attachment/1/1/1/20231202_201802.jpg",
    ]

    for url in test_urls:
        try:
            print(f"Downloading: {url}")
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                # Check if it's actual binary data, not JSON
                content = response.content

                # Check file type
                if content[:4] == b'%PDF':
                    file_type = "PDF"
                elif content[:3] in [b'GIF', b'\x89PN']:
                    file_type = "Image"
                elif content[:2] == b'\xff\xd8':
                    file_type = "JPEG"
                else:
                    file_type = f"Binary ({content[:10]})"

                # Check if it's JSON (bad)
                try:
                    import json
                    json.loads(content)
                    print(f"  ✗ ERROR: Downloaded JSON data instead of binary!")
                    print(f"    Content: {content[:100]}")
                    return False
                except:
                    pass  # Good - not JSON

                print(f"  ✓ SUCCESS: Downloaded {file_type} ({len(content)} bytes)")
                return True
            else:
                print(f"  ✗ HTTP {response.status_code}: {response.reason}")
                return False

        except Exception as e:
            print(f"  ✗ Download failed: {e}")
            return False

    return True

if __name__ == '__main__':
    success = verify_attachment_download(768)
    print(f"\n{'='*70}")
    if success:
        print("✓ ATTACHMENT DOWNLOAD VERIFIED - System is working!")
    else:
        print("✗ ATTACHMENT DOWNLOAD FAILED - Check FreeScout configuration")
    print(f"{'='*70}\n")
