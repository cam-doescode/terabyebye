# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TeraByeBye** - Yahoo email bulk deletion tool using POP3. Exists because Yahoo! slashed storage from 1TB to 20GB and IMAP caps visible emails at 10,000. POP3 can see all messages (tested with 379k+).

## Running the Script

```bash
# Preview what would be deleted
python3 terabyebye.py
python3 terabyebye.py --preview    # Explicit

# Delete with confirmation
python3 terabyebye.py --delete

# Backup + delete each batch
python3 terabyebye.py --backup ./backup --delete

# No prompts, no mercy
python3 terabyebye.py --unhinged
```

## Configuration

Config file: `.yahoo_cleanup_config` (local) or `~/.yahoo_cleanup_config` (home)

Required fields:
- `YAHOO_EMAIL` - Yahoo email address
- `YAHOO_APP_PASSWORD` - App password (spaces removed automatically)

Optional fields (choose one deletion method):
- `DELETE_YEARS` - Delete emails from year range (e.g., "2009-2015")
- `CUTOFF_DATE` - Delete before this date (DD-Mon-YYYY format)
- `YEARS_OLD` - Delete emails older than X years (default: 1)
- `BATCH_SIZE` - Emails per batch (default: 50, max: 50 - Yahoo kills larger)

## Architecture

Single-file script (`terabyebye.py`) with these key functions:

- `binary_search_date()` - Finds message boundaries by date (~20 iterations for any mailbox size)
- `get_deletion_range()` - Determines what to delete based on config (year range or cutoff date)
- `backup_emails_to_zip()` - Downloads emails and saves to monthly ZIP files (EML format)
- `delete_messages_robust()` - Batch deletion with reconnection handling, exponential backoff, and progress tracking
- `get_message_date()` - Uses POP3 TOP command to fetch only headers (fast)

## Yahoo POP3 Quirks

- Messages numbered 1 (oldest) to N (newest) - chronological order
- Deletions only commit on `QUIT` - if connection drops, nothing is deleted
- Yahoo rejects large batch commits with `-ERR Error in deleting message(s)`
- Server returns `SYS/TEMP` errors under load - requires retry with backoff
- POP3 only accesses Inbox (use IMAP for other folders if < 10k messages)

## Legacy Code

`legacy_code/` contains deprecated IMAP-based scripts that hit Yahoo's 10k cap.
