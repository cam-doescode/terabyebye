# TeraByeBye

**Yahoo! took your terabyte. Time to say bye-bye to old mail.**

Bulk delete old Yahoo Mail emails via POP3. Bypasses Yahoo's 10,000 email IMAP limit. Built because Yahoo! slashed storage from 1TB to 20GB and gave us terrible cleanup tools.

## Why This Exists

In 2024, Yahoo! reduced free email storage from 1TB to 20GB. If you're like me with 15+ years of emails, you suddenly need to delete hundreds of thousands of messages. But:

- Yahoo's web interface can only delete ~100 emails at a time
- Yahoo IMAP caps visible emails at 10,000 - older emails are **completely hidden**
- There's no official bulk delete tool

**TeraByeBye** uses POP3 to access ALL your emails (tested with 379,000+ messages) and delete them in bulk.

## Features

- **Binary search** to find the cutoff point (~20 checks instead of scanning all emails)
- **Robust reconnection** handling for large mailboxes
- **Batch processing** with automatic retry on connection drops
- **Dry-run mode** to preview before deleting
- **Unhinged mode** for when you just want it gone

## Setup

1. **Enable POP3** in Yahoo Mail settings (Settings > More Settings > Ways to access Yahoo Mail)

2. **Generate an App Password** at https://login.yahoo.com/account/security
   - Under "App passwords", create one for "Other App"

3. **Copy the config template:**
   ```bash
   cp .yahoo_cleanup_config.template .yahoo_cleanup_config
   ```

4. **Edit `.yahoo_cleanup_config`** with your credentials

## Usage

```bash
# Preview (dry run) - see what would be deleted
python3 pop3_cleanup_fast.py

# Actually delete (with confirmation prompt)
python3 pop3_cleanup_fast.py --execute

# No prompts, no mercy
python3 pop3_cleanup_fast.py --unhinged
```

## Configuration Options

Edit `.yahoo_cleanup_config` to customize:

| Option | Default | Description |
|--------|---------|-------------|
| `CUTOFF_DATE` | - | Delete emails before this date (DD-Mon-YYYY format) |
| `YEARS_OLD` | 1 | Delete emails older than X years (if CUTOFF_DATE not set) |
| `BATCH_SIZE` | 50 | Emails per batch (max 50 recommended - Yahoo drops larger batches) |

## How It Works

1. Connects via POP3 (which can see ALL emails, unlike IMAP's 10k limit)
2. Uses binary search to find where old emails end and new ones begin
3. Deletes in small batches with automatic retry on Yahoo's frequent connection drops
4. Tracks progress by actual mailbox count, so you can restart anytime

## Known Yahoo! Quirks

- Yahoo drops connections after ~50-100 deletions (handled automatically)
- Yahoo returns `SYS/TEMP` errors under load (retries with backoff)
- POP3 only accesses Inbox (use IMAP for other folders if < 10k messages)

## Note

This tool permanently deletes emails. Use dry-run mode first to preview what will be deleted.

## License

MIT - Do whatever you want with it. If it helps you escape Yahoo's storage prison, I'm happy.
