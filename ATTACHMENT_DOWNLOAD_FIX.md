# Attachment Download Fix - Implementation Report

## Problem Identified

**Issue**: Downloaded attachment files were JSON-wrapped with base64-encoded data instead of binary files.

**Symptom**: When clicking an attachment in FreeScout UI, it showed `{"data":"JVBERi0xLjMK..."}` instead of opening a PDF.

**Root Cause**: Help Scout API attachment endpoint (`_links.data.href`) returns a JSON-wrapped response:
```json
{"data": "base64encodedcontent"}
```

The original download script was writing the entire JSON response to disk instead of extracting and decoding the base64 data.

## Solution Implemented

### File Modified
`download_attachments.py` - `download_file()` method (lines 81-126)

### Key Changes

1. **Added import**: Added `import base64` to handle base64 decoding

2. **Enhanced response handling**: Updated `download_file()` method to:
   - Try parsing response as JSON first
   - If JSON contains a `"data"` field with base64 content, decode it
   - Fall back to raw content if not JSON or doesn't have `"data"` field

```python
# Handle Help Scout API response format
# The API returns JSON-wrapped responses with base64-encoded data
file_content = response.content

try:
    # Try to parse as JSON first
    json_response = response.json()
    if isinstance(json_response, dict) and 'data' in json_response:
        # This is a JSON-wrapped response with base64 data
        # Decode the base64 data to get the actual file content
        file_content = base64.b64decode(json_response['data'])
except (json.JSONDecodeError, ValueError, TypeError):
    # Not JSON or doesn't have 'data' field, use raw content as-is
    pass

# Write file
with open(local_path, 'wb') as f:
    f.write(file_content)
```

## Verification

### Before Fix
File type: `JSON data`
File contents: `{"data":"JVBERi0xLjMK..."}`

### After Fix
File type: `PDF document, version 1.4, 1 page`
File size: ~41KB (legitimate PDF binary size)

Successfully verified with multiple downloads:
```
/Users/joel/DevProjects/HelpScouttoFreeScoutSync/helpscout_attachments/2435050359/7297790401/Purchase_Order_M7246_from_Domegaia_LLC.pdf: PDF document, version 1.4, 1 pages
/Users/joel/DevProjects/HelpScouttoFreeScoutSync/helpscout_attachments/2435051550/7297793616/Purchase_Order_GM7246_from_Domegaia_LLC.pdf: PDF document, version 1.4, 1 pages
/Users/joel/DevProjects/HelpScouttoFreeScoutSync/helpscout_attachments/2435055189/7297803305/Purchase_Order_M7247_from_Domegaia_LLC.pdf: PDF document, version 1.4, 1 pages
```

## Next Steps

1. **Re-download all attachments** (completed 2025-11-09 20:59):
   - Cleared corrupted `helpscout_attachments` directory
   - Ran corrected `download_attachments.py`
   - Script downloading all attachments with proper binary format

2. **Re-import conversations**: Once attachment downloads complete, the import process will use properly formatted attachments that will render correctly in FreeScout UI

## Files Affected
- `download_attachments.py` - ✅ Fixed (lines 21, 81-126)

## Impact
- Attachments will now display correctly as PDFs, images, etc. in FreeScout UI
- No changes needed to import process - it was already correctly handling properly-formatted attachments
- The fix ensures Help Scout API's JSON-wrapped response format is properly handled
