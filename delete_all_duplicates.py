"""
Delete ALL duplicate conversations from FreeScout.

Usage:
    python delete_all_duplicates.py --confirm
"""
import json
import sys
import argparse
from api.freescout_client import FreeScoutClient
from config.config import Config

def main():
    parser = argparse.ArgumentParser(description='Delete all duplicate conversations from FreeScout')
    parser.add_argument('--confirm', action='store_true', help='Confirm deletion (required)')
    args = parser.parse_args()

    # Load the list of duplicates to delete
    with open('all_duplicates_to_delete.json', 'r') as f:
        data = json.load(f)

    fs_ids = data['fs_ids']

    print(f'Found {len(fs_ids)} duplicate conversations to delete')
    print()

    if not args.confirm:
        print('ERROR: You must use --confirm flag to proceed with deletion')
        print(f'Command: python delete_all_duplicates.py --confirm')
        return 1

    print('Deleting conversations...')
    print('=' * 70)

    fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

    success = 0
    failed = 0

    for i, fs_id in enumerate(fs_ids, 1):
        try:
            # FreeScout uses DELETE /conversations/{id}
            fs_client._make_request('DELETE', f'/conversations/{fs_id}')
            success += 1
            if i % 100 == 0:
                print(f'  Deleted {i}/{len(fs_ids)}...')
        except Exception as e:
            failed += 1
            if failed <= 10:  # Only print first 10 errors
                print(f'  Failed to delete FS:{fs_id} - {e}')

    print()
    print('=' * 70)
    print('SUMMARY')
    print('=' * 70)
    print(f'Successfully deleted: {success}')
    print(f'Failed: {failed}')
    print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
