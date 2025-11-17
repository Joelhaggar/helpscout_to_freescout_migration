# Production Ready - Help Scout to FreeScout Migration Tool

## Overview
This project is now production-ready with a complete, working migration pipeline from Help Scout to FreeScout. All core functionality has been implemented and tested.

## Main Production Scripts (production_scripts_v2/)

### 1. bulk_import_conversations.py
**Purpose**: Main script for bulk importing conversations with multi-threading support

**Features**:
- Multi-threaded import with configurable thread count (default: 10)
- Resumable imports with state tracking (bulk_import_state.json)
- Automatic attachment handling with binary file support
- Timestamp preservation (uses `imported=True` parameter)
- Conversation filtering:
  - Skips "spam" status conversations
  - Skips conversations with "ignore" or "low priority" tags
- Tag import: Applies Help Scout tags to FreeScout conversations
- Thread-safe statistics tracking with concurrent modification protection

**Usage**:
```bash
# First run
python bulk_import_conversations.py [--max-conversations N] [--dry-run]

# Resume interrupted import
python bulk_import_conversations.py --resume

# Test with 10 conversations
python bulk_import_conversations.py --max-conversations 10
```

**Output**:
- `bulk_import_state.json` - State file with progress, timestamps, and mappings
- Console output with real-time statistics

### 2. test_single_conversation.py
**Purpose**: Test/validate single conversation import before bulk operations

**Features**:
- Tests complete import pipeline on one conversation
- Validates customer mapping
- Tests attachment handling
- Shows conversation filtering reasons
- Displays tags that will be applied
- Displays timestamps to verify preservation
- Full error reporting with tracebacks

**Usage**:
```bash
# Test a specific conversation ID
python test_single_conversation.py --help-scout-conversation-id 3132185360

# Test without specifying ID (uses first found)
python test_single_conversation.py
```

### 3. build_customer_mapping.py
**Purpose**: Create Help Scout → FreeScout customer ID mapping

**Features**:
- Fetches all customers from Help Scout API
- Looks up each customer in FreeScout by email
- Saves mapping to customer_mapping.json
- Thread-safe with concurrent requests

**Usage**:
```bash
python build_customer_mapping.py
```

**Output**:
- `customer_mapping.json` - Mapping of HS customer ID → FS customer ID

### 4. extract_customer_mapping.py
**Purpose**: Extract customer mapping from exported data

**Features**:
- Reads from Help Scout export files
- Creates customer mapping without API calls
- Useful for testing or when API access is limited

**Usage**:
```bash
python extract_customer_mapping.py
```

### 5. update_export_from_cache.py
**Purpose**: Update Help Scout export with cached API data

**Features**:
- Merges Help Scout export with cached conversation data
- Ensures all required fields are present

**Usage**:
```bash
python update_export_from_cache.py
```

### 6. test_bulk_import.sh
**Purpose**: Convenience script to test bulk import with 10 conversations

**Features**:
- Quick way to validate full bulk import pipeline
- Tests all features without processing entire database

**Usage**:
```bash
bash test_bulk_import.sh
```

## Core Modules

### api/freescout_client.py
FreeScout REST API client with methods for:
- Creating conversations (`create_conversation(conversation, imported=True)`)
- Updating conversation tags (`update_conversation_tags(conversation_id, tags)`)
- Getting/setting custom fields
- Managing conversation status

**Key Methods**:
- `create_conversation(data, imported=True)` - Create with timestamp preservation
- `update_conversation_tags(id, tags)` - Apply tags to conversation
- `get_conversations(mailbox_id)` - Fetch conversations
- `update_conversation_status(id, status)` - Update status

### mapping/mappers.py
Data transformation functions:
- `map_customer_to_freescout()` - Map customer data
- `map_conversation_to_freescout()` - Map conversation data
- `map_thread_to_freescout()` - Map thread/message data
- `extract_tags()` - Extract tag names from conversation
- `map_status()` - Convert status values
- `map_mailbox_id()` - Map mailbox IDs
- `map_user_id()` - Map user IDs

### utils/filters.py
Filtering logic:
- `should_migrate_conversation()` - Check if conversation should be imported
- `is_spam_conversation()` - Check for spam status

### utils/helpscout_client.py
Help Scout REST API client

## Configuration

### .env (Local, Not Committed)
Required environment variables:
```
Helpscout_client_id=<your_client_id>
Helpscout_client_secret=<your_client_secret>
Freescout_APIKey=<your_api_key>
Freescout_URL=<your_freescout_url>
```

### config/user_mapping.json
Maps Help Scout user IDs to FreeScout user IDs
```json
{
  "mapping": {
    "12345": 8
  }
}
```

### config/mailbox_mapping.json
Maps Help Scout mailbox IDs to FreeScout mailbox IDs
```json
{
  "mapping": {
    "1": 1
  }
}
```

### customer_mapping.json (Generated)
Created by `build_customer_mapping.py`:
```json
{
  "mapping": {
    "3101070180": 123,
    "3110179134": 124
  }
}
```

### bulk_import_state.json (Generated)
Tracks import progress:
```json
{
  "started_at": "2025-11-16T13:00:00",
  "last_updated_at": "2025-11-16T13:30:00",
  "imported_conversations": {
    "3101070180": 123
  },
  "failed_conversations": {
    "3110179134": "Error message"
  },
  "statistics": { ... }
}
```

## Migration Workflow

