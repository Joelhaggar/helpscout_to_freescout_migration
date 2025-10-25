# Help Scout to FreeScout Migration Tool

A comprehensive Python tool for migrating all your data from Help Scout to FreeScout, including customers, conversations, threads, tags, and attachments.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

✅ **Complete Data Migration**
- Customers with full profile information
- Conversations with all threads and replies
- Tags and conversation metadata
- File attachments (images, PDFs, documents)
- Conversation statuses (active, pending, closed)
- Agent assignments
- Timestamps preserved

✅ **Smart Migration**
- **Streaming pagination** - Processes conversations page-by-page to minimize memory usage
- **Caching** - Saves Help Scout API responses locally for faster re-runs
- **Crash recovery** - Resume from where you left off if interrupted
- **Incremental sync** - Only migrate new/modified conversations
- **Duplicate prevention** - Won't create duplicates on re-runs

✅ **Advanced Filtering**
- Exclude conversations by status (spam, closed, etc.)
- Exclude conversations by tags (low-priority, test, ignore, etc.)
- Filter by mailbox
- API-level filtering to reduce data transfer

✅ **Performance Optimized**
- Automatic rate limiting for Help Scout API (0.5s delay)
- No rate limiting for local FreeScout (instant updates)
- Automatic retry on timeouts with exponential backoff
- Progress saves every 10 conversations

## Prerequisites

