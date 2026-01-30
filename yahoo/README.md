# YahooByeBye

Bulk delete Yahoo Mail emails via POP3. Bypasses Yahoo's 10,000 email IMAP limit.

## Why POP3?

Yahoo IMAP caps visible emails at 10,000 - older emails are completely hidden. POP3 can access ALL your emails (tested with 379,000+ messages).

## Setup

### 1. Enable POP3

In Yahoo Mail: Settings > More Settings > Ways to access Yahoo Mail > POP

### 2. Generate App Password

1. Go to https://login.yahoo.com/account/security
2. Under "App passwords", create one for "Other App"
3. Copy the generated password

### 3. Create Config File

Create `.yahoo_cleanup_config` in this folder:

```ini
YAHOO_EMAIL=your.email@yahoo.com
YAHOO_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Choose ONE deletion method:

# Option 1: Delete by year range
DELETE_YEARS=2009-2015

# Option 2: Delete before specific date
# CUTOFF_DATE=01-Jan-2024

# Option 3: Delete older than X years (default: 1)
# YEARS_OLD=1

# Batch size (default: 50, max: 50 - Yahoo kills larger)
BATCH_SIZE=50
```

## Usage

```bash
# Preview what would be deleted (default)
python3 yahoobyebye.py
python3 yahoobyebye.py --preview

# Actually delete (with confirmation prompt)
python3 yahoobyebye.py --delete

# Backup to monthly ZIP files, then delete
python3 yahoobyebye.py --backup ./email_backup --delete

# No prompts, no mercy
python3 yahoobyebye.py --unhinged
```

## Exclusion Filters (Optional)

Keep important emails from being deleted by adding filters to your config:

```ini
# Keep emails with these words in the subject
EXCLUDE_SUBJECTS=receipt,invoice,tax,confirmation

# Keep emails from these senders (wildcards supported)
EXCLUDE_SENDERS=*@government.gov,*@irs.gov,*@bank.com
```

**Performance warning:** When exclusion filters are active, each message's headers must be fetched individually via POP3 before deletion. This adds a network round-trip per message and will be significantly slower than unfiltered deletion.

## Yahoo POP3 Quirks

- Messages numbered 1 (oldest) to N (newest) in chronological order
- Deletions only commit on connection close (QUIT)
- Yahoo rejects large batch commits - max 50 per batch
- Server returns SYS/TEMP errors under load (handled with retry)
- POP3 only accesses Inbox

## Note

This tool permanently deletes emails. Use preview mode first to verify what will be deleted.
