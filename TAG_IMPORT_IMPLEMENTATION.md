# Tag Import Implementation

## Summary
Added tag import functionality to both `bulk_import_conversations.py` and `test_single_conversation.py` to ensure that tags from Help Scout conversations are properly imported into FreeScout after successful conversation creation.

## Changes Made

### 1. [production_scripts_v2/bulk_import_conversations.py](production_scripts_v2/bulk_import_conversations.py)

**Lines 274-284**: Added tag import logic after successful conversation creation

```python
# Apply tags if conversation has any
tags = extract_tags(conv_data)
if tags:
    try:
        # Filter out "ignore" and "low priority" tags since they're for filtering
        tags_to_apply = [t for t in tags if t.lower() not in ['ignore', 'low priority']]
        if tags_to_apply:
            fs_client.update_conversation_tags(fs_conv_id, tags_to_apply)
    except Exception as e:
        # Log tag error but don't fail the conversation import
        pass
```

**Key Features:**
- Extracts tags using existing `extract_tags()` function
- Filters out "ignore" and "low priority" tags (these are filtering tags, not regular tags to migrate)
- Calls FreeScout API's `update_conversation_tags()` method for each successfully imported conversation
- Tag errors don't fail the conversation import (graceful error handling)
- Non-blocking exception handling to keep import pipeline moving

### 2. [test_single_conversation.py](test_single_conversation.py)

**Lines 289-299**: Added tag import logic after successful conversation creation

```python
# Apply tags if conversation has any
tags = extract_tags(conv_data)
if tags:
    try:
        # Filter out "ignore" and "low priority" tags since they're for filtering
        tags_to_apply = [t for t in tags if t.lower() not in ['ignore', 'low priority']]
        if tags_to_apply:
            fs_client.update_conversation_tags(fs_conv_id, tags_to_apply)
            print(f"   Tags applied: {', '.join(tags_to_apply)}")
    except Exception as e:
        print(f"   ⚠ Failed to apply tags: {e}")
```

**Key Features:**
- Same tag extraction and filtering logic as bulk import
- Provides user feedback when tags are successfully applied
- Shows warning message if tag application fails
- Clear visibility into what tags were applied

## How It Works

1. **After conversation creation**: Once a conversation is successfully created in FreeScout and has an ID, we extract the tags from the original Help Scout conversation data

2. **Tag extraction**: Uses the existing `extract_tags()` function from `mapping/mappers.py` which handles both:
   - String tags: `["urgent", "customer"]`
   - Object tags: `[{"tag": "urgent"}, {"name": "customer"}]`

3. **Tag filtering**: Removes "ignore" and "low priority" tags since these are used for filtering conversations (preventing import), not for labeling imported conversations

4. **Tag application**: Calls `FreeScoutClient.update_conversation_tags(conversation_id, tags)` which sends a PUT request to `/conversations/{id}/tags` with the filtered tag list

5. **Error handling**:
   - In bulk import: Silently catches tag errors (doesn't fail the conversation)
   - In test script: Shows warning but still returns success

## API Used

```python
def update_conversation_tags(self, conversation_id: int, tags: List[str]) -> Dict:
    """Update tags for a conversation."""
    return self._make_request('PUT', f'/conversations/{conversation_id}/tags', data={'tags': tags})
```

From: `api/freescout_client.py` line 328-339

## Testing

Run the test script to verify tag import works:
```bash
cd production_scripts_v2
source ../venv/bin/activate
python test_single_conversation.py
```

Look for output like:
```
✅ Conversation created successfully!
   FreeScout ID: 123
   HS ID→FS ID: 3132185360→123
   Tags applied: urgent, customer, feedback
```

Then run bulk import with a small test:
```bash
python bulk_import_conversations.py --max-conversations 10
```

## Filtering vs. Application

**Tags used for filtering (NOT imported):**
- "ignore" - prevents conversation import
- "low priority" - prevents conversation import

**Tags that ARE imported:**
- All other tags from the Help Scout conversation are imported into FreeScout

## Edge Cases Handled

1. **No tags**: If conversation has no tags, no API call is made
2. **Only filtering tags**: If conversation has only "ignore"/"low priority", no tags are applied
3. **API failure**: If tag update fails, the conversation is still considered successfully imported (non-blocking)
4. **Mixed tags**: If conversation has "urgent,ignore,customer", only "urgent,customer" are applied

## Verification

To verify tags are being imported:
1. Look at conversations in FreeScout UI
2. Check conversation details for tag section
3. Tags should match Help Scout conversation tags (minus "ignore"/"low priority")
