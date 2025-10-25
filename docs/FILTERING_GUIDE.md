# Advanced Filtering Guide

## Overview

The migration tool supports **API-level filtering** to exclude conversations before they're even fetched from Help Scout. This significantly improves performance and reduces unnecessary API calls.

---

## Benefits of API-Level Filtering

✅ **Faster Migration**: Only fetch conversations you need
✅ **Reduced API Calls**: Stay well under rate limits
✅ **Lower Bandwidth**: Don't transfer data you'll skip anyway
✅ **Cleaner Migration**: Exclude test data, spam, low-priority items upfront

---

## Available Filters

### 1. Status Filter

Filter conversations by their Help Scout status.

**Available Status Values**:
- `active` - Active conversations (default when skipping spam)
- `closed` - Closed conversations only
- `spam` - Spam conversations only
- `pending` - Pending conversations
- `open` - Open conversations
- `all` - All conversations (default)

**Usage**:
```bash
# Only migrate active conversations
python migrate.py --status active

# Only migrate closed conversations
python migrate.py --status closed

# Migrate everything including spam
python migrate.py --status all --include-spam
```

**Note**: When `--skip-spam` is enabled (default), the status filter automatically changes to `active` to exclude spam at the API level.

---

### 2. Exclude Status (NEW!)

Exclude conversations with specific statuses. This allows you to fetch all conversations and then filter out unwanted statuses client-side.

**Usage**:
```bash
# Exclude spam conversations only
python migrate.py --status all --exclude-status "spam"

# Exclude spam and closed conversations
python migrate.py --status all --exclude-status "spam,closed"

# Migrate all except spam (with tag exclusion)
python migrate.py --status all --exclude-status "spam" --exclude-tags "low-priority"
```

**How It Works**:
- Fetches conversations with `--status all` (or specified status)
- Filters out excluded statuses client-side after fetching
- Useful when you want multiple statuses but Help Scout API only accepts one status at a time

**Common Use Case**:
```bash
# Get active, pending, and closed conversations, but exclude spam
python migrate.py --status all --exclude-status "spam" --exclude-tags "low-priority"
```

This is simpler than running the migration three times (once for active, once for pending, once for closed).

---

### 3. Exclude Tags

Exclude conversations with specific tags. Multiple tags can be excluded using comma-separated values.

**Usage**:
```bash
# Exclude conversations tagged "low-priority"
python migrate.py --exclude-tags "low-priority"

# Exclude multiple tags
python migrate.py --exclude-tags "low-priority,internal-testing,spam"

# Combine with status filter
python migrate.py --status active --exclude-tags "low-priority,test"
```

**How It Works**:
- Tags are excluded using Help Scout's `NOT tag:"tagname"` query operator
- Multiple excluded tags are combined with AND logic
- Tags are case-sensitive (match Help Scout exactly)

---

### 4. Mailbox Filter

Filter to a specific Help Scout mailbox.

**Usage**:
```bash
# Only migrate mailbox 312012
python migrate.py --mailbox 312012
```

---

### 5. Spam Handling

Two ways to handle spam:

**Option 1: Skip Spam (Default)**
```bash
# Default behavior - excludes spam via API status filter
python migrate.py

# Explicit
python migrate.py --status active
```

**Option 2: Include Spam**
```bash
# Include spam conversations
python migrate.py --include-spam --status all
```

---

## Filter Combinations

### Example 1: Production Migration (Recommended)

Migrate only active, non-spam conversations, excluding test and low-priority items:

```bash
python migrate.py \
  --status active \
  --exclude-tags "test,low-priority,internal" \
  --mailbox 312012
```

**Result**: Only fetches conversations that are:
- ✓ In mailbox 312012
- ✓ Status: active
- ✗ NOT tagged with "test", "low-priority", or "internal"

---

### Example 2: Closed Conversations Only

Migrate completed/resolved conversations:

```bash
python migrate.py \
  --status closed \
  --exclude-tags "spam"
```

---

### Example 3: Testing with Limited Scope

Test migration with a small subset:

```bash
python migrate.py \
  --status active \
  --exclude-tags "low-priority" \
  --max-conversations 10
```

**Result**: Fetches up to 10 active conversations without "low-priority" tag

---

### Example 4: Everything Except Test Data

Migrate all conversations but exclude testing artifacts:

```bash
python migrate.py \
  --status all \
  --include-spam \
  --exclude-tags "test,qa,staging,demo"
```

---

## How Filtering Works

### API Query Construction

The tool builds Help Scout API queries automatically:

```python
# Example: Exclude tags + active status
GET /v2/conversations?status=active&query=(NOT tag:"low-priority" AND NOT tag:"test")

# Example: Mailbox + exclude tags
GET /v2/conversations?mailbox=312012&query=(NOT tag:"spam")
```

### Filter Application Order

1. **API-Level Filters** (fast - reduces data transfer)
   - Status filter (`--status`)
   - Exclude tags (`--exclude-tags`)
   - Mailbox filter (`--mailbox`)

2. **Post-Fetch Filters** (slower - applied after fetching)
   - Max conversations limit (`--max-conversations`)
   - Additional spam detection (for edge cases)

---

## Performance Impact

### Without Filters

```bash
python migrate.py --status all --include-spam
```

