"""
Download an attachment from FreeScout and inspect its content.
"""
import sys
import requests
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config import Config


def download_attachment(file_url: str):
    """Download and inspect attachment from FreeScout."""
    print("=" * 70)
    print("DOWNLOAD FREESCOUT ATTACHMENT")
    print("=" * 70)

    try:
        print(f"\nURL: {file_url}")

        # Download the file
        print("\nDownloading...")
        headers = {
            'X-FreeScout-API-Key': Config.FREESCOUT_API_KEY
        }

        response = requests.get(file_url, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"✗ Download failed: HTTP {response.status_code}")
            print(f"  Response: {response.text[:500]}")
            return False

        content = response.content
        print(f"✓ Downloaded {len(content)} bytes")

        # Check if it's a PDF
        if content[:4] == b'%PDF':
            print("✓ File is a valid PDF")
        else:
            print("✗ File is NOT a valid PDF")
            print(f"  First 100 bytes (text): {content[:100]}")
            print(f"  First 100 bytes (hex): {content[:100].hex()}")

            # Check if it looks like Base64
            try:
                text = content.decode('utf-8', errors='ignore')
                if text.startswith('JVB'):  # Base64 for '%PDF'
                    print("\n⚠ File appears to be Base64-encoded text!")
                    print(f"  First 100 chars: {text[:100]}")

                    # Try to decode it
                    import base64
                    try:
                        decoded = base64.b64decode(text)
                        print(f"\n  Attempting Base64 decode...")
                        print(f"  Decoded size: {len(decoded)} bytes")

                        if decoded[:4] == b'%PDF':
                            print("  ✓ Decoded content is a valid PDF!")
                            print("\n  THIS IS THE ISSUE: FreeScout stored the Base64 string instead of decoding it")

                            # Save the correctly decoded file
                            output_file = project_root / 'decoded_attachment.pdf'
                            with open(output_file, 'wb') as f:
                                f.write(decoded)
                            print(f"\n  Saved correctly decoded PDF to: {output_file}")

                    except Exception as e:
                        print(f"  ✗ Base64 decode failed: {e}")
            except Exception as e:
                print(f"  Could not decode as text: {e}")

        # Save the downloaded file for inspection
        output_file = project_root / 'downloaded_attachment'
        with open(output_file, 'wb') as f:
            f.write(content)
        print(f"\nSaved downloaded file to: {output_file}")

        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_freescout_attachment.py <file_url>")
        print("Example: python download_freescout_attachment.py 'http://localhost:8000/storage/attachment/4/4/1/Inv00032844.pdf?id=1&token=357d97b1dda0f343f832529730c0443f'")
        sys.exit(1)

    file_url = sys.argv[1]
    sys.exit(0 if download_attachment(file_url) else 1)
