# Attachment Handling Strategy

## The FreeScout Limitation

FreeScout has a **critical limitation**: **Attachments can only be added during conversation creation, and only to the first thread.**

This means:
- ✓ Attachments on the **first thread** → Can be included during conversation creation
- ✗ Attachments on **subsequent threads** → Cannot be added via API after thread creation
- ✗ **Adding attachments later** → Not supported (no `add_attachment` endpoint)

## Our Solution: Pre-Download Strategy

Since attachments must be included at conversation creation time, and we can only attach to the first thread, we use a **three-phase approach**:

### Phase 1: Extract Data (COMPLETE ✓)
- Extract all Help Scout conversations with full thread metadata
- Save to JSON files with attachment metadata (URLs, filenames, MIME types)
- No file downloading yet (just URLs)

### Phase 2: Download Attachments (download_attachments.py)
- Scan all extracted conversation JSON files
- Identify all attachment URLs
- Download files from Help Scout API
- Store locally in organized directory structure:
  ```
  helpscout_attachments/
  ├── [conversation_id]/
  │   └── [thread_id]/
  │       └── [filename]  (actual binary file)
  └── manifest.json  (mapping index)
  ```
- Create manifest.json for fast lookup during import

### Phase 3: Import to FreeScout (import_from_export_with_attachments.py - TBD)
- Import customers (4,304 customers)
- Import conversations with threads
- **For conversations with first-thread attachments**: Include file content when creating conversation
- **For conversations without attachments**: Normal import
- Track which conversations have attachments in FreeScout for reference

## Why Pre-Download?

1. **Speed**: Importing from local files is much faster than downloading during import
2. **Reliability**: Failed downloads don't block conversation creation
3. **Flexibility**: Can retry failed attachment downloads separately
4. **Better Visibility**: Know attachment status before import begins

## Directory Structure After Download

```
project/
├── helpscout_export/
│   ├── customers/
│   │   └── customers_batch_*.json
│   └── conversations/
│       └── [organized by date]
│
└── helpscout_attachments/
    ├── [1234567890]/              # Conversation ID
    │   ├── [9876543210]/          # First thread ID
    │   │   ├── image.gif
    │   │   ├── document.pdf
    │   │   └── ...
    │   ├── [9876543211]/          # Other threads (for reference only)
    │   │   └── ...
    │   └── ...
    │
    ├── manifest.json              # Quick lookup:
    │                              # {
    │                              #   "conversations": {
    │                              #     "1234567890": {
    │                              #       "9876543210": [
    │                              #         {
    │                              #           "filename": "image.gif",
    │                              #           "local_path": "helpscout_attachments/1234567890/9876543210/image.gif"
    │                              #         }
    │                              #       ]
    │                              #     }
    │                              #   }
    │                              # }
    │
    └── download_progress.json     # Resume capability
```

## How to Use

### Download all attachments:
```bash
python download_attachments.py
```

This will:
- Process all 3,600+ conversations
- Download all attachments found
- Show progress and skipped files
- Resume from last point if interrupted
- Create manifest.json for import phase

### Monitor progress:
- Check `helpscout_attachments/download_progress.json` for stats
- Check `helpscout_attachments/` directory for downloaded files
- Manifest at `helpscout_attachments/manifest.json`

## Limitations & Workarounds

### First-Thread-Only Limitation

**Status**: This is a FreeScout API limitation.

**What we can do**:
- ✓ Attach all files to first thread during conversation creation
- ✓ Download attachments from later threads for archival purposes
- ✓ Store attachment metadata so you know what's there
- ✗ Cannot automatically attach files to threads 2+ via API

**Workaround for critical attachments on later threads**:
- Manually move attachments in FreeScout UI after import
- Or: Prepend attachment filenames to later thread text as links
- Or: Add a note on the first thread listing all attachments from all threads

### Large Files

**Help Scout API has rate limits**:
- Implemented 0.1s delay between downloads
- Script tracks failures and can be resumed
- Retries individual file downloads if network issues occur

### Storage Space

**Estimated size**: ~500MB - 2GB (depending on attachment sizes)
- Most conversations won't have large files
- Check available disk space before running: `df -h`

## Next Steps

1. **Wait for extraction to complete** (currently running)
   - Last count: 3,587 conversations extracted

2. **Run attachment downloader**:
   ```bash
   python download_attachments.py 2>&1 | tee attachment_download.log
   ```

3. **Monitor progress**:
   - Check manifest.json growth
   - Watch download_progress.json for stats

4. **Import with attachments** (after downloader completes):
   ```bash
   python import_from_export_with_attachments.py 2>&1 | tee import.log
   ```

## Manifest.json Structure

The manifest.json file maps conversations and threads to local attachment files:

```json
{
  "created": "2025-11-09T...",
  "conversations": {
    "3128309850": {
      "8702365936": [
        {
          "id": 769094067,
          "filename": "blocked.gif",
          "size": 118,
          "mimeType": "image/gif",
          "local_path": "helpscout_attachments/3128309850/8702365936/blocked.gif"
        }
      ]
    }
  }
}
```

This allows the import script to:
1. Quickly find what attachments a conversation has
2. Load files from disk (fast)
3. Include them in conversation creation request
4. Avoid repeated API calls for the same files