**Result**:
- Fetches: 5,000 conversations
- Processes: 5,000 conversations
- API Calls: ~50 pages × 100 conversations/page
- Time: ~7 hours

---

### With Filters

```bash
python migrate.py --status active --exclude-tags "low-priority,test"
```

**Result**:
- Fetches: 1,200 conversations (after filtering)
- Processes: 1,200 conversations
- API Calls: ~12 pages × 100 conversations/page
- Time: ~1.7 hours

**Savings**: 76% fewer conversations, 76% less API calls, 76% faster!

---

## Tag Discovery

### Find Available Tags

To see what tags exist in your Help Scout account:

```bash
# Use Help Scout UI
# Settings → Tags → View all tags

# Or query via API (manual)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.helpscout.net/v2/conversations?page=1
```

### Common Tags to Exclude

- `test`, `testing`, `qa` - Test conversations
- `spam`, `junk` - Spam (though status filter handles this)
- `low-priority`, `nice-to-have` - Low importance
- `internal`, `admin` - Internal communications
- `duplicate` - Duplicate conversations
- `archived`, `old` - Old/archived items

---

## Best Practices

### 1. Start Narrow, Expand Later

```bash
# Phase 1: Migrate recent active conversations
python migrate.py --status active --max-conversations 100

# Phase 2: Migrate closed conversations
python migrate.py --status closed --max-conversations 100

# Phase 3: Full migration
python migrate.py --status active --exclude-tags "test"
```

### 2. Test Filters First

```bash
# Test with 10 conversations to verify filters work correctly
python migrate.py \
  --status active \
  --exclude-tags "low-priority" \
  --max-conversations 10
```

### 3. Document Your Filters

Keep a record of what you're excluding:

```bash
# Create a migration script
cat > migrate_production.sh << 'EOF'
#!/bin/bash
python migrate.py \
  --status active \
  --exclude-tags "test,low-priority,internal,duplicate" \
  --mailbox 312012

echo "Migration complete!"
echo "Excluded tags: test, low-priority, internal, duplicate"
echo "Status filter: active (spam excluded)"
EOF

chmod +x migrate_production.sh
./migrate_production.sh
```

### 4. Validate Filters

After migration, check what was excluded:

```bash
# Check Help Scout for conversations with excluded tags
# Verify they're NOT in FreeScout
```

---

## Troubleshooting

### No Conversations Found

**Problem**: `✓ Found 0 conversations (after API filters)`

**Possible Causes**:
1. Filters too restrictive (no conversations match)
2. Wrong mailbox ID
3. Incorrect tag names (tags are case-sensitive)
4. Wrong status filter

**Solutions**:
```bash
# Try broader filters
python migrate.py --status all --include-spam

# Check tag spelling
# Verify in Help Scout UI: tags are case-sensitive

# Test without filters
python migrate.py --max-conversations 10
```

---

### Filter Not Working

**Problem**: Conversations with excluded tags still appear

**Possible Causes**:
1. Tag names don't match exactly (case-sensitive)
2. Conversations have multiple tags (only excluding one)
3. Post-fetch filtering needed

**Debug**:
```bash
# Enable verbose output (future enhancement)
# For now, check migration_progress.json for actual conversation data
```

---

## Advanced: Custom Queries

For very complex filtering, use the Help Scout API client directly:

```python
from api.helpscout_client import HelpScoutClient

hs_client = HelpScoutClient()

# Custom query with complex logic
conversations = hs_client.get_all_conversations(
    mailbox=312012,
    status='active',
    query='(assigned:"john" AND NOT tag:"low-priority")'
)

print(f"Found {len(conversations)} conversations")
```

**Supported Query Operators**:
- `AND` - Must match both conditions
- `OR` - Match either condition
- `NOT` - Exclude condition
- `tag:"name"` - Has tag
- `assigned:"user"` - Assigned to user
- `customerId:123` - Specific customer
- Combine with parentheses for complex logic

---

## Summary

**Available Filters**:
- ✅ Status (`--status active|closed|all|spam|pending|open`)
- ✅ Exclude Status (`--exclude-status "spam,closed"`) - NEW!
- ✅ Exclude Tags (`--exclude-tags "tag1,tag2"`)
- ✅ Mailbox (`--mailbox ID`)
- ✅ Spam Handling (`default: skip`, or `--include-spam`)
- ✅ Limit (`--max-conversations N`)

**Recommended Production Commands**:

**Option 1**: Single status (active only)
```bash
python migrate.py \
  --status active \
  --exclude-tags "test,low-priority,internal" \
  --mailbox 312012
```

**Option 2**: Multiple statuses (exclude spam)
```bash
python migrate.py \
  --status all \
  --exclude-status "spam" \
  --exclude-tags "test,low-priority,internal" \
  --mailbox 312012
```

This ensures you migrate **all conversation statuses (active, pending, closed)** except spam, while excluding test data and low-priority items.

---

## See Also

- [README.md](README.md) - General migration guide
- [RATE_LIMITS_AND_PAGINATION.md](RATE_LIMITS_AND_PAGINATION.md) - Performance details
- [ATTACHMENT_SOLUTION.md](ATTACHMENT_SOLUTION.md) - Attachment handling
