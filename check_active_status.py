"""
Check all active conversations in FreeScout against Help Scout cache
to find status mismatches.
"""
from api.freescout_client import FreeScoutClient
from config.config import Config
import json
from pathlib import Path

fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

# Load Help Scout cache
print('Loading Help Scout cache...')
hs_conversations = {}
cache_dir = Path('helpscout_cache')
for cache_file in sorted(cache_dir.glob('conversations_page_*.json')):
    with open(cache_file, 'r') as f:
        conversations = json.load(f)
        for conv in conversations:
            hs_conversations[conv['id']] = conv
print(f'Loaded {len(hs_conversations)} conversations from cache')

# Load mapping
with open('migration_progress.json', 'r') as f:
    data = json.load(f)
    mapping = data.get('conversation_mapping', {})

# Reverse mapping (FreeScout ID -> Help Scout ID)
reverse_mapping = {int(fs_id): int(hs_id) for hs_id, fs_id in mapping.items()}
print(f'Loaded {len(reverse_mapping)} conversation mappings')
print()

# Fetch ALL active conversations from FreeScout
print('Fetching ALL active conversations from FreeScout...')
all_active_fs = []
page = 1

while True:
    try:
        response = fs_client._make_request('GET', '/conversations', params={'page': page, 'status': 'active'})
        conversations = response.get('_embedded', {}).get('conversations', [])

        if not conversations:
            break

        all_active_fs.extend(conversations)
        page += 1

        if page % 10 == 0:
            print(f'  Fetched {len(all_active_fs)} so far...')

    except Exception as e:
        print(f'Error on page {page}: {e}')
        break

print(f'Found {len(all_active_fs)} active conversations in FreeScout')
print()

# Check each one against Help Scout cache
mismatches = []
not_in_cache = []
not_in_mapping = []

for fs_conv in all_active_fs:
    fs_id = fs_conv.get('id')
    fs_assignee = fs_conv.get('assignee', {}).get('id') if fs_conv.get('assignee') else None

    # Find Help Scout ID
    hs_id = reverse_mapping.get(fs_id)

    if not hs_id:
        not_in_mapping.append({'fs_id': fs_id, 'subject': fs_conv.get('subject', '')[:50]})
        continue

    # Find in cache
    if hs_id not in hs_conversations:
        not_in_cache.append({'fs_id': fs_id, 'hs_id': hs_id, 'subject': fs_conv.get('subject', '')[:50]})
        continue

    hs_conv = hs_conversations[hs_id]
    hs_status = hs_conv.get('status')

    if hs_status != 'active':
        mismatches.append({
            'fs_id': fs_id,
            'hs_id': hs_id,
            'fs_status': 'active',
            'hs_status': hs_status,
            'fs_assignee': fs_assignee,
            'hs_assignee': hs_conv.get('assignee', {}).get('id') if hs_conv.get('assignee') else None,
            'subject': fs_conv.get('subject', '')[:60]
        })

print('=' * 70)
print('RESULTS')
print('=' * 70)
print(f'Total active in FreeScout: {len(all_active_fs)}')
print(f'Not in mapping: {len(not_in_mapping)}')
print(f'Not in cache: {len(not_in_cache)}')
print(f'STATUS MISMATCHES: {len(mismatches)}')
print()

if mismatches:
    print('STATUS MISMATCHES (showing first 30):')
    print('=' * 70)
    for i, m in enumerate(mismatches[:30], 1):
        print(f'{i}. FS:{m["fs_id"]} (HS:{m["hs_id"]})')
        print(f'   FreeScout: active (assignee: {m["fs_assignee"]}) | Help Scout: {m["hs_status"]} (assignee: {m["hs_assignee"]})')
        print(f'   Subject: {m["subject"]}')
        print()

    # Count mismatches by assignee
    assigned_to_8 = sum(1 for m in mismatches if m['fs_assignee'] == 8)
    assigned_to_10 = sum(1 for m in mismatches if m['fs_assignee'] == 10)
    assigned_to_none = sum(1 for m in mismatches if m['fs_assignee'] is None)

    print(f'Mismatches by assignee:')
    print(f'  Joel (8): {assigned_to_8}')
    print(f'  Anica (10): {assigned_to_10}')
    print(f'  Unassigned: {assigned_to_none}')

    # Save all mismatches to file
    with open('status_mismatches.json', 'w') as f:
        json.dump(mismatches, f, indent=2)
    print(f'\nAll {len(mismatches)} mismatches saved to status_mismatches.json')
else:
    print('✓ No mismatches found!')

if not_in_mapping:
    print()
    print(f'Conversations in FreeScout but not in mapping (first 10):')
    for i, item in enumerate(not_in_mapping[:10], 1):
        print(f'  {i}. FS:{item["fs_id"]} - {item["subject"]}')