- Python 3.8 or higher
- Help Scout account with API access ([create OAuth app](https://secure.helpscout.net/apps/custom/))
- FreeScout instance (local or remote)
- API credentials for both platforms

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/HelpScouttoFreeScoutSync.git
cd HelpScouttoFreeScoutSync
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env_example .env
```

Edit `.env` with your credentials:

```bash
# Help Scout API Configuration
Helpscout_client_id=your_helpscout_client_id_here
Helpscout_client_secret=your_helpscout_client_secret_here

# FreeScout API Configuration
Freescout_APIKey=your_freescout_api_key_here
Freescout_URL=http://localhost:8000
```

**How to get API credentials:**

- **Help Scout**: [Create OAuth App](https://secure.helpscout.net/apps/custom/) → Copy Client ID & Secret
- **FreeScout**: Settings → API → Generate API Key

### 5. Configure User & Mailbox Mapping

Create mapping configuration files from the examples:

```bash
cp config/user_mapping.json.example config/user_mapping.json
cp config/mailbox_mapping.json.example config/mailbox_mapping.json
```

Edit `config/user_mapping.json` with your actual user IDs:

```json
{
  "mapping": {
    "123456": 1,    // Help Scout User ID → FreeScout User ID
    "789012": 2
  }
}
```

Edit `config/mailbox_mapping.json` with your actual mailbox IDs:

```json
{
  "mapping": {
    "111111": 1     // Help Scout Mailbox ID → FreeScout Mailbox ID
  }
}
```

**Find Help Scout IDs**: Check URLs when viewing users/mailboxes

**Find FreeScout IDs**: Use API:
```bash
curl -H "X-FreeScout-API-Key: YOUR_KEY" http://localhost:8000/api/users
curl -H "X-FreeScout-API-Key: YOUR_KEY" http://localhost:8000/api/mailboxes
```

### 6. Test Migration

```bash
# Test with 10 conversations first
python migrate.py --max-conversations 10 --status active
```

### 7. Run Full Migration

```bash
# Recommended: Exclude spam and test conversations
python migrate.py --status all --exclude-status "spam" --exclude-tags "low-priority,test,ignore" --include-spam
```

## Usage

### Basic Commands

```bash
# Migrate all active conversations
python migrate.py --status active

# Migrate with filters (recommended for production)
python migrate.py --status all --exclude-status "spam" --exclude-tags "test,ignore"

# Resume after interruption
python migrate.py --resume migration_progress.json

# Incremental sync (only new/modified since last run)
python migrate.py --incremental --resume migration_progress.json

# Test with small batch
python migrate.py --max-conversations 10
```

### Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--status` | Filter by status | `--status active` |
| `--exclude-status` | Exclude specific statuses | `--exclude-status "spam,closed"` |
| `--exclude-tags` | Exclude tagged conversations | `--exclude-tags "test,ignore"` |
| `--include-spam` | Include spam (default: skip) | `--include-spam` |
| `--mailbox` | Filter by mailbox ID | `--mailbox 312012` |
| `--max-conversations` | Limit for testing | `--max-conversations 100` |
| `--resume` | Resume from progress file | `--resume migration_progress.json` |
| `--incremental` | Only sync modified | `--incremental` |
| `--modified-since` | Sync since specific date | `--modified-since "2025-10-20T00:00:00Z"` |

## Migration Workflow

### Pre-Cutover Testing

Perfect for testing FreeScout before permanently switching:

```bash
# 1. Initial migration (week 1)
python migrate.py --status active --exclude-tags "test,ignore"

# 2. Daily incremental syncs (weeks 2-4, while still using Help Scout)
python migrate.py --incremental --resume migration_progress.json

# 3. Final sync before cutover (cutover day)
python migrate.py --incremental --resume migration_progress.json

# 4. Switch to FreeScout permanently
```


## How It Works

### Data Flow

```
Help Scout API → Cache (JSON) → Transform → FreeScout API
                     ↓
              Resume from here if crashed
```

### Caching System

Conversation data is cached in `helpscout_cache/`:

```
helpscout_cache/
├── conversations_page_0001.json  (25 conversations)
├── conversations_page_0002.json  (25 conversations)
└── conversations_page_0391.json  (10 conversations)
```

**Benefits:**
- ✅ Instant loading on re-runs (no API calls to Help Scout)
- ✅ Fix scripts run without hitting Help Scout API
- ✅ Debugging - inspect raw data anytime
- ✅ Recovery - rebuild if FreeScout data is lost

### State Management

State tracked in `migration_progress.json`:

```json
{
  "stats": {
    "customers_migrated": 123,
    "conversations_migrated": 4868,
    "last_sync_time": "2025-10-24T17:37:26Z"
  },
  "conversation_mapping": {
    "3119294864": 162  // Help Scout ID → FreeScout ID
  },
  "processed_conversation_ids": [3119294864, ...]
}
```

Enables:
- Crash recovery
- Incremental syncs
- Duplicate prevention
- Progress tracking

## Performance

**8000 conversations (typical migration):**

| Phase | With Cache | Without Cache |
|-------|------------|---------------|
| Load Help Scout data | 30 seconds | 4 hours |
| Migrate to FreeScout | 2-3 hours | 2-3 hours |
| **Total** | **~3 hours** | **~7 hours** |

**Rate Limits:**
- Help Scout: 0.5s delay (120 req/min, under 200 limit)
- FreeScout: 0.0s delay (local, no limit)

## Known Limitations

### FreeScout API Limitations

1. **Attachments only work in initial thread**
   - FreeScout's `add_thread()` endpoint doesn't support attachments
   - **Solution**: Tool automatically reorders threads to put attachment thread first
   - Only first thread's attachments migrate (others need manual upload)

2. **Status auto-changes based on thread type**
   - If last thread added is from customer → status becomes "active"
   - **Solution**: Tool updates status after adding all threads

## Project Structure

```
HelpScouttoFreeScoutSync/
├── api/
│   ├── helpscout_client.py          # Help Scout API wrapper
│   └── freescout_client.py          # FreeScout API wrapper
├── config/
│   ├── config.py                    # Configuration loader
│   ├── user_mapping.json            # User ID mappings
│   └── mailbox_mapping.json         # Mailbox ID mappings
├── mapping/
│   └── mappers.py                   # Data transformations
├── utils/
│   └── filters.py                   # Conversation filtering
├── helpscout_cache/                 # Cached API responses
├── migrate.py                       # Main migration script
├── fix_conversation_statuses_v2.py  # Fix script for updates
├── migration_progress.json          # Migration state
└── .env                             # Your credentials
```

## Troubleshooting

### Common Issues

**"No module named 'requests'"**
```bash
pip install -r requirements.txt
```

**Migration stuck at "Fetching conversations..."**
- First API call with `status=all` can take 1-2 minutes for large datasets
- Subsequent pages load faster (especially from cache)

**400 Error when updating conversations**
- Fixed in latest version (adds `byUser` parameter automatically)


**No conversations found**
- Check tag names are exact match (case-sensitive)
- Try `--status all` instead of specific status
- Verify mailbox ID is correct
- Remove `--exclude-tags` temporarily

## Documentation

- **[FILTERING_GUIDE.md](FILTERING_GUIDE.md)** - Advanced filtering options
- **[STATE_MANAGEMENT.md](STATE_MANAGEMENT.md)** - State, recovery, incremental sync
- **[RATE_LIMITS_AND_PAGINATION.md](RATE_LIMITS_AND_PAGINATION.md)** - API limits & pagination

## API Documentation

- [Help Scout API Docs](https://developer.helpscout.com/mailbox-api/)
- [FreeScout API Docs](https://api-docs.freescout.net/)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test thoroughly
4. Submit a pull request

## License

MIT License - see LICENSE file

## Support

- Open an issue on GitHub
- Check documentation in repo
- Review [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) (if exists)

## Migration Checklist

- [ ] Install dependencies
- [ ] Configure `.env` with API credentials
- [ ] Set up user mapping
- [ ] Set up mailbox mapping
- [ ] Test with 10 conversations
- [ ] **Backup FreeScout database**
- [ ] Run full migration
- [ ] Validate results
- [ ] Fix any status issues
- [ ] Test FreeScout UI

---

**Ready for production migration!** ✓

Built to migrate from Help Scout to FreeScout while preserving all conversation history, customer data, and metadata.
