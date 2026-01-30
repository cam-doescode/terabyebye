<p align="center">
  <img src="assets/terabyebye-Yahoo.png" alt="TeraByeBye Logo" width="600">
</p>

# TeraByeBye

**Yahoo! took your terabyte. Time to say bye-bye to old mail.**

Bulk delete old emails via POP3 (Yahoo) and Gmail API / IMAP (Gmail). Built because Yahoo! slashed storage from 1TB to 20GB and gave us terrible cleanup tools.

> **New here?** Check out [GETTING_STARTED.md](GETTING_STARTED.md) for a beginner-friendly walkthrough with no technical jargon.

## Why This Exists

In 2024, Yahoo! reduced free email storage from 1TB to 20GB. If you're like me with 15+ years of emails, you suddenly need to delete hundreds of thousands of messages. But:

- Yahoo's web interface can only delete ~100 emails at a time
- Yahoo IMAP caps visible emails at 10,000 - older emails are **completely hidden**
- There's no official bulk delete tool

TeraByeBye uses POP3 to access ALL your Yahoo emails (tested with 379,000+ messages) and delete them in bulk. Now with Gmail support too.

## Features

- **Binary search** to find the cutoff point (~20 checks instead of scanning all emails)
- **Robust reconnection** handling for large mailboxes
- **Batch processing** with automatic retry on connection drops
- **Backup to ZIP** - export emails to monthly ZIP files before deletion
- **Safe mode** - backup + delete with extra safety checks and smaller batches
- **Dry-run mode** to preview before deleting
- **Unhinged mode** for when you just want it gone
- **Setup wizard** - interactive configuration, no config files to edit manually

## Quick Start

### Option 1: Setup Wizard (recommended)

```bash
python3 setup.py
```

The interactive wizard walks you through:
- Choosing your provider (Yahoo or Gmail)
- Entering credentials (tells you exactly where to get them)
- Configuring deletion rules
- Testing the connection

### Option 2: Manual Setup

