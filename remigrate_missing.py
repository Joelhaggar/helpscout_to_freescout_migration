"""
Re-migrate conversations that are missing from FreeScout.
This will identify active/pending conversations in Help Scout that
are not in FreeScout and migrate them.
"""
from api.helpscout_client import HelpScoutClient
from api.freescout_client import FreeScoutClient
from config.config import Config
import json
from pathlib import Path

hs_client = HelpScoutClient()
fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

# Load mapping
with open('migration_progress.json', 'r') as f:
    data = json.load(f)
    mapping = data.get('conversation_mapping', {})

reverse_mapping = {int(fs_id): int(hs_id) for hs_id, fs_id in mapping.items()}

print('Step 1: Get all current FreeScout conversations...')
fs_conversation_ids = set()
page = 1

while True:
    try:
        response = fs_client._make_request('GET', '/conversations', params={'page': page})
        conversations = response.get('_embedded', {}).get('conversations', [])

        if not conversations:
            break

        for conv in conversations:
            fs_id = conv.get('id')
            # Find the Help Scout ID for this FreeScout conversation
            hs_id = reverse_mapping.get(fs_id)
            if hs_id:
                fs_conversation_ids.add(hs_id)

        page += 1
    except Exception as e:
        print(f'Error: {e}')
        break

print(f'Found {len(fs_conversation_ids)} Help Scout conversations currently in FreeScout')
print()

# Load Help Scout cache
print('Step 2: Load Help Scout cache...')
hs_conversations = {}
cache_dir = Path('helpscout_cache')

for cache_file in sorted(cache_dir.glob('conversations_page_*.json')):
    with open(cache_file, 'r') as f:
        conversations = json.load(f)
        for conv in conversations:
            hs_conversations[conv['id']] = conv

print(f'Loaded {len(hs_conversations)} conversations from Help Scout cache')
print()

# Find missing conversations (active or pending)
print('Step 3: Find missing conversations...')
missing = []

for hs_id, hs_conv in hs_conversations.items():
    status = hs_conv.get('status')

    # Only check active and pending
    if status not in ['active', 'pending']:
        continue

    # Check if this HS conversation exists in FreeScout
    if hs_id not in fs_conversation_ids:
        missing.append({
            'hs_id': hs_id,
            'status': status,
            'subject': hs_conv.get('subject', '')[:60],
            'assignee_id': hs_conv.get('assignee', {}).get('id') if hs_conv.get('assignee') else None
        })

print(f'Found {len(missing)} missing active/pending conversations')
print()

if missing:
    # Save to file
    with open('missing_conversations.json', 'w') as f:
        json.dump(missing, f, indent=2)

    print('Missing conversations by status:')
    status_counts = {}
    for m in missing:
        status_counts[m['status']] = status_counts.get(m['status'], 0) + 1

    for status, count in sorted(status_counts.items()):
        print(f'  {status}: {count}')

    print()
    print('Saved to missing_conversations.json')
    print()
    print('To re-migrate these conversations, you can:')
    print('1. Delete non-migrated test conversations from FreeScout')
    print('2. Run the migration script with --resume to add missing conversations')
else:
    print('✓ No missing conversations!')
