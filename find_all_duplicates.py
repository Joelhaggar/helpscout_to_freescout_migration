"""
Find ALL duplicate conversations in FreeScout (by subject).
"""
from api.freescout_client import FreeScoutClient
from config.config import Config
import json
from collections import defaultdict

fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

# Load mapping to identify migrated vs non-migrated
with open('migration_progress.json', 'r') as f:
    data = json.load(f)
    mapping = data.get('conversation_mapping', {})

reverse_mapping = {int(fs_id): int(hs_id) for hs_id, fs_id in mapping.items()}

print('Fetching ALL conversations from FreeScout...')
all_convs = []
page = 1

while True:
    try:
        response = fs_client._make_request('GET', '/conversations', params={'page': page})
        conversations = response.get('_embedded', {}).get('conversations', [])

        if not conversations:
            break

        all_convs.extend(conversations)
        page += 1

        if page % 50 == 0:
            print(f'  Fetched {len(all_convs)} so far...')

    except Exception as e:
        print(f'Error: {e}')
        break

print(f'Total conversations: {len(all_convs)}')
print()

# Group by subject to find ALL duplicates
by_subject = defaultdict(list)

for conv in all_convs:
    subject = conv.get('subject', '').strip()
    if not subject:
        continue

    assignee = conv.get('assignee')
    assignee_id = None
    assignee_name = 'Unassigned'

    if assignee:
        assignee_id = assignee.get('id')
        if assignee_id == 8:
            assignee_name = 'Joel'
        elif assignee_id == 10:
            assignee_name = 'Anica'

    by_subject[subject].append({
        'fs_id': conv.get('id'),
        'number': conv.get('number'),
        'status': conv.get('status'),
        'assignee_id': assignee_id,
        'assignee_name': assignee_name,
        'migrated': conv.get('id') in reverse_mapping
    })

# Find ALL duplicates (any subject appearing more than once)
all_duplicates = {subject: convs for subject, convs in by_subject.items() if len(convs) > 1}

print(f'Total subjects with duplicates: {len(all_duplicates)}')

# Count by status
active_duplicate_subjects = []
for subject, conv_list in all_duplicates.items():
    active_count = sum(1 for c in conv_list if c['status'] == 'active')
    if active_count > 1:
        active_duplicate_subjects.append(subject)

print(f'Subjects with multiple ACTIVE duplicates: {len(active_duplicate_subjects)}')
print()

if all_duplicates:
    print('ALL DUPLICATE CONVERSATIONS:')
    print('=' * 70)

    duplicate_ids_to_remove = []

    for subject, conv_list in sorted(all_duplicates.items()):
        active_count = sum(1 for c in conv_list if c['status'] == 'active')

        print(f'Subject: {subject[:60]}')
        print(f'  Total copies: {len(conv_list)} | Active: {active_count}')

        # Sort by number, keep the lowest
        conv_list.sort(key=lambda x: x['number'])

        for i, conv in enumerate(conv_list):
            marker = '  KEEP  ' if i == 0 else '  DELETE'
            migrated = ' (from HS)' if conv['migrated'] else ' (local)'
            print(f'    {marker} | #{conv["number"]:4d} | FS:{conv["fs_id"]:5d} | {conv["status"]:8s} | {conv["assignee_name"]:10s}{migrated}')

            if i > 0:
                duplicate_ids_to_remove.append(conv['fs_id'])
        print()

    print('=' * 70)
    print(f'Total duplicate conversations to remove: {len(duplicate_ids_to_remove)}')

    # Count by status
    status_breakdown = {}
    for detail_list in all_duplicates.values():
        for conv in detail_list[1:]:  # Skip first (the one we keep)
            status = conv['status']
            status_breakdown[status] = status_breakdown.get(status, 0) + 1

    print(f'\nDuplicates to delete by status:')
    for status, count in sorted(status_breakdown.items()):
        print(f'  {status}: {count}')

    # Save
    with open('all_duplicates_to_delete.json', 'w') as f:
        json.dump({
            'count': len(duplicate_ids_to_remove),
            'fs_ids': duplicate_ids_to_remove,
            'details': [c for convs in all_duplicates.values() for c in convs[1:]]
        }, f, indent=2)

    print()
    print('List saved to all_duplicates_to_delete.json')
else:
    print('✓ No duplicates found!')
