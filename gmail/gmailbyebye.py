#!/usr/bin/env python3
"""
Gmail Email Cleanup via Gmail API
Uses Gmail search queries for efficient filtering, then batch deletes.
"""
import os
import sys
import time
import base64
import zipfile
from datetime import datetime, timedelta
from collections import defaultdict
from email import message_from_bytes
from email.utils import parsedate_to_datetime

# Gmail API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Config
# Full mail access scope - required for batchDelete
SCOPES = ['https://mail.google.com/']
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_LOCAL = os.path.join(SCRIPT_DIR, ".gmail_cleanup_config")
CONFIG_FILE_HOME = os.path.expanduser("~/.gmail_cleanup_config")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.json")

# Defaults
DEFAULT_CONFIG = {
    "YEARS_OLD": 1,
    "CUTOFF_DATE": None,
    "DELETE_YEARS": None,  # Format: "2009-2015"
    "LABELS": None,  # Comma-separated: "INBOX,CATEGORY_PROMOTIONS"
    "BATCH_SIZE": 100,  # Gmail API allows up to 1000
    "EXCLUDE_SUBJECTS": None,  # Comma-separated keywords to exclude
    "EXCLUDE_SENDERS": None,  # Comma-separated, supports *@domain.com wildcards
}


def load_config():
    """Load settings from config file."""
    config = {
        "email": None,
        **DEFAULT_CONFIG
    }

    config_file = None
    if os.path.exists(CONFIG_FILE_LOCAL):
        config_file = CONFIG_FILE_LOCAL
    elif os.path.exists(CONFIG_FILE_HOME):
        config_file = CONFIG_FILE_HOME

    if config_file:
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    if key == "GMAIL_EMAIL":
                        config["email"] = value
                    elif key == "CUTOFF_DATE":
                        config["CUTOFF_DATE"] = value
                    elif key == "YEARS_OLD":
                        config["YEARS_OLD"] = int(value)
                    elif key == "BATCH_SIZE":
                        config["BATCH_SIZE"] = int(value)
                    elif key == "DELETE_YEARS":
                        config["DELETE_YEARS"] = value
                    elif key == "LABELS":
                        config["LABELS"] = value
                    elif key == "EXCLUDE_SUBJECTS":
                        config["EXCLUDE_SUBJECTS"] = value
                    elif key == "EXCLUDE_SENDERS":
                        config["EXCLUDE_SENDERS"] = value

        print(f"Loaded config from {config_file}")

    return config


def authenticate_gmail():
    """Authenticate with Gmail API using OAuth2."""
    creds = None

    # Load existing token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        # Check if token has the required scope
        if creds and creds.scopes and SCOPES[0] not in creds.scopes:
            print(f"Token has wrong scopes: {creds.scopes}")
            print(f"Need: {SCOPES}")
            print("Deleting old token and re-authenticating...")
            os.remove(TOKEN_FILE)
            creds = None

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Error: {CREDENTIALS_FILE} not found!")
                print("\nTo set up Gmail API access:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project and enable Gmail API")
                print("3. Create OAuth 2.0 credentials (Desktop app)")
                print("4. Download and save as credentials.json in this folder")
                sys.exit(1)

            print("Opening browser for Gmail authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_FILE}")

    return build('gmail', 'v1', credentials=creds)


def parse_delete_years(delete_years_str):
    """Parse DELETE_YEARS config value into start and end dates."""
    if "-" in delete_years_str:
        parts = delete_years_str.split("-")
        start_year = int(parts[0].strip())
        end_year = int(parts[1].strip())
    else:
        start_year = end_year = int(delete_years_str.strip())

    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year + 1, 1, 1)  # First day of next year

    return start_year, end_year, start_date, end_date


