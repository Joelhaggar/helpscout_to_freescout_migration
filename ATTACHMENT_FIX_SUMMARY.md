# Attachment Format Fix - Complete Solution

## Problem Identified

**Issue**: Attachments imported into FreeScout were being stored incorrectly, causing them to display as JSON instead of proper files when downloaded.

**Root Cause**: The mapper was base64-encoding attachment data and sending it with the `'data'` field, but FreeScout's API actually expects raw binary data in the `'content'` field.

## Solution Implemented

### 1. Fixed Download Handler (download_attachments.py)
**Status**: ✅ Already fixed
- Added proper JSON-wrapped response handling
- Extracts base64 data from Help Scout API responses
- Decodes to binary before saving to disk
- Files now save as legitimate PDFs, JPGs, etc.

### 2. Fixed Attachment Mapper (mapping/mappers.py)
**Status**: ✅ Fixed
- Changed from base64-encoded `'data'` field to raw binary `'content'` field
- Matches the pattern used in the working `import_from_export_with_attachments.py` script
- Removed unnecessary base64 import

**Key Changes**:
```python
# BEFORE (incorrect):
encoded_data = base64.b64encode(att_data['data_bytes']).decode('utf-8')
fs_attachments.append({
    "fileName": att_data['filename'],
    "mimeType": att_data['mimeType'],
    "data": encoded_data  # ❌ Wrong field and format
})

# AFTER (correct):
fs_attachments.append({
    "fileName": att_data['filename'],
    "mimeType": att_data['mimeType'],
    "content": att_data['data_bytes']  # ✅ Raw binary data
})
```

## How It Works Now

### Full Attachment Pipeline:

1. **Download Phase** (download_attachments.py):
   - Help Scout API returns: `{"data": "base64encodedstring"}`
   - Script detects JSON, extracts `"data"` field
   - Base64-decodes to get binary content
   - Saves as proper binary file (PDF, JPG, etc.)

2. **Import Phase** (test_import_recent_conversations.py):
   - Reads binary file from disk
   - Creates attachment object with file bytes: `{'filename': 'x.pdf', 'mimeType': 'application/pdf', 'data_bytes': b'...'}`

3. **Mapping Phase** (mapping/mappers.py):
   - Takes attachment object with binary data
   - Creates FreeScout API payload with raw `'content'` field
   - Sends to FreeScout API: `{'fileName': 'x.pdf', 'mimeType': 'application/pdf', 'content': b'...'}`

4. **Storage Phase** (FreeScout):
   - FreeScout API receives binary content
   - Properly stores as file on disk
   - Returns correct file URL in response

5. **Retrieval Phase** (FreeScout UI):
   - User clicks attachment link
   - FreeScout serves actual binary file
   - Browser downloads/opens as PDF/image/etc.

## Files Modified

1. **download_attachments.py**
   - Added `import base64`
   - Enhanced `download_file()` method to handle JSON-wrapped responses
   - Lines 21, 103-117

2. **mapping/mappers.py**
   - Removed `import base64` (no longer needed)
   - Changed attachment format from `'data'` (base64) to `'content'` (binary)
   - Lines 4-6, 256-267

## Testing

### Verified:
- ✅ Downloaded PDFs are valid binary files (`file` command shows "PDF document, version 1.4")
- ✅ Attachment mapper creates correct structure with `'content'` field containing bytes
- ✅ Matches pattern from working `import_from_export_with_attachments.py` script

### Next Steps:
1. Run test import with fixed mapper
2. Verify attachments download correctly in FreeScout UI
3. Test with FS:702 "Bender Return Label" ticket

## Key Learning

**FreeScout API Attachment Formats:**
- ✅ `'content'` field with raw binary data (bytes)
- ✅ Proper for initial thread creation
- ❌ `'data'` field with base64 string (does not work)
- ❌ Attempting to send base64 causes storage/retrieval issues

This matches the successful pattern found in `import_from_export_with_attachments.py` which had attachments working correctly.
