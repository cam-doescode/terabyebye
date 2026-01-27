# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TeraByeBye** - Yahoo email bulk deletion tool using POP3. Exists because Yahoo! slashed storage from 1TB to 20GB and IMAP caps visible emails at 10,000. POP3 can see all messages (tested with 379k+).

## Running the Script

```bash
# Dry run (preview only)
python3 pop3_cleanup_fast.py

# Execute with confirmation
python3 pop3_cleanup_fast.py --execute

# Execute without prompts
python3 pop3_cleanup_fast.py --unhinged
```

## Configuration

Config file: `.yahoo_cleanup_config` (local) or `~/.yahoo_cleanup_config` (home)

Required fields:
- `YAHOO_EMAIL` - Yahoo email address
- `YAHOO_APP_PASSWORD` - App password (spaces removed automatically)

Optional fields:
- `CUTOFF_DATE` - Delete before this date (DD-Mon-YYYY format)
- `YEARS_OLD` - Delete emails older than X years (default: 1, ignored if CUTOFF_DATE set)
- `BATCH_SIZE` - Emails per batch (default: 100, max: 100 - Yahoo rejects larger)

## Architecture

Single-file script (`pop3_cleanup_fast.py`) with these key functions:

- `binary_search_cutoff()` - Finds the message number where emails transition from old to new (~20 iterations for any mailbox size)
- `delete_messages_robust()` - Batch deletion with reconnection handling, exponential backoff, and progress tracking by actual mailbox count
- `get_message_date()` - Uses POP3 TOP command to fetch only headers (fast)

## Yahoo POP3 Quirks

- Messages numbered 1 (oldest) to N (newest) - chronological order
- Deletions only commit on `QUIT` - if connection drops, nothing is deleted
- Yahoo rejects large batch commits with `-ERR Error in deleting message(s)`
- Server returns `SYS/TEMP` errors under load - requires retry with backoff
- POP3 only accesses Inbox (use IMAP for other folders if < 10k messages)

## Legacy Code

`legacy_code/` contains deprecated IMAP-based scripts that hit Yahoo's 10k cap.