def build_search_query(config):
    """Build Gmail search query from config."""
    query_parts = []

    delete_years = config.get("DELETE_YEARS")
    if delete_years:
        start_year, end_year, start_date, end_date = parse_delete_years(delete_years)
        # Gmail uses YYYY/MM/DD format
        query_parts.append(f"after:{start_year}/1/1")
        query_parts.append(f"before:{end_year + 1}/1/1")
        description = f"years {start_year}-{end_year}"
    else:
        # Cutoff date mode
        if config.get("CUTOFF_DATE"):
            cutoff_date = datetime.strptime(config["CUTOFF_DATE"], "%d-%b-%Y")
        else:
            years = config.get("YEARS_OLD", 1)
            cutoff_date = datetime.now() - timedelta(days=years * 365)

        query_parts.append(f"before:{cutoff_date.strftime('%Y/%m/%d')}")
        description = f"before {cutoff_date.strftime('%Y-%m-%d')}"

    # Add label filter if specified
    labels = config.get("LABELS")
    if labels:
        label_list = [l.strip() for l in labels.split(",")]
        # Gmail search: in:inbox OR in:promotions
        label_queries = [f"in:{label.lower().replace('category_', '')}" for label in label_list]
        if len(label_queries) > 1:
            query_parts.append(f"({' OR '.join(label_queries)})")
        else:
            query_parts.append(label_queries[0])
        description += f" in {labels}"

    # Add exclusions (optional)
    exclusions = []

    exclude_subjects = config.get("EXCLUDE_SUBJECTS")
    if exclude_subjects:
        for subject in exclude_subjects.split(","):
            subject = subject.strip()
            if subject:
                # Quote subjects with spaces
                if " " in subject:
                    query_parts.append(f'-subject:"{subject}"')
                else:
                    query_parts.append(f"-subject:{subject}")
                exclusions.append(f"subject:{subject}")

    exclude_senders = config.get("EXCLUDE_SENDERS")
    if exclude_senders:
        for sender in exclude_senders.split(","):
            sender = sender.strip()
            if sender:
                # Convert *@domain.com to @domain.com for Gmail
                if sender.startswith("*"):
                    sender = sender[1:]  # Remove leading *
                query_parts.append(f"-from:{sender}")
                exclusions.append(f"from:{sender}")

    if exclusions:
        description += f" (excluding {len(exclusions)} patterns)"

    return " ".join(query_parts), description


def get_messages_by_query(service, query, max_results=None):
    """
    Get all message IDs matching a query.

    Args:
        service: Gmail API service
        query: Gmail search query
        max_results: Maximum messages to return (None for all)

    Returns:
        List of message IDs
    """
    print(f"Searching: {query}")

    message_ids = []
    page_token = None

    while True:
        try:
            results = service.users().messages().list(
                userId='me',
                q=query,
                pageToken=page_token,
                maxResults=500  # Max per page
            ).execute()

            messages = results.get('messages', [])
            message_ids.extend([m['id'] for m in messages])

            print(f"  Found {len(message_ids):,} messages so far...")

            if max_results and len(message_ids) >= max_results:
                message_ids = message_ids[:max_results]
                break

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        except HttpError as e:
            print(f"Error searching messages: {e}")
            break

    return message_ids


def get_message_details(service, message_id):
    """Get message date and subject for display/organizing."""
    try:
        msg = service.users().messages().get(
            userId='me',
            id=message_id,
            format='metadata',
            metadataHeaders=['Date', 'Subject']
        ).execute()

        headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
        date_str = headers.get('Date', '')
        subject = headers.get('Subject', '(no subject)')

        msg_date = None
        if date_str:
            try:
                msg_date = parsedate_to_datetime(date_str)
                if msg_date.tzinfo:
                    msg_date = msg_date.replace(tzinfo=None)
            except:
                pass

        return msg_date, subject

    except HttpError:
        return None, None


def get_full_message(service, message_id):
    """Get full message content for backup."""
    try:
        msg = service.users().messages().get(
            userId='me',
            id=message_id,
            format='raw'
        ).execute()

        raw = msg.get('raw', '')
        return base64.urlsafe_b64decode(raw)

    except HttpError as e:
        print(f"Error fetching message {message_id}: {e}")
        return None