See the [Yahoo](#yahoo-manual-setup) or [Gmail](#gmailbyebye) sections below for manual configuration.

## Usage

```bash
# Auto-detect provider and preview (safe - no changes made)
python3 terabyebye.py

# Safe mode: backup + delete with extra confirmations (recommended for first run)
python3 terabyebye.py --safe

# Delete with confirmation
python3 terabyebye.py --delete

# Force a specific provider
python3 terabyebye.py --yahoo --delete
python3 terabyebye.py --gmail --delete
python3 terabyebye.py --gmail-oauth --delete

# Backup + delete
python3 terabyebye.py --backup ./my_backup --delete

# No prompts, no mercy
python3 terabyebye.py --unhinged

# Check what's configured
python3 terabyebye.py --status

# Re-run setup wizard
python3 terabyebye.py --setup
```

Or run provider scripts directly:

```bash
cd yahoo
python3 yahoobyebye.py              # Preview
python3 yahoobyebye.py --safe       # Safe mode
python3 yahoobyebye.py --delete     # Delete
python3 yahoobyebye.py --unhinged   # No prompts
```

### Safe Mode

If this is your first time or you want extra protection, use `--safe`:

```bash
python3 terabyebye.py --safe
```

Safe mode automatically:
- **Backs up** all emails to ZIP files before deleting anything
- Uses **smaller batches** for more granular control
- Asks for **confirmation** before each step

### Backup

Use `--backup OUTPUT_DIR` to export emails:

```bash
# Just backup (no deletion)
python3 terabyebye.py --backup ./my_backup

# Backup + delete (deletes each batch after successful backup)
python3 terabyebye.py --backup ./my_backup --delete
```

Creates monthly ZIP files containing EML files:
```
./my_backup/
  emails_2009-01.zip
  emails_2009-02.zip
  ...
```

Each ZIP contains individual `.eml` files that can be opened in any email client or imported into other services.

When using `--backup --delete`, each batch is deleted immediately after being written to disk. This keeps memory low and ensures you don't lose emails if the process is interrupted - you'll have everything backed up that was deleted.

---

## Yahoo Manual Setup

1. **Enable POP3** in Yahoo Mail settings (Settings > More Settings > Ways to access Yahoo Mail)

2. **Generate an App Password** at https://login.yahoo.com/account/security
   - Under "App passwords", create one for "Other App"

3. **Copy the config template:**
   ```bash
   cd yahoo
   cp .yahoo_cleanup_config.template .yahoo_cleanup_config
   ```

4. **Edit `.yahoo_cleanup_config`** with your credentials

## Configuration Options

Edit `.yahoo_cleanup_config` to customize what gets deleted. Choose **one** method:

### Method 1: Delete by Year Range (NEW)
```ini
DELETE_YEARS=2009-2015
```
Deletes all emails from years 2009 through 2015, keeping emails before 2009 and after 2015.

### Method 2: Delete Before Date
```ini
CUTOFF_DATE=01-Jan-2024
```
Deletes all emails before January 1, 2024.

### Method 3: Delete by Age (default)
```ini
YEARS_OLD=1
```
Deletes emails older than 1 year. Only used if neither `DELETE_YEARS` nor `CUTOFF_DATE` is set.

### Performance Settings
| Option | Default | Description |
|--------|---------|-------------|
| `BATCH_SIZE` | 50 | Emails per batch (max 50 - Yahoo drops larger connections) |

## How It Works

1. Connects via POP3 (which can see ALL emails, unlike IMAP's 10k limit)
2. Uses binary search to find where old emails end and new ones begin
3. Deletes in small batches with automatic retry on Yahoo's frequent connection drops
4. Tracks progress by actual mailbox count, so you can restart anytime

## Known Yahoo! Quirks

- Yahoo drops connections after ~50-100 deletions (handled automatically)
- Yahoo returns `SYS/TEMP` errors under load (retries with backoff)
- POP3 only accesses Inbox (use IMAP for other folders if < 10k messages)

---

<p align="center">
  <img src="assets/terabyebye-Gmail.png" alt="GmailByeBye Logo" width="600">
</p>

# GmailByeBye

**Now with Gmail support!**

*Added because my wife had 45,000 "SALE ENDS TODAY!!!" emails from 2016 and Google kept asking her to pay for more storage. Honey, the sale ended 8 years ago. Let it go.*

Same great deletion power, now for Gmail. Two versions available:

### Quick Start (App Password - no dependencies)

```bash
cd gmail
cp .gmail_simple_config.template .gmail_simple_config
# Edit .gmail_simple_config with your email + App Password
python3 gmailbyebye-simple.py              # Preview
python3 gmailbyebye-simple.py --safe       # Safe: backup + delete
python3 gmailbyebye-simple.py --delete     # Delete
```

Just needs 2-Step Verification + an App Password from https://myaccount.google.com/apppasswords

### Full Version (OAuth2 - faster, more capable)

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
cd gmail
cp .gmail_cleanup_config.template .gmail_cleanup_config
# Set up Google Cloud OAuth credentials (see gmail/README.md)
python3 gmailbyebye.py                     # Preview
python3 gmailbyebye.py --safe              # Safe: backup + delete
python3 gmailbyebye.py --delete            # Delete
```

See [gmail/README.md](gmail/README.md) for detailed setup instructions for both versions.

## Gmail Usage

```bash
cd gmail

# Simple version (App Password / IMAP)
python3 gmailbyebye-simple.py              # Preview
python3 gmailbyebye-simple.py --safe       # Safe: backup + delete + confirmations
python3 gmailbyebye-simple.py --delete     # Delete with confirmation
python3 gmailbyebye-simple.py --backup ./backup --delete  # Backup + delete
python3 gmailbyebye-simple.py --unhinged   # No prompts, no mercy

# Full version (OAuth2 / Gmail API)
python3 gmailbyebye.py                     # Preview
python3 gmailbyebye.py --safe              # Safe: backup + delete + confirmations
python3 gmailbyebye.py --delete            # Delete with confirmation
python3 gmailbyebye.py --backup ./backup --delete  # Backup + delete
python3 gmailbyebye.py --unhinged          # No prompts, no mercy
```

### Gmail Features

- **Two auth options** - App Password / IMAP (easy) or OAuth2 / Gmail API (powerful)
- **Target specific labels** - INBOX, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL, etc.
- **Larger batches** - up to 1000 per batch with OAuth version (vs Yahoo's 50)
- **No binary search needed** - Gmail/IMAP search handles date filtering

---

## Disclaimer

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. BY USING THIS SOFTWARE, YOU ACKNOWLEDGE AND AGREE THAT:

- **Email deletion is permanent and irreversible.** The authors are not responsible for any lost, deleted, or corrupted emails.
- **You use this tool entirely at your own risk.** The authors assume no liability for errors, malfunctions, data loss, security vulnerabilities, or any other damages arising from the use of this software.
- **You are solely responsible for your credentials.** This tool requires access to your email account. The authors are not responsible for any unauthorized access, credential exposure, or security breaches.
- **No guarantee of correctness.** Date filtering, exclusion filters, and batch operations are best-effort. Always use preview mode first and back up anything important before deleting.
- **This is not an official product** of Yahoo, Google, or any email provider. It may break at any time due to provider changes.

Use preview mode (`--preview`) before deleting anything. When in doubt, use `--safe` or `--backup` first.

## License

MIT - Do whatever you want with it. If it helps you escape email storage prison, I'm happy.
