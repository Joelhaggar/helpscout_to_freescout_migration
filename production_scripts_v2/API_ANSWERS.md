# FreeScout API Questions - Answers from Code Analysis

## Question 1: Customer ID vs Email for Conversation Import

**Q: When importing into the FreeScout API, do we need to send a customer ID or is just the email enough?**

**A: You must send the customer ID.**

### Evidence

From [freescout_client.py:208-228](api/freescout_client.py#L208-L228), the `create_conversation()` method accepts conversation data but doesn't auto-create customers:

```python
def create_conversation(self, conversation_data: Dict, imported: bool = False) -> Dict:
    """
    Create a new conversation with initial threads.

    Args:
        conversation_data: Conversation data with required fields:
            - subject
            - mailboxId
            - type (email, phone, chat)
            - status (active, closed, pending, spam)
            - threads: array of thread objects
            - createdAt (optional): ISO 8601 timestamp, requires imported=True
            - closedAt (optional): ISO 8601 timestamp for closed conversations
        imported: If True, allows setting createdAt and prevents auto-emails/notifications
    """
```

The conversation data structure expects a **customer object with an ID field**. From [import_from_local_export.py:495-500](import_from_local_export.py#L495-L500), we can see the actual format passed to the mapper:

```python
customer_for_conversation = {
    "id": fs_customer_id,              # ← REQUIRED: Customer ID
    "email": hs_customer.get('email', ''),
    "first_name": hs_customer.get('firstName') or hs_customer.get('first', ''),
    "last_name": hs_customer.get('lastName') or hs_customer.get('last', '')
}

fs_conv_data = map_conversation_to_freescout(hs_conv, customer_for_conversation)
result = self.fs_client.create_conversation(fs_conv_data)
```

### Implication for bulk_import_conversations.py

**We still need the customer mapping process** because conversations require a FreeScout customer ID to be created. The current bulk_import_conversations.py script attempts to create conversations with only email/name data, which will fail.

**The script needs to be updated to:**
1. Load the customer_mapping.json created by build_customer_mapping.py
2. Look up the HS customer ID to find the FS customer ID
3. Pass the FS customer ID in the conversation creation

---

## Question 2: Log File and State File for Resumable Imports

**Q: Does the script output a log file and a state file so that if we need to run the script a second time, we know which conversations have already been imported?**

**A: The current script does NOT. We will add this functionality.**

### Current Behavior
- The script has in-memory statistics (ImportStats class)
- Progress is printed to console
- No persistent state is saved
- If the script crashes or is stopped, all progress is lost

### Solution: Add State Tracking

We will implement:

1. **State File** (`bulk_import_state.json`):
   - Tracks which conversations have been imported
   - Updated after each successful import
   - Allows resuming on second run

2. **Log File** (`bulk_import.log`):
   - Detailed import results
   - Timestamps for each conversation
   - Error messages for failures
   - Final summary statistics

3. **Resume Capability**:
   - On startup, check if state file exists
   - Skip conversations already in the imported list
   - Resume from where the last run left off

### Example State File Format
```json
{
  "started_at": "2025-11-16T10:30:00Z",
  "last_updated_at": "2025-11-16T10:35:45Z",
  "imported_conversations": {
    "3132185360": "12345",    // HS ID → FS ID mapping
    "3132185361": "12346",
    "3132185362": "12347"
  },
  "failed_conversations": {
    "3132185363": "No primaryCustomer found",
    "3132185364": "Customer not found in mapping"
  },
  "statistics": {
    "total_found": 1000,
    "imported": 3,
    "failed": 2,
    "skipped": 995,
    "elapsed_seconds": 345.67
  }
}
```

---

## Recommended Next Steps

1. **Update bulk_import_conversations.py** to:
   - Load customer_mapping.json
   - Use FreeScout customer ID instead of just email
   - Add state file tracking (bulk_import_state.json)
   - Add detailed logging (bulk_import.log)
   - Implement resume capability on re-runs

2. **Test on small batch** first:
   ```bash
   python bulk_import_conversations.py --max-conversations 10
   ```

3. **Then run full import**:
   ```bash
   python bulk_import_conversations.py
   ```

4. **If needed, resume**:
   ```bash
   python bulk_import_conversations.py
   # Script will skip already-imported conversations
   ```
