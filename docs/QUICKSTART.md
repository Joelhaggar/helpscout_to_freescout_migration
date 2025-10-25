# Quick Start Guide

## 1. Initial Setup (5 minutes)

### Install Dependencies

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### Verify Configuration

Your `.env` file should already be configured:
```env
Helpscout_client_id=YOUR_ID
Helpscout_client_secret=YOUR_SECRET
Freescout_APIKey=YOUR_KEY
Freescout_URL=http://localhost:8000
```

## 2. Test FreeScout Connection (10 minutes)

**IMPORTANT**: Make sure your FreeScout instance is running at `http://localhost:8000` before running tests.

### Run All Tests

```bash
./run_tests.sh
```

This will run three test suites:
1. Connection & Authentication
2. Customer API (create, retrieve, update)
3. Conversation API (create, add threads, update tags)

### Run Individual Tests

If you prefer to run tests individually:

```bash
# Test 1: Connection
python tests/test_freescout_connection.py

# Test 2: Customers
python tests/test_freescout_customer.py

# Test 3: Conversations
python tests/test_freescout_conversation.py
```

## 3. What the Tests Do

### Connection Test
- ✅ Validates API authentication
- ✅ Fetches mailboxes
- ✅ Fetches users
- ✅ Fetches tags

### Customer Test
- ✅ Creates a test customer
- ✅ Retrieves customer by ID
- ✅ Searches customer by email
- ✅ Updates customer details

### Conversation Test
- ✅ Creates conversation with initial thread
- ✅ Adds additional threads (agent reply, note)
- ✅ Updates conversation tags
- ✅ Retrieves conversation
- ✅ **Tests timestamp preservation** (critical for migration)

## 4. Expected Results

### ✅ All Tests Pass
```
Results: 3/3 tests passed
✓ All tests passed! FreeScout API is ready for migration.
```

**Action**: You're ready to proceed with the next phase (Help Scout integration).

### ⚠️ Timestamp Preservation Test Fails

If the conversation test shows:
```
✗ Custom timestamp NOT preserved (used server time)
```

**This is OK!** It means FreeScout doesn't accept custom timestamps. We'll handle this by:
- Prepending the original timestamp to thread text
- Example: `[Originally sent: 2023-05-15 10:30 AM] Thread content...`

### ❌ Tests Fail

**Common Issues**:

1. **Connection Failed**
   - Is FreeScout running?
   - Check URL: `http://localhost:8000`
   - Verify API key is correct

2. **401 Unauthorized**
   - API key is invalid
   - Regenerate API key in FreeScout admin panel

3. **404 Not Found**
   - Wrong FreeScout URL
   - Check if FreeScout is installed at a subdirectory

4. **No Mailboxes**
   - Create at least one mailbox in FreeScout
   - Go to: Settings → Mailboxes → Create Mailbox

## 5. Test Output Files

Tests will create test data:
- Test customers (will have emails like `test.customer.{timestamp}@example.com`)
- Test conversations (subjects starting with "Test Migration Conversation")

**Cleanup**: You can manually delete these from FreeScout UI after testing.

## 6. Next Steps

Once all tests pass:

1. **Create User Mapping** (see docs/UPDATED_PLAN_AND_RECOMMENDATIONS.md)
   - Map Help Scout users to FreeScout users
   - Create `config/user_mapping.json`

2. **Create Mailbox Mapping**
   - Map Help Scout mailboxes to FreeScout mailboxes
   - Create `config/mailbox_mapping.json`

3. **Build Help Scout Client**
   - Refactor existing extraction scripts
   - Create `api/helpscout_client.py`

4. **Create Data Mappers**
   - Build transformation functions
   - Create `mapping/mappers.py`

5. **Build Migration Script**
   - Create main orchestration script
   - Add progress tracking and logging

## 7. Troubleshooting

### FreeScout Not Running

Start your FreeScout instance:
```bash
# If using Docker
docker-compose up -d

# If using PHP built-in server
php artisan serve --port=8000
```

### Import Errors

Make sure you're in the virtual environment:
```bash
source venv/bin/activate
```

### Permission Errors

Ensure directories exist:
```bash
mkdir -p logs output
```

## 8. Getting Help

- Review the full plan: [docs/UPDATED_PLAN_AND_RECOMMENDATIONS.md](docs/UPDATED_PLAN_AND_RECOMMENDATIONS.md)
- Check existing Help Scout scripts: [docs/examples/HelpScoutDownload/](docs/examples/HelpScoutDownload/)
- Review API documentation:
  - FreeScout: https://api-docs.freescout.net/
  - Help Scout: https://developer.helpscout.com/

---

**Ready?** Run `./run_tests.sh` to get started!