def backup_emails_to_zip(service, message_ids, output_dir, delete_after=False, config=None):
    """
    Backup emails to monthly ZIP files containing EML files.

    Args:
        service: Gmail API service
        message_ids: List of message IDs to backup
        output_dir: Directory to write ZIP files to
        delete_after: If True, delete each batch after backing up
        config: Configuration dict

    Returns:
        (backed_up, deleted) tuple
    """
    os.makedirs(output_dir, exist_ok=True)

    total = len(message_ids)
    print(f"\nBacking up {total:,} emails to {output_dir}/")
    if delete_after:
        print("(Will delete each batch after backup)")

    batch_size = config.get("BATCH_SIZE", 100) if config else 100
    zip_email_counts = defaultdict(int)

    backed_up = 0
    deleted = 0
    consecutive_failures = 0
    max_failures = 5

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_ids = message_ids[batch_start:batch_end]

        print(f"\nProcessing batch {batch_start + 1}-{batch_end} ({backed_up:,}/{total:,} done)...")

        batch_emails = []  # [(zip_filename, eml_filename, content), ...]

        for i, msg_id in enumerate(batch_ids):
            try:
                # Get full message
                content = get_full_message(service, msg_id)
                if not content:
                    continue

                # Get date for organizing
                msg_date, subject = get_message_details(service, msg_id)
                if msg_date:
                    year, month = msg_date.year, msg_date.month
                    date_str = msg_date.strftime('%Y%m%d')
                else:
                    year, month = 1970, 1
                    date_str = "unknown"

                file_index = backed_up + len(batch_emails) + 1
                zip_filename = os.path.join(output_dir, f"emails_{year:04d}-{month:02d}.zip")
                eml_filename = f"msg_{file_index:06d}_{date_str}.eml"
                batch_emails.append((zip_filename, eml_filename, content))

                if (i + 1) % 20 == 0:
                    print(f"  Downloaded {i + 1}/{len(batch_ids)}...")

            except Exception as e:
                print(f"  Error on message {msg_id}: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    break

        if consecutive_failures >= max_failures:
            print("Too many failures, stopping.")
            break

        # Write batch to ZIP files
        batch_by_zip = defaultdict(list)
        for zip_filename, eml_filename, content in batch_emails:
            batch_by_zip[zip_filename].append((eml_filename, content))

        for zip_filename, emails in batch_by_zip.items():
            mode = 'a' if os.path.exists(zip_filename) else 'w'
            with zipfile.ZipFile(zip_filename, mode, zipfile.ZIP_DEFLATED) as zf:
                for eml_filename, content in emails:
                    zf.writestr(eml_filename, content)
            zip_email_counts[zip_filename] += len(emails)

        backed_up += len(batch_emails)
        consecutive_failures = 0

        # Delete batch if requested
        if delete_after and batch_emails:
            batch_msg_ids = batch_ids[:len(batch_emails)]
            print(f"  Deleting {len(batch_msg_ids)} messages...")

            try:
                delete_messages_batch(service, batch_msg_ids)
                deleted += len(batch_msg_ids)
                print(f"  Deleted {len(batch_msg_ids)} messages.")
            except Exception as e:
                print(f"  Delete failed: {e}")
                consecutive_failures += 1

        print(f"  Progress: {backed_up:,}/{total:,} ({100*backed_up/total:.1f}%)")

        # Brief pause between batches
        if batch_end < total:
            time.sleep(1)

    # Print summary
    print(f"\nBackup complete:")
    for zip_filename in sorted(zip_email_counts.keys()):
        count = zip_email_counts[zip_filename]
        size_mb = os.path.getsize(zip_filename) / 1024 / 1024
        print(f"  {os.path.basename(zip_filename)}: {count:,} emails, {size_mb:.1f} MB")

    print(f"\nTotal: {backed_up:,} emails backed up", end="")
    if delete_after:
        print(f", {deleted:,} deleted")
    else:
        print()

    return backed_up, deleted


def delete_messages_batch(service, message_ids):
    """
    Delete messages using Gmail batch delete API.

    Args:
        service: Gmail API service
        message_ids: List of message IDs to delete
    """
    # Gmail batchDelete moves to Trash
    # Use batchDelete for permanent deletion
    service.users().messages().batchDelete(
        userId='me',
        body={'ids': message_ids}
    ).execute()


def delete_messages_robust(service, message_ids, config):
    """
    Delete messages with robust error handling.

    Args:
        service: Gmail API service
        message_ids: List of message IDs to delete
        config: Configuration dict

    Returns:
        Total deleted count
    """
    batch_size = min(config.get("BATCH_SIZE", 100), 1000)  # Gmail API max is 1000
    consecutive_failures = 0
    max_failures = 10  # More retries for connection issues

    total = len(message_ids)
    deleted = 0
    batch_start = 0

    while batch_start < total:
        if consecutive_failures >= max_failures:
            print(f"Too many consecutive failures ({max_failures}), stopping.")
            break

        batch_end = min(batch_start + batch_size, total)
        batch_ids = message_ids[batch_start:batch_end]

        print(f"\nDeleting batch {batch_start + 1}-{batch_end} ({deleted:,}/{total:,} done)...")

        try:
            delete_messages_batch(service, batch_ids)
            deleted += len(batch_ids)
            consecutive_failures = 0
            print(f"  Deleted {len(batch_ids)} messages.")
            batch_start = batch_end  # Move to next batch only on success

        except HttpError as e:
            if e.resp.status == 429:
                # Rate limited
                wait_time = min(60 * (consecutive_failures + 1), 300)
                print(f"  Rate limited, waiting {wait_time} seconds...")
                time.sleep(wait_time)
            elif e.resp.status >= 500:
                # Server error
                wait_time = min(30 * (consecutive_failures + 1), 120)
                print(f"  Server error: {e}")
                print(f"  Waiting {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"  Error: {e}")
            consecutive_failures += 1

        except (ConnectionResetError, ConnectionError, OSError) as e:
            # Network errors - retry with backoff
            consecutive_failures += 1
            wait_time = min(30 * consecutive_failures, 120)
            print(f"  Connection error: {e}")
            print(f"  Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

        except Exception as e:
            # Catch-all for other errors
            consecutive_failures += 1
            wait_time = min(30 * consecutive_failures, 120)
            print(f"  Unexpected error: {e}")
            print(f"  Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

        # Brief pause between successful batches
        if consecutive_failures == 0 and batch_start < total:
            time.sleep(1)

    return deleted


def get_label_message_counts(service, labels):
    """Get message counts for specified labels."""
    counts = {}
    for label in labels:
        try:
            label_info = service.users().labels().get(
                userId='me',
                id=label.upper()
            ).execute()
            counts[label] = label_info.get('messagesTotal', 0)
        except HttpError:
            # Try with different case
            try:
                label_info = service.users().labels().get(
                    userId='me',
                    id=label
                ).execute()
                counts[label] = label_info.get('messagesTotal', 0)
            except:
                counts[label] = "unknown"
    return counts


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="GmailByeBye - Bulk delete Gmail emails via API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gmailbyebye.py                         # Preview what would be deleted
  python gmailbyebye.py --preview               # Same as above (explicit)
  python gmailbyebye.py --delete                # Actually delete emails
  python gmailbyebye.py --backup ./backup       # Backup only (no delete)
  python gmailbyebye.py --backup ./backup --delete  # Backup + delete each batch
  python gmailbyebye.py --unhinged              # No prompts, no mercy
        """
    )
    parser.add_argument("--preview", action="store_true",
                        help="Preview what would be deleted (default behavior)")
    parser.add_argument("--delete", action="store_true",
                        help="Actually delete emails")
    parser.add_argument("--unhinged", action="store_true",
                        help="No prompts, no mercy. Just delete.")
    parser.add_argument("--backup", metavar="OUTPUT_DIR",
                        help="Backup emails to monthly ZIP files (add --delete to also delete)")
    args = parser.parse_args()

    print("=" * 60)
    print("GmailByeBye - Gmail API Email Cleanup")
    print("=" * 60)

    config = load_config()

    # Unhinged mode implies delete
    if args.unhinged:
        args.delete = True
        print("\n" + "!" * 60)
        print("UNHINGED MODE ACTIVATED")
        print("No prompts. No mercy. Deleting all old emails.")
        print("!" * 60)
    elif not args.delete:
        print("\n" + "!" * 60)
        print("PREVIEW MODE - No emails will be deleted")
        print("Run with --delete to actually delete emails")
        print("!" * 60)

    # Authenticate
    print("\nAuthenticating with Gmail...")
    service = authenticate_gmail()

    # Get profile info
    try:
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress', 'unknown')
        total_messages = profile.get('messagesTotal', 0)
        print(f"Account: {email}")
        print(f"Total messages: {total_messages:,}")
    except HttpError as e:
        print(f"Error getting profile: {e}")
        return

    if total_messages == 0:
        print("No messages to process!")
        return

    # Show label counts if configured
    labels = config.get("LABELS")
    if labels:
        label_list = [l.strip() for l in labels.split(",")]
        print(f"\nTarget labels: {', '.join(label_list)}")
        counts = get_label_message_counts(service, label_list)
        for label, count in counts.items():
            print(f"  {label}: {count:,} messages")

    # Build search query and find messages
    query, description = build_search_query(config)
    print(f"\nSearching for emails: {description}")
    print(f"  Query: {query}")

    # Log active exclusions
    exclude_subjects = config.get("EXCLUDE_SUBJECTS")
    exclude_senders = config.get("EXCLUDE_SENDERS")
    if exclude_subjects or exclude_senders:
        print(f"\n  Active exclusion filters (these emails will be KEPT):")
        if exclude_subjects:
            for s in exclude_subjects.split(","):
                s = s.strip()
                if s:
                    print(f"    Skipping subjects containing: {s}")
        if exclude_senders:
            for s in exclude_senders.split(","):
                s = s.strip()
                if s:
                    print(f"    Skipping senders matching: {s}")

    message_ids = get_messages_by_query(service, query)
    messages_to_delete = len(message_ids)

    print()
    print("=" * 60)
    print(f"RESULT: Deleting {description}")
    print(f"  Messages to DELETE: {messages_to_delete:,}")
    print("=" * 60)

    if messages_to_delete == 0:
        print(f"\nNothing to delete! No emails match: {description}")
        return

    # Handle backup if requested
    if args.backup:
        print("\n" + "=" * 60)
        print("BACKUP REQUESTED")
        print("=" * 60)
        print(f"  Output directory: {args.backup}")
        print(f"  Emails to backup: {messages_to_delete:,}")
        if args.delete:
            print("  Mode: Backup + Delete (will delete each batch after backup)")
        else:
            print("  Mode: Backup only")

        # Estimate size
        est_size_gb = (messages_to_delete * 75 * 1024) / (1024**3)  # ~75KB avg for Gmail
        print(f"  Estimated size: ~{est_size_gb:.1f} GB (varies by email size)")

        if messages_to_delete > 10000:
            print(f"\n  WARNING: Backing up {messages_to_delete:,} emails will take a while!")

        if not args.unhinged:
            if args.delete:
                confirm = input("\nProceed with backup AND deletion? (y/N): ").strip().lower()
            else:
                confirm = input("\nProceed with backup? (y/N): ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                return

        backed_up, deleted = backup_emails_to_zip(
            service, message_ids, args.backup,
            delete_after=args.delete, config=config
        )

        if backed_up < messages_to_delete:
            print(f"\nWARNING: Only backed up {backed_up:,} of {messages_to_delete:,} emails!")

        print("\n" + "=" * 60)
        print("COMPLETE!")
        print(f"Backed up {backed_up:,} messages")
        if args.delete:
            print(f"Deleted {deleted:,} messages")
        print("=" * 60)
        return

    # No backup requested
    if not args.delete:
        print(f"\n[DRY RUN] Would delete {messages_to_delete:,} messages ({description})")
        print("\nTo actually delete, run with --delete or --unhinged")
        return

    # Confirm unless unhinged
    if not args.unhinged:
        print(f"\nAbout to delete {messages_to_delete:,} messages ({description}).")
        print("This cannot be undone!")
        confirm = input("Type 'DELETE' to confirm: ").strip()
        if confirm != "DELETE":
            print("Aborted.")
            return

    # Delete!
    print("\n" + "=" * 60)
    print(f"DELETING {description}...")
    print("=" * 60)

    total_deleted = delete_messages_robust(service, message_ids, config)

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print(f"Deleted {total_deleted:,} messages")
    print("=" * 60)


if __name__ == "__main__":
    main()
