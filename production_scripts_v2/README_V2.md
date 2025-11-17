# Production Scripts V2 - Help Scout to FreeScout Migration

This folder contains the refined production scripts for migrating Help Scout data to FreeScout with full attachment support.

## Overview

This is a complete, working pipeline that:
1. Downloads Help Scout data (customers, conversations, attachments) via API
2. Caches downloaded data locally
3. Merges cache into structured export folder
4. Maps customers between Help Scout and FreeScout
5. Tests single conversation imports with attachments
6. Supports bulk imports with proper thread and attachment handling

## Scripts

### 1. `update_export_from_cache.py` - Merge Cache into Export
**Purpose**: Take cached data and organize it into the export folder structure

**Usage**:
```bash
source ../venv/bin/activate && python update_export_from_cache.py
```

**Output**:
- Populates `helpscout_export/` folder with structured data
- Organizes conversations by date (YYYY/MM/DD)
- Merges new data with existing exports

### 2. `extract_customer_mapping.py` - Extract FreeScout Customers
**Purpose**: Read FreeScout customers from CSV and extract to JSON

**Usage**:
```bash
source ../venv/bin/activate && python extract_customer_mapping.py
```

**Input**:
- FreeScout customer CSV export (UTF-8 encoded)
- Expected at: `config/customers_2025-11-16_utf8.csv`

**Output**:
- `freescout_customers.json` - List of all FreeScout customers with id, first_name, last_name, email

### 3. `build_customer_mapping.py` - Create Permanent Customer Mapping
**Purpose**: Match Help Scout customers to FreeScout customers

**Usage**:
```bash
source ../venv/bin/activate && python build_customer_mapping.py
```

**Input**:
- Help Scout customers from `helpscout_export/customers/`
- FreeScout customers from `freescout_customers.json`

**Output**:
- `customer_mapping.json` - Permanent mapping of:
  - HS ID → FS ID
  - HS email → FS ID
  - Unmatched customers list
  - Match statistics (85.2% match rate in current data)

**Matching Strategy** (in order):
1. Email exact match (case-insensitive)
2. Full name match (first + last name)
3. Unmatched (created as placeholders)

### 4. `test_single_conversation.py` - Test Single Conversation Import
**Purpose**: Test importing a single conversation with threads and attachments

**Usage**:
```bash
# Test most recent conversation
source ../venv/bin/activate && python test_single_conversation.py

# Test specific conversation ID
source ../venv/bin/activate && python test_single_conversation.py 3132185360

# Test specific conversation with date hint
source ../venv/bin/activate && python test_single_conversation.py 3132185360 2025/11/6
```

**Features**:
- Extracts customer data from conversation's `primaryCustomer` field
- Maps all threads from `_embedded.threads`
- Loads and processes attachments from manifest
- Supports conversations with multiple threads and attachments
- Shows clear success/failure output

**Output**:
- Creates conversation in FreeScout
- Shows conversation ID mapping (HS ID → FS ID)
- Reports thread counts and attachments status

### 5. `bulk_import_conversations.py` - Bulk Import All Conversations
**Purpose**: Import all conversations from Help Scout export to FreeScout with multi-threading and resumable state

**Usage**:
```bash
# Test with 10 conversations (dry-run)
source ../venv/bin/activate && python bulk_import_conversations.py --max-conversations 10 --dry-run

# Import all conversations with 10 parallel threads
source ../venv/bin/activate && python bulk_import_conversations.py

# Resume a previous import (skip already imported)
source ../venv/bin/activate && python bulk_import_conversations.py --resume

# Custom thread count
source ../venv/bin/activate && python bulk_import_conversations.py --threads 5
```

**Features**:
- Multi-threaded import (10 parallel threads by default)
- Processes conversations newest-first automatically
- Requires customer mapping (run build_customer_mapping.py first)
- Extracts customer data from `primaryCustomer` field
- Maps all threads from `_embedded.threads`
- Handles attachments via manifest with base64 encoding
- **Resumable imports** - saves state after every 10 conversations
- Progress tracking and statistics
- Clean error reporting

**State Tracking**:
- Saves `bulk_import_state.json` with:
  - List of imported conversations (HS ID → FS ID mapping)
  - Failed conversation tracking with error messages
  - Import statistics and timestamps
- Use `--resume` flag to skip already imported conversations on re-runs

