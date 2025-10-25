# State Management & Incremental Syncs

## Overview

The migration tool provides comprehensive state management for:
- ✅ **Crash Recovery**: Resume from where you left off
- ✅ **Duplicate Prevention**: Never migrate the same conversation twice
- ✅ **Incremental Syncs**: Only sync new/updated conversations
- ✅ **Progress Tracking**: Monitor migration status
- ✅ **ID Mapping**: Track Help Scout → FreeScout ID relationships

---

## State File: `migration_progress.json`

### Location
```
/Users/joel/DevProjects/HelpScouttoFreeScoutSync/migration_progress.json
```

### Structure
```json
{
  "stats": {
    "customers_migrated": 145,
    "customers_skipped": 5,
    "conversations_migrated": 523,
    "conversations_skipped": 87,
    "threads_migrated": 2891,
    "attachments_migrated": 142,
    "errors": [],
    "last_sync_time": "2025-10-24T15:30:00Z",
    "migration_start_time": "2025-10-24T10:00:00Z",
    "migration_end_time": "2025-10-24T15:30:00Z"
  },
  "customer_mapping": {
    "657731462": 44,  // HS Customer ID → FS Customer ID
    "657731463": 45,
    ...
  },
  "conversation_mapping": {
    "3070818812": 40,  // HS Conversation ID → FS Conversation ID
    "3119109492": 41,
    ...
  },
  "processed_conversation_ids": [
    3070818812,
    3119109492,
    ...
  ],
  "timestamp": "2025-10-24T15:30:00.123456"
}
```

### What's Tracked

**Stats**:
- Counts of migrated/skipped items
- Error log
- Sync timestamps

**Customer Mapping**:
- Maps Help Scout customer IDs to FreeScout customer IDs
- Used to reuse existing customers

**Conversation Mapping**:
- Maps Help Scout conversation IDs to FreeScout conversation IDs
- Enables conversation updates (future feature)

**Processed IDs**:
- Set of all Help Scout conversation IDs that have been processed
- Used to skip duplicates

---

## Use Cases

### 1. Crash Recovery

**Scenario**: Migration crashes after 200 conversations

**Solution**:
```bash
# Resume from where you left off
python migrate.py --resume migration_progress.json
```

**What Happens**:
1. Loads previously migrated conversation IDs
2. Fetches all conversations from Help Scout
3. Filters out already-processed conversations
4. Continues with remaining conversations

**Result**: Continues from conversation #201

---

### 2. Initial Full Migration

**Scenario**: First-time migration of all data

**Command**:
```bash
python migrate.py --status active
```

**Process**:
1. Fetches all active conversations
2. Migrates each conversation
3. Saves progress every 10 conversations
4. Records `last_sync_time` when complete
5. Saves final state to `migration_progress.json`

**State File Created**: `migration_progress.json` with all mappings

---

### 3. Incremental Sync (One Week Later)

**Scenario**: You migrated last week, now want to sync new conversations

**Command**:
```bash
# Automatic - uses last_sync_time from progress file
python migrate.py --incremental --resume migration_progress.json
```

**What Happens**:
1. Loads `migration_progress.json`
2. Reads `last_sync_time`: `2025-10-17T10:00:00Z`
3. Fetches only conversations modified since that time
4. Skips already-processed conversation IDs
5. Migrates new conversations
6. Updates `last_sync_time` to current time

**Result**: Only conversations created/updated in the last week are migrated

---

### 4. Explicit Date Range Sync

**Scenario**: Sync conversations from a specific date

**Command**:
```bash
python migrate.py --modified-since "2025-10-20T00:00:00Z"
```

**What Happens**:
1. Fetches conversations modified since October 20, 2025
2. Skips already-processed IDs (if resume file exists)
3. Migrates matching conversations

---

### 5. Pre-Cutover Sync

**Scenario**: Testing migration for a week before final cutover

**Week 1 - Initial Migration**:
```bash
python migrate.py --status active
# Migrates 5000 conversations
# Saves state to migration_progress.json
```

