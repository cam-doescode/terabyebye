# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TeraByeBye** - Email bulk deletion tools for Yahoo Mail and Gmail. Created because email providers slashed storage limits and provide inadequate cleanup tools.

## Directory Structure

```
yahoo/          # Yahoo Mail tool (POP3)
gmail/          # Gmail tool (Gmail API)
legacy_code/    # Deprecated IMAP scripts
assets/         # Logo images
```

## Yahoo Tool (yahoo/)

### Running

```bash
cd yahoo
python3 terabyebye.py              # Preview
python3 terabyebye.py --delete     # Delete with confirmation
python3 terabyebye.py --backup ./backup --delete
python3 terabyebye.py --unhinged   # No prompts
```

### Config: `yahoo/.yahoo_cleanup_config`

```ini
YAHOO_EMAIL=user@yahoo.com
YAHOO_APP_PASSWORD=xxxx xxxx xxxx xxxx
DELETE_YEARS=2009-2015  # or CUTOFF_DATE or YEARS_OLD
BATCH_SIZE=50
```

### Key Functions

- `binary_search_date()` - Finds message boundaries (~20 iterations for any mailbox)
- `get_deletion_range()` - Determines what to delete based on config
- `backup_emails_to_zip()` - Downloads to monthly ZIP files (EML format)
- `delete_messages_robust()` - Batch deletion with retry/backoff

### Yahoo POP3 Quirks

- Messages numbered 1 (oldest) to N (newest)
- Deletions commit on QUIT - connection drop = no deletion
- Max 50 per batch (Yahoo kills larger)
- POP3 only accesses Inbox

## Gmail Tool (gmail/)

### Running

```bash
cd gmail
python3 gmailbyebye.py              # Preview
python3 gmailbyebye.py --delete     # Delete with confirmation
python3 gmailbyebye.py --backup ./backup --delete
python3 gmailbyebye.py --unhinged   # No prompts
```

### Config: `gmail/.gmail_cleanup_config`

```ini
GMAIL_EMAIL=user@gmail.com
DELETE_YEARS=2015-2020  # or CUTOFF_DATE or YEARS_OLD
LABELS=INBOX,CATEGORY_PROMOTIONS
BATCH_SIZE=100
```

### Setup

Requires OAuth2 credentials from Google Cloud Console:
1. Enable Gmail API
2. Create OAuth 2.0 credentials (Desktop app)
3. Save as `gmail/credentials.json`

### Key Functions

- `authenticate_gmail()` - OAuth2 flow
- `build_search_query()` - Builds Gmail search from config
- `get_messages_by_query()` - Finds messages using Gmail search
- `backup_emails_to_zip()` - Downloads to monthly ZIPs
- `delete_messages_robust()` - Batch deletion with retry/backoff

### Gmail API Notes

- Uses `gmail.modify` scope for read/delete
- Batch size up to 1000 (default: 100)
- Rate limited: handle 429 responses
- Can target specific labels

## Legacy Code

`legacy_code/` contains deprecated IMAP-based scripts that hit Yahoo's 10k cap.
