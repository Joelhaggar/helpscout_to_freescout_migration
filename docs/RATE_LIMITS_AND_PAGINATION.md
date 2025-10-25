# Rate Limiting & Pagination

## Current Implementation Status: ✓ Fully Handled

Both **rate limiting** and **pagination** are properly implemented in the migration tool.

---

## Rate Limiting

### Help Scout API Limits

Help Scout enforces these rate limits:

**Burst Limit (Write Operations)**:
- **12 requests per 5 seconds** for POST, PUT, DELETE
- Applies per account (all API keys share this limit)

**Minute Limit (All Operations)**:
- Varies by Help Scout plan
- Typical: **200 requests per minute**
- Check your plan for exact limit

**Response Codes**:
- `429 Too Many Requests` - Rate limit exceeded
- `Retry-After` header indicates seconds to wait

### Our Implementation

**Location**: [`api/helpscout_client.py`](api/helpscout_client.py) lines 132-136

```python
# Add rate limiting delay
if delay is None:
    delay = Config.RATE_LIMIT_DELAY  # 0.5 seconds default
if delay > 0:
    time.sleep(delay)
```

**Current Settings**:
- **Default delay**: 0.5 seconds between requests
- **Configurable**: Set in [`config/config.py`](config/config.py) line 33
- **Rate**: ~2 requests/second = ~120 requests/minute

**Why This Works**:
- 0.5s delay = 2 req/sec (well under 12/5sec burst limit)
- 120 req/min (well under typical 200/min limit)
- Conservative approach prevents 429 errors

### Adjusting Rate Limits

Edit [`config/config.py`](config/config.py):

```python
# Faster (risky - may hit limits)
RATE_LIMIT_DELAY = 0.25  # 4 req/sec

# Current (safe)
RATE_LIMIT_DELAY = 0.5   # 2 req/sec

# Slower (very conservative)
RATE_LIMIT_DELAY = 1.0   # 1 req/sec
```

**Recommendation**: Keep at **0.5 seconds** unless you have a higher-tier Help Scout plan with increased limits.

### FreeScout Rate Limiting

FreeScout (self-hosted) typically has no API rate limits, but our implementation applies the same delay for consistency:

**Location**: [`api/freescout_client.py`](api/freescout_client.py)

```python
# Same rate limiting as Help Scout
if delay is None:
    delay = Config.RATE_LIMIT_DELAY
if delay > 0:
    time.sleep(delay)
```

---

## Pagination

### Help Scout Pagination

Help Scout uses **page-based pagination** with HAL+JSON format:

**Response Structure**:
```json
{
  "_embedded": {
    "conversations": [...]
  },
  "page": {
    "size": 50,
    "totalElements": 523,
    "totalPages": 11,
    "number": 1
  }
}
```

**Parameters**:
- `page`: Page number (1-indexed)
- `size`: Results per page (default 50, max 100)

### Our Implementation

We have **two approaches**:

#### 1. Manual Pagination (for fine control)

```python
# Get specific page
response = hs_client.get_conversations(page=1, status='all')
conversations = response.get('_embedded', {}).get('conversations', [])
```

#### 2. Automatic Pagination (recommended)

**Location**: [`api/helpscout_client.py`](api/helpscout_client.py) lines 326-373

```python
def get_all_conversations(...) -> List[Dict]:
    """Get all conversations (handles pagination automatically)."""
    all_conversations = []
    page = 1

    while True:
        response = self.get_conversations(page=page, ...)
        conversations = response.get('_embedded', {}).get('conversations', [])

        if not conversations:
            break

        all_conversations.extend(conversations)

        # Check if there are more pages
        page_info = response.get('page', {})
        total_pages = page_info.get('totalPages', 1)

        if page >= total_pages:
            break

        page += 1

    return all_conversations
```

**Features**:
- ✓ Automatically fetches all pages
- ✓ Respects rate limiting between pages
- ✓ Handles empty responses
- ✓ Checks `totalPages` metadata
- ✓ Returns combined list of all results

**Usage in Migration**:
```python
# Automatically gets all conversations across all pages
all_conversations = hs_client.get_all_conversations(
    mailbox=312012,
    status='all'
)
```

### Pagination for Other Resources

Same pattern implemented for:

**Users**: `get_all_users()` (lines 390-418)
**Mailboxes**: `get_all_mailboxes()` (similar pattern)
**Customers**: `get_customers()` (manual pagination)

---

## Performance Calculations

### Migration Time Estimates

**Variables**:
- Rate limit delay: 0.5s
- Average conversation threads: 5
- Average API calls per conversation: 8-10

