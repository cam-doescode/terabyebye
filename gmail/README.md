# GmailByeBye

Bulk delete Gmail emails via the Gmail API.

## Setup

### 1. Create Google Cloud Project & Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Navigate to **APIs & Services > Library**
4. Search for "Gmail API" and click **Enable**

### 2. Create OAuth 2.0 Credentials

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - Choose "External" user type
   - Fill in app name (e.g., "GmailByeBye")
   - Add your email as a test user
4. Select **Desktop app** as application type
5. Download the credentials JSON file
6. Save as `credentials.json` in this folder

### 3. Install Dependencies

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 4. Create Config File

Create `.gmail_cleanup_config` in this folder:

```ini
# Gmail account (optional - for reference)
GMAIL_EMAIL=your.email@gmail.com

# Choose ONE deletion method:

# Option 1: Delete by year range
DELETE_YEARS=2015-2020

# Option 2: Delete before specific date
# CUTOFF_DATE=01-Jan-2023

# Option 3: Delete older than X years (default: 1)
# YEARS_OLD=2

# Target specific labels (comma-separated)
# Common labels: INBOX, SENT, SPAM, TRASH, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL
LABELS=INBOX,CATEGORY_PROMOTIONS,CATEGORY_SOCIAL

# Batch size (default: 100, max: 1000)
BATCH_SIZE=100
```

## Usage

```bash
# Preview what would be deleted (default)
python3 gmailbyebye.py
python3 gmailbyebye.py --preview

# Actually delete (with confirmation prompt)
python3 gmailbyebye.py --delete

# Backup to monthly ZIP files, then delete
python3 gmailbyebye.py --backup ./email_backup --delete

# No prompts, no mercy
python3 gmailbyebye.py --unhinged
```

### First Run

On first run, a browser window will open for Google authorization. Grant access to allow the script to read and delete emails. A `token.json` file will be created to remember your authorization.

## Exclusion Filters (Optional)

Keep important emails from being deleted by adding filters to your config:

```ini
# Keep emails with these words in the subject
EXCLUDE_SUBJECTS=receipt,invoice,tax,confirmation

# Keep emails from these senders (wildcards supported)
EXCLUDE_SENDERS=*@government.gov,*@irs.gov,*@bank.com
```

Exclusions are handled by Gmail's search query (e.g., `-subject:receipt -from:@irs.gov`), so there's no performance penalty.

## Gmail Labels Reference

| Config Value | Gmail Folder |
|--------------|--------------|
| `INBOX` | Inbox |
| `SENT` | Sent |
| `SPAM` | Spam |
| `TRASH` | Trash |
| `CATEGORY_PROMOTIONS` | Promotions tab |
| `CATEGORY_SOCIAL` | Social tab |
| `CATEGORY_UPDATES` | Updates tab |
| `CATEGORY_FORUMS` | Forums tab |

## Files

| File | Purpose |
|------|---------|
| `gmailbyebye.py` | Main script |
| `.gmail_cleanup_config` | Your settings (gitignored) |
| `credentials.json` | OAuth client credentials (gitignored) |
| `token.json` | OAuth token (auto-generated, gitignored) |

## Note

This tool permanently deletes emails. Use preview mode first to verify what will be deleted.