**Week 2 - Daily Incremental Syncs**:
```bash
# Monday
python migrate.py --incremental --resume migration_progress.json
# Migrates ~50 new conversations from weekend

# Tuesday
python migrate.py --incremental --resume migration_progress.json
# Migrates ~20 new conversations from Monday

# ... repeat daily

# Friday (Cutover Day)
python migrate.py --incremental --resume migration_progress.json
# Final sync before switching to FreeScout permanently
```

**Result**: FreeScout stays in sync with Help Scout during testing period

---

## Command-Line Options

### Resume from Crash
```bash
python migrate.py --resume migration_progress.json
```
- Loads previous state
- Skips already-processed conversations
- Continues migration

### Incremental Sync (Automatic)
```bash
python migrate.py --incremental --resume migration_progress.json
```
- Uses `last_sync_time` from progress file
- Only fetches modified conversations
- Updates sync time when complete

### Incremental Sync (Explicit Date)
```bash
python migrate.py --modified-since "2025-10-20T00:00:00Z"
```
- Syncs from specific date
- Ignores `last_sync_time`
- Useful for one-time catch-up

### Combine with Filters
```bash
python migrate.py \
  --incremental \
  --resume migration_progress.json \
  --exclude-tags "test,low-priority" \
  --status active
```

---

## How Duplicate Prevention Works

### Deduplication Strategy

**1. Before API Call**: Skip based on processed IDs
```python
# Already in progress file
if conv_id in processed_hs_conversation_ids:
    skip()
```

**2. During Fetch**: Filter list after fetching
```python
# Remove already-processed conversations
unprocessed = [c for c in conversations
               if c['id'] not in processed_ids]
```

**3. After Migration**: Mark as processed
```python
# Add to processed set and mapping
processed_hs_conversation_ids.add(conv_id)
conversation_mapping[hs_conv_id] = fs_conv_id
```

### Why Multiple Checks?

- **API Filter** (`modifiedSince`): Reduces data transfer
- **Memory Filter** (`processed_ids`): Prevents re-processing
- **Database Check** (`search_customer_by_email`): Prevents duplicate customers

---

## State File Management

### Auto-Save Frequency

Progress is saved:
- **Every 10 conversations** during migration
- **At completion** of migration
- **On error** (before exit)

### Manual Save

Not needed - automatic!

### State File Location

Default: `migration_progress.json` in project root

Custom:
```bash
python migrate.py --resume /path/to/custom_progress.json
```

### Multiple State Files

You can maintain separate state files for different scenarios:

```bash
# Production migration
python migrate.py > migration_progress_prod.json

# Test migration
python migrate.py --max-conversations 100 > migration_progress_test.json

# Resume production
python migrate.py --resume migration_progress_prod.json
```

---

## Incremental Sync: How It Works

### API-Level Filtering

```
GET /v2/conversations?modifiedSince=2025-10-20T00:00:00Z
```

Help Scout returns only conversations where:
- Created after the date, OR
- Modified after the date (replies, status changes, etc.)

### Client-Side Deduplication

Even with `modifiedSince`, we still check processed IDs because:
1. Conversation might have been updated but already migrated
2. Previous sync might have failed partway through
3. Manual re-runs with different filters

### Flow Diagram

```
┌─────────────────────────┐
│ Start Incremental Sync  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Load migration_progress │
│ last_sync_time:         │
│ 2025-10-17T10:00:00Z    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Fetch from Help Scout   │
│ modifiedSince parameter │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Filter processed IDs    │
│ Skip: 150 conversations │
│ New: 12 conversations   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Migrate 12 new convs    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Update last_sync_time   │
│ 2025-10-24T15:30:00Z    │
└─────────────────────────┘
```

---

## Best Practices

### 1. Pre-Cutover Testing

```bash
# Week 1: Initial migration
python migrate.py --status active

# Weeks 2-4: Daily syncs to keep in sync
python migrate.py --incremental --resume migration_progress.json

# Cutover day: Final sync
python migrate.py --incremental --resume migration_progress.json
# Switch users to FreeScout
```

### 2. Backup State Files

```bash
# Before major operations, backup state
cp migration_progress.json migration_progress_backup_$(date +%Y%m%d).json

# Run migration
python migrate.py --incremental --resume migration_progress.json
```

### 3. Monitor Progress