### Step 1: Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your actual credentials
```

### Step 2: Create Mappings
```bash
# Create customer mapping
cd production_scripts_v2
python build_customer_mapping.py

# Verify config/user_mapping.json and config/mailbox_mapping.json are correct
```

### Step 3: Test Single Conversation
```bash
# Test with one conversation to validate pipeline
python test_single_conversation.py

# Check the output:
# - Timestamps are preserved
# - Tags are displayed
# - Filtering works correctly
# - Attachments are imported
```

### Step 4: Test Bulk Import (10 conversations)
```bash
# Quick test with just 10 conversations
python bulk_import_conversations.py --max-conversations 10

# Review bulk_import_state.json to see progress
```

### Step 5: Full Migration
```bash
# Run full import
python bulk_import_conversations.py

# Or resume interrupted import
python bulk_import_conversations.py --resume
```

## Features Implemented

### ✅ Conversation Filtering
- Skips conversations with "spam" status
- Skips conversations with "ignore" or "low priority" tags
- Records filtering reason in state file

### ✅ Timestamp Preservation
- Uses FreeScout API's `imported=True` parameter
- Original Help Scout creation time is preserved
- Original closure time is preserved if applicable

### ✅ Attachment Support
- Downloads attachments from Help Scout
- Converts to base64 for API transport
- Stores as binary files in FreeScout
- Handles multiple attachments per thread

### ✅ Tag Import
- Extracts tags from Help Scout conversations
- Filters out "ignore" and "low priority" tags
- Applies remaining tags to FreeScout conversations
- Handles both string and object tag formats

### ✅ User and Mailbox Mapping
- Maps Help Scout user IDs to FreeScout users
- Maps Help Scout mailbox IDs to FreeScout mailboxes
- Validates mappings before import

### ✅ Resumable Imports
- State file tracks progress
- Can resume from interruption
- Avoids duplicate imports
- `--resume` flag skips already-imported conversations

### ✅ Thread-Safe Multi-Threading
- Concurrent import with configurable thread count
- Thread-safe statistics tracking
- Protected shared data access with locks
- Concurrent modification handling in state saves

### ✅ Error Handling
- Records failed conversations with error reasons
- Graceful tag failure handling (doesn't fail conversation)
- Clear error messages in console and logs
- Traceback display for debugging

## Cleanup

### .gitignore Configuration
Files excluded from version control:
- `.env` - Credentials
- `bulk_import_state.json` - Runtime state
- `customer_mapping.json` - Generated mapping
- `helpscout_attachments/` - Downloaded files
- `production_scripts/` - Old version
- Debug scripts in root directory
- Planning documentation

### What's NOT Committed
- `.env` file (credentials)
- Generated state/mapping files
- Downloaded attachments
- Debug scripts from root directory
- Old production_scripts/ version
- Planning documents (already implemented)

### What IS Committed
- `production_scripts_v2/` - Production code
- Core modules: `api/`, `mapping/`, `utils/`, `config/`
- Configuration templates: `user_mapping.json.example`, etc.
- Documentation: `README.md`, `TAG_IMPORT_IMPLEMENTATION.md`, etc.

## Testing Checklist

Before running full migration:

- [ ] `.env` file is created with valid credentials
- [ ] `config/user_mapping.json` is configured
- [ ] `config/mailbox_mapping.json` is configured
- [ ] `python test_single_conversation.py` runs successfully
- [ ] Timestamps are preserved in test import
- [ ] Tags appear in FreeScout conversation
- [ ] Attachments are imported correctly
- [ ] `python bulk_import_conversations.py --max-conversations 10` succeeds
- [ ] State file is created and updated
- [ ] Statistics in console match expected values

## Troubleshooting

### "dictionary changed size during iteration" Error
**Status**: FIXED in version committed
**Cause**: Concurrent modification of shared data structures
**Solution**: State save now creates atomic snapshots while holding lock

### Timestamps Not Preserved
**Status**: FIXED - use `imported=True` parameter
**Check**: Script uses `fs_client.create_conversation(fs_conversation, imported=True)`

### Tags Not Imported
**Status**: FIXED - tag import implemented
**Check**: Script calls `fs_client.update_conversation_tags()` after conversation creation

### Customer Not Found
**Status**: Check customer_mapping.json
**Solution**: Run `build_customer_mapping.py` or `extract_customer_mapping.py`

### Attachment Errors
**Status**: Check helpscout_attachments/ directory exists
**Solution**: Ensure Help Scout API access for attachment downloads

## Performance Notes

- Default: 10 concurrent threads
- Adjust with `--num-threads` parameter
- State file saves every ~10 conversations
- Rate limiting: 0.5s between Help Scout API calls
- No rate limiting on FreeScout (local instance)

## Security

- ✅ No credentials in code
- ✅ Credentials loaded from `.env` only
- ✅ Customer mapping files generated, not hardcoded
- ✅ No customer PII in git history
- ✅ `.gitignore` prevents accidental credential commits

## Next Steps

For future improvements:
1. Add database migration tracking to FreeScout
2. Implement conversation merge detection
3. Add custom field mapping
4. Create health check endpoint
5. Add webhook for automated resume on failure

## Support

For issues or questions:
1. Check `bulk_import_state.json` for failure details
2. Review console output for error messages
3. Check `.env` configuration
4. Verify customer_mapping.json exists and is valid
5. Run `test_single_conversation.py` to isolate issues

---

**Last Updated**: 2025-11-16
**Version**: 2.0 - Production Ready
**Status**: ✅ Ready for Full Migration