**Output**:
- Real-time progress updates every 10 conversations
- Final summary with success/failure counts
- Import rate statistics (conversations per second)
- State file for recovery

## Workflow - Step by Step

This folder contains scripts for:
1. **Merging cached Help Scout data** into structured export folders
2. **Mapping customers** between Help Scout and FreeScout
3. **Testing conversation imports** with threads and attachments

### Setup Steps (One-Time)

#### Step 1: Extract FreeScout Customers
```bash
cd production_scripts_v2
source ../venv/bin/activate
python extract_customer_mapping.py
```
This creates `freescout_customers.json` from your FreeScout CSV export.

#### Step 2: Create Permanent Customer Mapping
```bash
python build_customer_mapping.py
```
This creates `customer_mapping.json` with Help Scout ↔ FreeScout customer mappings (85% match rate in current data).

#### Step 3: Test Single Conversation Import
```bash
python test_single_conversation.py 3132185360
```
This tests the import pipeline with a real conversation including threads and attachments.

#### Step 4: Test Bulk Import (Optional, Recommended)

**Quick way (recommended):**
```bash
./test_bulk_import.sh
```
This runs the bulk import with only 10 conversations (actual import, not dry-run). Perfect for validating the pipeline before full import.

**Or manually:**
```bash
python bulk_import_conversations.py --max-conversations 10
```
This tests the bulk import with only 10 conversations (actual import, not dry-run).

#### Step 5: Run Full Bulk Import
```bash
python bulk_import_conversations.py
```
This imports all conversations in helpscout_export/ to FreeScout with 10 parallel threads.

#### Step 6 (If needed): Resume Partial Import
```bash
python bulk_import_conversations.py --resume
```
If the import was interrupted, this continues from where it left off by checking bulk_import_state.json.

### For Processing Downloaded Data

If you have Help Scout data cached in `helpscout_cache/`:

```bash
cd production_scripts_v2
python update_export_from_cache.py
```

This organizes cached data into the `helpscout_export/` folder structure (organized by date: YYYY/MM/DD).

## Key Features

### Customer Data
- Extracts customer info directly from conversation `primaryCustomer` field
- Supports customer mapping fallback for conversations without direct customer data
- Creates placeholder emails for customers without email addresses

### Thread Handling
- Maps Help Scout threads to FreeScout thread types (customer, message, note)
- Preserves thread content and timestamps
- Handles special types (lineitem) gracefully

### Attachment Support
- Automatically detects attachments from manifest
- Reads attachment files from disk
- Base64 encodes for API transport
- FreeScout limitation: Attachments only on first thread during conversation creation

## Troubleshooting

### Conversation Import Fails
1. Check customer data is present with `primaryCustomer` field
2. Verify threads exist in `_embedded.threads`
3. Check attachment manifest exists at `helpscout_attachments/manifest.json`

### Missing Customers
- Some Help Scout customers may not have matches in FreeScout
- These are logged in `customer_mapping.json` under `unmatched`
- Placeholder emails are created with pattern: `no-email-{hs_id}@migration.local`

### Attachment Issues
- File must exist at path specified in manifest
- Check manifest format: `conversations/{conv_id}/{thread_id}/filename`
- Verify file permissions are readable

## Data Flow Diagram

```
Help Scout API
    ↓
migrate.py (caches data locally)
    ↓
helpscout_cache/
    ↓
update_export_from_cache.py
    ↓
helpscout_export/
    ├── customers/
    ├── conversations/
    └── attachments/ (via manifest)
    ↓
build_customer_mapping.py
    ↓
customer_mapping.json
    ↓
test_single_conversation.py
    ↓
FreeScout API (creates conversation with threads & attachments)
```

## Success Metrics from Today's Testing

- ✅ Successfully extracted 4,813 FreeScout customers
- ✅ Created 3,689 customer mappings (85.2% match rate)
  - Email matches: 3,137
  - Name matches: 552
  - Unmatched: 643
- ✅ Tested single conversation import with attachments
- ✅ All 4 threads imported successfully
- ✅ Attachment (PDF) included in conversation

## Notes

- All scripts use relative imports, run from `production_scripts_v2/` folder
- Virtual environment must be activated: `source ../venv/bin/activate`
- FreeScout API URL and credentials configured in `api/freescout_client.py`
- Help Scout API credentials configured in environment/config

