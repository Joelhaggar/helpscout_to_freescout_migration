# Help Scout ID Custom Field Setup

## ✅ Custom Field Successfully Configured!

The FreeScout Custom Fields module has been installed and tested. All future migrations will automatically include the Help Scout conversation ID.

## Test Results

**Test Conversation:** #10255
- ✅ Custom field "Helpscout" (ID: 1) created
- ✅ Value set to Help Scout ID: 3119294864
- ✅ Searchable in FreeScout UI
- ✅ API update method working

View test conversation:
- FreeScout: https://helpdesk.domegaia.com/conversation/10255
- Help Scout: https://secure.helpscout.net/conversation/3119294864

## What's Been Updated

### 1. FreeScout API Client

Added method to update custom fields: [api/freescout_client.py:312-333](api/freescout_client.py#L312-L333)

```python
fs_client.update_custom_fields(conversation_id, [
    {'id': 1, 'value': '3119294864'}
])
```

### 2. Main Migration Script

Updated [migrate.py:342-349](migrate.py#L342-L349) to automatically set custom field during migration.

All future migrations will include the Help Scout ID custom field.

### 3. Test Script

Created [test_custom_field_migration.py](test_custom_field_migration.py) to test custom field functionality.

### 4. Bulk Update Script

Created [add_helpscout_custom_field_to_all.py](add_helpscout_custom_field_to_all.py) to add custom fields to existing conversations.

## Next Steps

### For Existing Conversations

Since you have a clean FreeScout database, you'll be doing a fresh migration. The custom fields will be set automatically for all new conversations.

If you want to add custom fields to the one test conversation we just created, you can run:

```bash
python add_helpscout_custom_field_to_all.py
```

### For New Migrations

Just run the migration normally:

```bash
python migrate.py
```

The custom field will be set automatically for each conversation.

## Custom Field Benefits

✅ **Searchable** - Search by Help Scout ID in FreeScout UI
✅ **Structured Data** - Dedicated field, not mixed with conversation content
✅ **API Accessible** - Can query via API (if FreeScout adds support in future)
✅ **Clean Timeline** - Doesn't add notes to conversation thread
✅ **Workflow Integration** - Can use in FreeScout workflows

## Comparing with Notes Method

| Feature | Custom Field | Notes |
|---------|-------------|-------|
| Searchable in UI | ✅ Yes | ✅ Yes |
| Searchable via API | ❌ Not yet | ❌ No |
| Cost | $59 module | Free |
| Timeline clutter | ✅ None | ⚠️ Adds note |
| Structured data | ✅ Yes | ❌ No |
| Clickable link | ❌ No | ✅ Yes |
| Workflow support | ✅ Yes | ❌ No |

## Custom Field Details

- **Field ID:** 1
- **Field Name:** Helpscout
- **Field Type:** Text
- **Value:** Help Scout conversation ID (e.g., "3119294864")

## Searching in FreeScout

You can search for conversations by Help Scout ID in the FreeScout search bar:

```
Search: 3119294864
```

This will find the conversation with that Help Scout ID in the custom field.

## API Documentation

### Update Custom Field

```python
from api.freescout_client import FreeScoutClient
from config.config import Config

fs_client = FreeScoutClient(Config.FREESCOUT_API_KEY, Config.FREESCOUT_URL)

# Update custom field
fs_client.update_custom_fields(conversation_id, [
    {'id': 1, 'value': 'help_scout_id'}
])
```

### Read Custom Field

```python
# Get conversation
conv = fs_client.get_conversation(conversation_id)

# Access custom fields
if 'customFields' in conv:
    for field in conv['customFields']:
        if field.get('name') == 'Helpscout':
            hs_id = field.get('value')
            print(f"Help Scout ID: {hs_id}")
```

## Troubleshooting

### Custom field update fails with 404

**Cause:** Conversation doesn't exist in FreeScout.

**Solution:** Verify the conversation was migrated. Check `migration_progress.json`.

### Custom field not showing in conversation

**Cause:** Custom Fields module not installed or custom field not created.

**Solution:**
1. Verify Custom Fields module is active in FreeScout
2. Check that "Helpscout" custom field exists (ID: 1)
3. Verify field is assigned to the mailbox

### Cannot search by custom field value

**Cause:** FreeScout search may have limitations depending on version/modules.

**Solution:** Use the lookup script as alternative:

```bash
python lookup_conversation.py 3119294864
```

## Future Enhancements

- [ ] Add custom field for Help Scout customer ID
- [ ] Add custom field for original Help Scout conversation number
- [ ] Create workflow to auto-tag conversations based on custom fields
- [ ] Add custom field search to API (requires FreeScout update)

## Related Files

- [api/freescout_client.py](api/freescout_client.py) - FreeScout API client with custom field methods
- [migrate.py](migrate.py) - Main migration script (auto-sets custom field)
- [test_custom_field_migration.py](test_custom_field_migration.py) - Test script
- [add_helpscout_custom_field_to_all.py](add_helpscout_custom_field_to_all.py) - Bulk update script
- [lookup_conversation.py](lookup_conversation.py) - Command-line lookup utility
- [NOTES_VS_CUSTOM_FIELDS.md](NOTES_VS_CUSTOM_FIELDS.md) - Comparison document
