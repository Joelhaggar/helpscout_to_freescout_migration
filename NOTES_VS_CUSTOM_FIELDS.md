# Notes vs Custom Fields: Help Scout ID Storage

## Summary

**Notes are searchable in the FreeScout UI**, but **Custom Fields are NOT searchable via API** (and may not be searchable in UI either).

**Recommendation: Use Notes method** - it provides better search capability and doesn't require additional modules.

## Detailed Comparison

### Notes Method ✅

**Pros:**
- ✅ **Searchable in UI**: FreeScout's search includes notes content
- ✅ **No extra modules required**: Works with base FreeScout
- ✅ **Visible to all users**: Notes appear in conversation timeline
- ✅ **Easy to implement**: Simple API call to add thread
- ✅ **Works with Faster Search**: Compatible with Meilisearch module
- ✅ **Clickable links**: Can include direct URL to Help Scout
- ✅ **Rich formatting**: Supports markdown for better readability

**Cons:**
- ❌ **Not structured data**: Just text in notes
- ❌ **Not filterable via API**: Can't use as API filter parameter
- ❌ **Clutters timeline**: Adds an entry to conversation history

**Search in UI:**
```
Search: "HS:3119109492"
Result: Finds conversation with that Help Scout ID in notes
```

**Implementation:**
```python
note_data = {
    'type': 'note',
    'text': f'**Migrated from Help Scout**\n\nHelp Scout ID: {hs_id}\n[View in Help Scout](https://secure.helpscout.net/conversation/{hs_id})',
    'user': 8,
    'imported': True
}
fs_client.add_thread(fs_id, note_data, imported=True)
```

### Custom Fields Method ❌

**Pros:**
- ✅ **Structured data**: Dedicated field for Help Scout ID
- ✅ **Cleaner timeline**: Doesn't add to conversation thread
- ✅ **Can be used in Workflows**: Trigger actions based on field value

**Cons:**
- ❌ **Requires paid module**: Need Custom Fields module (~$59)
- ❌ **NOT searchable via API**: Cannot filter conversations by custom field via API (confirmed limitation)
- ❌ **May not be searchable in UI**: Unclear if UI search includes custom fields
- ❌ **Incompatible with Faster Search**: Customer fields don't work with Meilisearch
- ❌ **More complex setup**: Need to create custom field first, then populate

**API Limitation (confirmed in GitHub Issue #2096):**
```
Q: Can I search conversations by custom field value via API?
A: "Seems no. Would be nice feature though."
Status: Not supported as of 2024
```

## FreeScout Search Capabilities

### UI Search (with or without Faster Search module)
- ✅ Searches tickets
- ✅ Searches messages
- ✅ Searches **notes** ⭐
- ✅ Searches customers
- ✅ Searches tags
- ✅ Searches team members
- ✅ Searches tasks
- ❓ Custom fields (unclear/limited)

### API Search Parameters
The API only supports these filters:
- mailboxId, folderId, status, state, type
- assignedTo, customerEmail, customerPhone, customerId
- number, **subject** (text search), tag
- createdByUserId, createdByCustomerId
- createdSince, updatedSince

**NOT supported:**
- ❌ Thread/note content search
- ❌ Custom field filtering

## Recommendations

### Option 1: Notes Only (Recommended) ⭐

Use `add_helpscout_reference_notes.py` to add notes to all conversations.

**Best for:**
- You want to search by Help Scout ID in the UI
- You don't want to pay for extra modules
- You're okay with notes appearing in timeline

**Usage:**
```bash
python add_helpscout_reference_notes.py
```

### Option 2: Custom Field Only

Purchase Custom Fields module and add Help Scout ID as structured data.

**Best for:**
- You need structured metadata (not recommended based on limitations)
- You want clean conversation timelines
- You don't need to search by Help Scout ID (❗limitation)

**Setup:**
1. Purchase Custom Fields module ($59)
2. Create "Help Scout ID" custom field in FreeScout settings
3. Create script to populate field via API

### Option 3: Both Notes + Custom Field (Overkill)

Add both notes AND custom fields.

**Best for:**
- Maximum compatibility
- You already have Custom Fields module
- You want both searchability and structured data

**Trade-offs:**
- More work to implement
- Cost of Custom Fields module
- Notes already solve the search problem

### Option 4: Lookup Script Only (Current State) ✅

Use `lookup_conversation.py` with `migration_progress.json` mapping.

**Best for:**
- You primarily search via command line/scripts
- You don't want to modify FreeScout conversations
- You're comfortable with technical tools

**Usage:**
```bash
# Quick lookup
python lookup_conversation.py 3119109492
python lookup_conversation.py --fs 9913
```

## Implementation Scripts

### Already Created:
1. ✅ `lookup_conversation.py` - Command-line lookup tool
2. ✅ `add_helpscout_reference_notes.py` - Add notes with HS ID
3. ✅ `check_helpscout_updates.py` - Find modified conversations

### Would Need to Create (for Custom Fields):
- Script to create custom field via API
- Script to populate custom field for all conversations
- More complex, requires Custom Fields module

## Final Recommendation

**Go with the Notes method** (`add_helpscout_reference_notes.py`) because:

1. ✅ **Searchable in UI** - You can search for Help Scout IDs
2. ✅ **No cost** - Works with base FreeScout
3. ✅ **Simple** - One script execution
4. ✅ **Includes clickable link** - Direct access to Help Scout conversation
5. ✅ **Permanent** - Even if mapping file is lost

The only downside is it adds a note to each conversation timeline, but that's actually a feature - it provides a clear audit trail that the conversation was migrated.

## Test Before Full Rollout

Before adding notes to all 6,500+ conversations, test on a few:

```bash
# Test manually with a single conversation
python -c "
from api.freescout_client import FreeScoutClient
from config.config import Config

fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

# Test on conversation 10169
note_data = {
    'type': 'note',
    'text': '**Migrated from Help Scout**\n\nHelp Scout ID: 3119109492\n[View in Help Scout](https://secure.helpscout.net/conversation/3119109492)',
    'user': 8,
    'imported': True
}

result = fs_client.add_thread(10169, note_data, imported=True)
print('Note added successfully!')
print('Check conversation #10169 in FreeScout UI')
"
```

Then verify:
1. Note appears in conversation timeline
2. You can search for "3119109492" in FreeScout search
3. Link works and goes to Help Scout
