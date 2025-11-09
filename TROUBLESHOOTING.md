# Troubleshooting & Utility Scripts

## Problem: Active Conversation Count Mismatch

If you see more active conversations in FreeScout than Help Scout, it could be due to:

1. **Status sync issues** - FreeScout auto-changes status when threads are added
2. **Duplicate conversations** - From multiple migration runs
3. **New conversations in Help Scout** - Created after migration

## Utility Scripts

### 1. Check for Help Scout Updates

**Script:** `check_helpscout_updates.py`

Find conversations that have been modified in Help Scout since the migration:

```bash
python check_helpscout_updates.py
```

This uses the Help Scout API's `modifiedSince` parameter to:
- Find conversations updated since migration
- Identify new conversations not yet migrated
- Save results to `helpscout_updates_check.json`

**Help Scout API modifiedSince Parameter:**
```python
from api.helpscout_client import HelpScoutClient

hs_client = HelpScoutClient()

# Get conversations modified since a specific date
conversations = hs_client.get_all_conversations(
    status='active',
    modified_since='2025-10-20T00:00:00Z'  # ISO 8601 format
)
```

### 2. Lookup Conversations

**Script:** `lookup_conversation.py`

Quickly find FreeScout conversations from Help Scout IDs:

```bash
# Lookup by Help Scout ID
python lookup_conversation.py 3119109492

# Lookup by FreeScout ID (reverse lookup)
python lookup_conversation.py --fs 9913

# Lookup by Help Scout URL
python lookup_conversation.py --url https://secure.helpscout.net/conversation/3119109492
```

**Output:**
```
✓ Found mapping:
  Help Scout ID: 3119109492
  FreeScout ID:  9913

Links:
  Help Scout:  https://secure.helpscout.net/conversation/3119109492
  FreeScout:   https://helpdesk.domegaia.com/conversation/9913

FreeScout Details:
  Number:  #9913
  Subject: Voting Open for BroadwayWorld Next on Stage Season 6
  Status:  pending
  Threads: 3
```

### 3. Add Help Scout Reference Notes

**Script:** `add_helpscout_reference_notes.py`

Add a system note to each FreeScout conversation with the Help Scout link:

```bash
python add_helpscout_reference_notes.py
```

This adds a note like:

```
**Migrated from Help Scout**

Help Scout ID: 3119109492
Original conversation: https://secure.helpscout.net/conversation/3119109492
```

**Benefits:**
- Easy cross-referencing between systems
- Direct link to original conversation
- Visible in FreeScout UI
- Permanent record even if mapping file is lost

**Note:** This will add ~6,500 notes (one per migrated conversation). The process takes time but only needs to be run once.

## Mapping Files

### migration_progress.json

Contains the bidirectional mapping between Help Scout and FreeScout:

```json
{
  "conversation_mapping": {
    "3119109492": "9913",
    "3118908830": "9914",
    ...
  },
  "customer_mapping": {
    "755302126": "1234",
    ...
  }
}
```

**Use this file to:**
- Lookup conversations by ID
- Verify migration status
- Troubleshoot missing conversations
- Create custom reports

### Example: Find FreeScout ID from Help Scout ID

```python
import json

with open('migration_progress.json', 'r') as f:
    progress = json.load(f)

hs_id = "3119109492"
fs_id = progress['conversation_mapping'].get(hs_id)
print(f"FreeScout ID: {fs_id}")
```

## Common Issues

### Issue 1: More active in FreeScout than Help Scout

**Cause:** Conversations may have been updated in Help Scout after migration.

**Solution:**
1. Run `check_helpscout_updates.py` to identify updated conversations
2. Use the `modifiedSince` parameter to query only recent changes
3. Create a sync script to update statuses if needed

### Issue 2: Can't find conversation in FreeScout

**Cause:** Conversation may not have been migrated or was deleted.

**Solution:**
1. Use `lookup_conversation.py` to check if it was migrated
2. Check `migration_progress.json` for the mapping
3. Run `migrate_missing_conversations.py` if needed

### Issue 3: Duplicate conversations

**Cause:** Running migration scripts multiple times.

**Solution:**
1. Use FreeScout filters to find duplicates (same subject, same customer)
2. Delete duplicates manually or with a cleanup script
3. Make sure to keep the conversation with higher number (migrated ones)

## API Query Examples

### Get conversations modified in last 7 days

```python
from datetime import datetime, timedelta

date_7_days_ago = datetime.now() - timedelta(days=7)
modified_since = date_7_days_ago.strftime('%Y-%m-%dT%H:%M:%SZ')

conversations = hs_client.get_all_conversations(
    mailbox=312012,
    status='active',
    modified_since=modified_since
)
```

### Get conversations by status

```python
# Active only
active = hs_client.get_all_conversations(status='active')

# Pending only
pending = hs_client.get_all_conversations(status='pending')

# All statuses
all_convs = hs_client.get_all_conversations(status='all')
```

### Exclude spam conversations

```python
conversations = hs_client.get_all_conversations(
    status='all',
    exclude_tags=['spam', 'spam_review']
)
```

## Best Practices

1. **Always check migration_progress.json first** - It's the source of truth for mappings
2. **Use modifiedSince for incremental updates** - Don't re-fetch everything
3. **Add Help Scout reference notes** - Makes troubleshooting much easier
4. **Keep backups of mapping files** - Essential for troubleshooting
5. **Use lookup_conversation.py** - Faster than manual searching

## Help Scout API Reference

- **Conversations API:** https://developer.helpscout.com/mailbox-api/endpoints/conversations/list/
- **modifiedSince parameter:** ISO 8601 datetime format (e.g., `2025-10-20T00:00:00Z`)
- **Rate limits:** 400 requests per minute per app
- **Pagination:** 25 conversations per page (use `get_all_conversations()` to handle automatically)
