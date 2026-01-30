# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TeraByeBye** - Email bulk deletion tools for Yahoo Mail and Gmail. Created because email providers slashed storage limits and provide inadequate cleanup tools.

## Directory Structure

```
terabyebye.py   # Unified CLI wrapper (auto-detects provider)
setup.py         # Interactive setup wizard
yahoo/           # Yahoo Mail tool (POP3)
gmail/           # Gmail tool (Gmail API + IMAP)
legacy_code/     # Deprecated IMAP scripts
assets/          # Logo images
```

## Top-Level Scripts

### `terabyebye.py` - Unified CLI Wrapper

Auto-detects which providers are configured and routes to the right script. Supports `--yahoo`, `--gmail`, `--gmail-oauth` to force a provider, `--status` to check config, and `--setup` to launch the wizard. All other flags are passed through to the underlying script.

### `setup.py` - Interactive Setup Wizard

Walks users through provider selection, credential entry, deletion method config, exclusion filters, and connection testing. Run with `--status` to see what's configured.

## Yahoo Tool (yahoo/)

### Running

```bash
cd yahoo
python3 yahoobyebye.py              # Preview
python3 yahoobyebye.py --delete     # Delete with confirmation
python3 yahoobyebye.py --backup ./backup --delete
python3 yahoobyebye.py --unhinged   # No prompts
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

Two versions: `gmailbyebye.py` (OAuth2/API) and `gmailbyebye-simple.py` (App Password/IMAP).

### Running

```bash
cd gmail
# Simple version (App Password)
python3 gmailbyebye-simple.py              # Preview
python3 gmailbyebye-simple.py --delete     # Delete

# Full version (OAuth2)
python3 gmailbyebye.py              # Preview
python3 gmailbyebye.py --delete     # Delete
```

### Config: `gmail/.gmail_simple_config` (App Password version)

```ini
GMAIL_EMAIL=user@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
DELETE_YEARS=2015-2020
LABELS=INBOX
```

### Config: `gmail/.gmail_cleanup_config` (OAuth2 version)

```ini
GMAIL_EMAIL=user@gmail.com
DELETE_YEARS=2015-2020
LABELS=INBOX,CATEGORY_PROMOTIONS
BATCH_SIZE=100
```

### Setup (OAuth2 version)

Requires OAuth2 credentials from Google Cloud Console:
1. Enable Gmail API
2. Create OAuth 2.0 credentials (Desktop app)
3. Save as `gmail/credentials.json`

### Setup (Simple version)

1. Enable 2-Step Verification on Google Account
2. Generate App Password at https://myaccount.google.com/apppasswords
3. Enable IMAP in Gmail settings

## Legacy Code

`legacy_code/` contains deprecated IMAP-based scripts that hit Yahoo's 10k cap.
