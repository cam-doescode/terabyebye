<p align="center">
  <img src="assets/terabyebye-Yahoo.png" alt="TeraByeBye Logo" width="600">
</p>

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
- **Backup to ZIP** - export emails to monthly ZIP files before deletion
- **Dry-run mode** to preview before deleting
- **Unhinged mode** for when you just want it gone

## Setup

1. **Enable POP3** in Yahoo Mail settings (Settings > More Settings > Ways to access Yahoo Mail)

2. **Generate an App Password** at https://login.yahoo.com/account/security
   - Under "App passwords", create one for "Other App"

3. **Copy the config template:**
   ```bash
   cd yahoo
   cp .yahoo_cleanup_config.template .yahoo_cleanup_config
   ```

4. **Edit `.yahoo_cleanup_config`** with your credentials

## Usage

```bash
cd yahoo

# Preview what would be deleted (default)
python3 terabyebye.py
python3 terabyebye.py --preview    # Same thing, explicit

# Actually delete (with confirmation prompt)
python3 terabyebye.py --delete

# Backup to monthly ZIP files, then delete
python3 terabyebye.py --backup ./email_backup --delete

# No prompts, no mercy
python3 terabyebye.py --unhinged
```

### Backup Option

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

Same great deletion power, now for Gmail. Uses the Gmail API for efficient batch operations and label-based filtering.

## Gmail Setup

1. **Install dependencies:**
   ```bash
   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
   ```

2. **Create Google Cloud credentials:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project and enable Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download as `gmail/credentials.json`

3. **Copy the config template:**
   ```bash
   cd gmail
   cp .gmail_cleanup_config.template .gmail_cleanup_config
   ```

4. **Edit config** with your target labels and date range

See [gmail/README.md](gmail/README.md) for detailed setup instructions.

## Gmail Usage

```bash
cd gmail

python3 gmailbyebye.py                    # Preview
python3 gmailbyebye.py --delete           # Delete with confirmation
python3 gmailbyebye.py --backup ./backup --delete  # Backup + delete
python3 gmailbyebye.py --unhinged         # No prompts, no mercy
```

### Gmail-Specific Features

- **Target specific labels** - INBOX, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL, etc.
- **Larger batches** - up to 1000 per batch (vs Yahoo's 50)
- **No binary search needed** - Gmail's search handles date filtering
- **OAuth2 authentication** - secure, no app passwords needed

---

## License

MIT - Do whatever you want with it. If it helps you escape email storage prison, I'm happy.