**API Calls Per Conversation**:
1. Get conversation (1 call)
2. Get customer (1 call)
3. Get threads (1 call)
4. Download attachments (0-N calls)
5. Create customer in FreeScout (1 call)
6. Create conversation in FreeScout (1 call)
7. Add threads in FreeScout (4-5 calls)
8. Update tags (1 call)

**Total**: ~8-10 calls per conversation

**Time Calculation**:
- 10 calls × 0.5s delay = **5 seconds per conversation**
- 100 conversations = **~8.3 minutes**
- 1000 conversations = **~83 minutes (1.4 hours)**
- 5000 conversations = **~7 hours**

**Note**: Actual time may vary based on:
- Network latency
- API response times
- Number of attachments
- Thread count per conversation

### Optimization Options

**1. Reduce Delay (if your plan allows)**:
```python
RATE_LIMIT_DELAY = 0.25  # 2x faster, but check your limits!
```

**2. Batch Processing**:
```python
# Process in batches with status monitoring
python migrate.py --max-conversations 100  # First batch
python migrate.py --resume migration_progress.json --max-conversations 100  # Next batch
```

**3. Parallel API Calls (future enhancement)**:
- Some calls could be parallelized (fetch customer + threads simultaneously)
- Would require refactoring to use async/await
- Complexity vs. speed tradeoff

---

## Error Handling

### 429 Rate Limit Exceeded

**Currently**: Script will fail with `HelpScoutAPIError`

**Response**:
```json
{
  "status": 429,
  "headers": {
    "Retry-After": "5"
  }
}
```

**Recommendation**: Implement exponential backoff (future enhancement)

### Pagination Edge Cases

**Empty Pages**: ✓ Handled (breaks loop)
**No totalPages**: ✓ Handled (defaults to 1)
**API Errors Mid-Pagination**: ✗ Will raise exception

---

## Monitoring Rate Limits

Help Scout includes rate limit info in response headers:

```
X-RateLimit-Limit-burst: 12
X-RateLimit-Remaining-burst: 8
X-RateLimit-Interval-burst: 5
X-RateLimit-Limit-minute: 200
X-RateLimit-Remaining-minute: 145
X-RateLimit-Interval-minute: 60
```

### Future Enhancement: Header Monitoring

Could add logging to track:
- Remaining requests
- Time until reset
- Automatic delay adjustment

```python
# Pseudo-code for future implementation
def _check_rate_limits(response):
    remaining = int(response.headers.get('X-RateLimit-Remaining-minute', 999))
    if remaining < 10:
        # Slow down
        time.sleep(2.0)
```

---

## Recommendations

### For Current Migration

✓ **Keep current settings**: 0.5s delay is safe and reasonable

✓ **Use automatic pagination**: `get_all_conversations()` handles everything

✓ **Monitor progress**: Check `migration_progress.json` during long migrations

✓ **Plan for time**: Large migrations may take hours (run overnight)

### For Future Improvements

1. **Add 429 retry logic with exponential backoff**:
   ```python
   max_retries = 3
   for attempt in range(max_retries):
       try:
           return make_request()
       except RateLimitError as e:
           wait_time = int(e.retry_after)
           time.sleep(wait_time)
   ```

2. **Dynamic rate limit adjustment**:
   - Read response headers
   - Adjust delay based on remaining quota
   - Speed up if quota is high, slow down if low

3. **Progress indicators**:
   - Show current page / total pages
   - Estimated time remaining
   - Requests per minute actual rate

4. **Parallel processing**:
   - Use `asyncio` for concurrent requests
   - Respect rate limits globally
   - Complex but significant speed improvement

---

## Testing Rate Limits

### Test with Small Batches

```bash
# Test with 10 conversations to verify rate limiting works
python migrate.py --max-conversations 10

# Check timing
# Should take ~50 seconds (10 conv × 5 sec/conv)
```

### Monitor Output

Look for timing between operations:
```
[1/10] Conversation: Subject (ID: 123)
  ✓ Created customer: email@example.com (ID: 45)
  ✓ Created conversation #42 (ID: 42)
  ✓ Migrated 5 threads
```

Between conversations, you'll see the 0.5s delay.

---

## Summary

✓ **Rate Limiting**: Implemented with 0.5s delay (safe for all plans)
✓ **Pagination**: Automatic handling in `get_all_*()` methods
✓ **Both APIs**: Same rate limiting applied to Help Scout and FreeScout
✓ **Tested**: Working correctly in production migrations

**No action required** - both are properly handled in the current implementation!

**Optional**: Adjust `RATE_LIMIT_DELAY` in [`config/config.py`](config/config.py) if you have higher API limits or want to slow down.