```bash
# Check progress file
cat migration_progress.json | grep "conversations_migrated"

# Check last sync time
cat migration_progress.json | grep "last_sync_time"
```

### 4. Validate After Sync

```bash
# Run validation
python validate_migration.py --progress-file migration_progress.json

# Check for errors
cat migration_progress.json | jq '.stats.errors'
```

---

## Troubleshooting

### Incremental Sync Not Finding New Conversations

**Problem**: `--incremental` returns 0 conversations

**Causes**:
1. No new conversations since last sync
2. `last_sync_time` is in the future (clock skew)
3. Help Scout API caching

**Solution**:
```bash
# Check last sync time
cat migration_progress.json | grep last_sync_time

# Force sync from specific date
python migrate.py --modified-since "2025-10-23T00:00:00Z"
```

---

### Duplicate Conversations

**Problem**: Same conversation migrated twice

**Should Not Happen**: Our deduplication prevents this

**If It Does**:
```bash
# Check processed IDs
cat migration_progress.json | jq '.processed_conversation_ids | length'

# Check for duplicate FS conversation IDs
cat migration_progress.json | jq '.conversation_mapping | to_entries | group_by(.value) | map(select(length > 1))'
```

---

### Lost State File

**Problem**: Deleted or corrupted `migration_progress.json`

**Recovery**:
1. **Don't panic** - FreeScout has the data
2. Check for backups
3. Re-run with duplicate prevention (customers won't duplicate due to email check)

```bash
# Fresh start (will skip existing customers automatically)
python migrate.py --status active
```

---

### State File Too Large

**Problem**: 10,000+ conversations, state file is huge

**Current Size**: ~1KB per 100 conversations
**10,000 conversations**: ~100KB (not a problem)

**If Needed**:
- State file can handle 100,000+ conversations
- JSON compression available if needed

---

## Advanced: Custom State Management

### Reading State Programmatically

```python
import json

with open('migration_progress.json') as f:
    state = json.load(f)

# Get last sync time
last_sync = state['stats']['last_sync_time']

# Get conversation count
count = state['stats']['conversations_migrated']

# Check if conversation was migrated
conv_id = 3070818812
if conv_id in state['processed_conversation_ids']:
    fs_conv_id = state['conversation_mapping'][str(conv_id)]
    print(f"HS {conv_id} → FS {fs_conv_id}")
```

### Merging State Files

If you ran multiple migrations and need to merge:

```python
import json

with open('migration_progress_1.json') as f:
    state1 = json.load(f)

with open('migration_progress_2.json') as f:
    state2 = json.load(f)

# Merge
merged = {
    'stats': {
        'conversations_migrated': state1['stats']['conversations_migrated'] + state2['stats']['conversations_migrated'],
        # ... merge other stats
    },
    'customer_mapping': {**state1['customer_mapping'], **state2['customer_mapping']},
    'conversation_mapping': {**state1['conversation_mapping'], **state2['conversation_mapping']},
    'processed_conversation_ids': list(set(state1['processed_conversation_ids'] + state2['processed_conversation_ids']))
}

with open('migration_progress_merged.json', 'w') as f:
    json.dump(merged, f, indent=2)
```

---

## Summary

**State Management Features**:
- ✅ Automatic progress saving
- ✅ Crash recovery via `--resume`
- ✅ Incremental syncs via `--incremental`
- ✅ Custom date ranges via `--modified-since`
- ✅ Duplicate prevention (3 layers)
- ✅ ID mapping (customers & conversations)
- ✅ Error tracking

**Common Workflows**:
1. **Full Migration**: `python migrate.py`
2. **Resume After Crash**: `python migrate.py --resume migration_progress.json`
3. **Incremental Sync**: `python migrate.py --incremental --resume migration_progress.json`
4. **Custom Date**: `python migrate.py --modified-since "2025-10-20T00:00:00Z"`

**Files**:
- State: `migration_progress.json`
- Documentation: This file
- Implementation: `migrate.py` lines 63-120

---

## See Also

- [README.md](README.md) - General usage
- [FILTERING_GUIDE.md](FILTERING_GUIDE.md) - Filtering options
- [RATE_LIMITS_AND_PAGINATION.md](RATE_LIMITS_AND_PAGINATION.md) - Performance
