#!/usr/bin/env python3
"""
Gmail Email Cleanup via IMAP (App Password)
Simple version - no OAuth, no Google Cloud project needed.
Just enable 2FA, generate an App Password, and go.
"""
import imaplib
import os
import ssl
import stat
import sys
import time
import zipfile
from datetime import datetime, timedelta
from collections import defaultdict
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from fnmatch import fnmatch

# Config
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_LOCAL = os.path.join(SCRIPT_DIR, ".gmail_simple_config")
CONFIG_FILE_HOME = os.path.expanduser("~/.gmail_simple_config")

# Defaults
DEFAULT_CONFIG = {
    "YEARS_OLD": 1,
    "CUTOFF_DATE": None,
    "DELETE_YEARS": None,  # Format: "2009-2015"
    "LABELS": None,  # Comma-separated: "INBOX,[Gmail]/Spam"
    "BATCH_SIZE": 100,
    "EXCLUDE_SUBJECTS": None,
    "EXCLUDE_SENDERS": None,
}


def load_config():
    """Load credentials and settings from config file."""
    config = {
        "email": None,
        "password": None,
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
                    elif key == "GMAIL_APP_PASSWORD":
                        config["password"] = value.replace(" ", "")
                    elif key == "CUTOFF_DATE":
                        config["CUTOFF_DATE"] = value
                    elif key == "YEARS_OLD":
                        val = int(value)
                        if val < 0:
                            print(f"Warning: YEARS_OLD cannot be negative, using default (1)")
                        else:
                            config["YEARS_OLD"] = val
                    elif key == "BATCH_SIZE":
                        val = int(value)
                        if val <= 0:
                            print(f"Warning: BATCH_SIZE must be positive, using default (100)")
                        else:
                            config["BATCH_SIZE"] = val
                    elif key == "DELETE_YEARS":
                        config["DELETE_YEARS"] = value
                    elif key == "LABELS":
                        config["LABELS"] = value
                    elif key == "EXCLUDE_SUBJECTS":
                        config["EXCLUDE_SUBJECTS"] = value
                    elif key == "EXCLUDE_SENDERS":
                        config["EXCLUDE_SENDERS"] = value

        print(f"Loaded config from {config_file}")

        # Warn if config file is readable by others (contains credentials)
        try:
            file_mode = os.stat(config_file).st_mode
            if file_mode & (stat.S_IRGRP | stat.S_IROTH):
                print(f"WARNING: {config_file} is readable by other users!")
                print(f"  Run: chmod 600 {config_file}")
        except OSError:
            pass

    return config


def connect_imap(config):
    """Connect to Gmail IMAP with App Password and explicit TLS settings."""
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=ctx)
    imap.login(config["email"], config["password"])
    return imap


def build_imap_search(config):
    """
    Build IMAP SEARCH criteria from config.

    Returns:
        (search_criteria, description)
    """
    criteria = []

    delete_years = config.get("DELETE_YEARS")
    if delete_years:
        if "-" in delete_years:
            parts = delete_years.split("-")
            start_year = int(parts[0].strip())
            end_year = int(parts[1].strip())
        else:
            start_year = end_year = int(delete_years.strip())

        # IMAP date format: DD-Mon-YYYY
        since_date = datetime(start_year, 1, 1).strftime("%d-%b-%Y")
        before_date = datetime(end_year + 1, 1, 1).strftime("%d-%b-%Y")
        criteria.append(f'SINCE {since_date}')
        criteria.append(f'BEFORE {before_date}')
        description = f"years {start_year}-{end_year}"
    else:
        if config.get("CUTOFF_DATE"):
            cutoff_date = datetime.strptime(config["CUTOFF_DATE"], "%d-%b-%Y")
        else:
            years = config.get("YEARS_OLD", 1)
            cutoff_date = datetime.now() - timedelta(days=years * 365)

        before_str = cutoff_date.strftime("%d-%b-%Y")
        criteria.append(f'BEFORE {before_str}')
        description = f"before {cutoff_date.strftime('%Y-%m-%d')}"

    return " ".join(criteria), description


def get_mailbox_folders(config):
    """
    Get list of IMAP folders to process from config.
    Maps common Gmail label names to IMAP folder names.
    """
    label_map = {
        "INBOX": "INBOX",
        "SENT": "[Gmail]/Sent Mail",
        "SPAM": "[Gmail]/Spam",
        "TRASH": "[Gmail]/Trash",
        "DRAFTS": "[Gmail]/Drafts",
        "ALL": "[Gmail]/All Mail",
        "STARRED": "[Gmail]/Starred",
        "IMPORTANT": "[Gmail]/Important",
        "CATEGORY_PROMOTIONS": "[Gmail]/Promotions",     # May not exist as IMAP folder
        "CATEGORY_SOCIAL": "[Gmail]/Social",
        "CATEGORY_UPDATES": "[Gmail]/Updates",
        "CATEGORY_FORUMS": "[Gmail]/Forums",
    }

    labels = config.get("LABELS")
    if not labels:
        return ["INBOX"]

    folders = []
    for label in labels.split(","):
        label = label.strip()
        # Map known labels or use as-is (for custom labels)
        folder = label_map.get(label.upper(), label)
        folders.append(folder)

    return folders


def parse_exclusions(config):
    """Parse exclusion config into lists."""
    subject_keywords = None
    sender_patterns = None

    exclude_subjects = config.get("EXCLUDE_SUBJECTS")
    if exclude_subjects:
        subject_keywords = [s.strip().lower() for s in exclude_subjects.split(",") if s.strip()]

    exclude_senders = config.get("EXCLUDE_SENDERS")
    if exclude_senders:
        sender_patterns = [s.strip().lower() for s in exclude_senders.split(",") if s.strip()]

    return subject_keywords, sender_patterns


def should_exclude(subject, sender, subject_keywords, sender_patterns):
    """Check if a message should be excluded from deletion."""
    if subject_keywords:
        subject_lower = subject.lower()
        for keyword in subject_keywords:
            if keyword in subject_lower:
                return True

    if sender_patterns:
        sender_lower = sender.lower()
        if "<" in sender_lower and ">" in sender_lower:
            sender_email = sender_lower.split("<")[1].split(">")[0]
        else:
            sender_email = sender_lower.strip()

        for pattern in sender_patterns:
            if fnmatch(sender_email, pattern):
                return True

    return False


def get_message_headers(imap, uid):
    """Fetch Subject and From headers for a message UID."""
    try:
        status, data = imap.uid('FETCH', uid, '(BODY.PEEK[HEADER.FIELDS (Subject From Date)])')
        if status != 'OK' or not data or not data[0]:
            return "", "", None

        header_data = data[0][1] if isinstance(data[0], tuple) else data[0]
        if isinstance(header_data, bytes):
            header_data = header_data.decode('utf-8', errors='replace')

        subject = ""
        sender = ""
        msg_date = None

        for line in header_data.split('\r\n'):
            lower = line.lower()
            if lower.startswith('subject:'):
                subject = line[8:].strip()
            elif lower.startswith('from:'):
                sender = line[5:].strip()
            elif lower.startswith('date:'):
                date_str = line[5:].strip()
                try:
                    msg_date = parsedate_to_datetime(date_str)
                    if msg_date.tzinfo:
                        msg_date = msg_date.replace(tzinfo=None)
                except Exception:
                    pass

        return subject, sender, msg_date

    except Exception:
        return "", "", None


def search_messages(imap, folder, search_criteria):
    """
    Search for messages in a folder matching criteria.

    Returns:
        List of message UIDs
    """
    try:
        status, _ = imap.select(f'"{folder}"')
        if status != 'OK':
            print(f"  Could not select folder: {folder}")
            return []
    except imaplib.IMAP4.error as e:
        print(f"  Error selecting folder '{folder}': {e}")
        return []

    try:
        status, data = imap.uid('SEARCH', None, search_criteria)
        if status != 'OK':
            print(f"  Search failed in {folder}")
            return []

        uids = data[0].split()
        return [uid.decode() for uid in uids]

    except imaplib.IMAP4.error as e:
        print(f"  Search error in {folder}: {e}")
        return []


def delete_messages_batch(imap, uids):
    """Mark messages as deleted and expunge."""
    uid_set = ','.join(uids)
    status, _ = imap.uid('STORE', uid_set, '+FLAGS', '(\\Deleted)')
    if status != 'OK':
        raise Exception(f"Failed to flag messages for deletion")
    imap.expunge()


def backup_emails_to_zip(imap, folder, uids, output_dir, delete_after=False, config=None):
    """
    Backup emails to monthly ZIP files containing EML files.

    Args:
        imap: IMAP connection
        folder: Current IMAP folder
        uids: List of message UIDs to backup
        output_dir: Directory to write ZIP files to
        delete_after: If True, delete each batch after backing up
        config: Configuration dict

    Returns:
        (backed_up, deleted) tuple
    """
    os.makedirs(output_dir, exist_ok=True)

    total = len(uids)
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
        batch_uids = uids[batch_start:batch_end]

        print(f"\nProcessing batch {batch_start + 1}-{batch_end} ({backed_up:,}/{total:,} done)...")

        batch_emails = []
        batch_successful_uids = []

        for i, uid in enumerate(batch_uids):
            try:
                # Fetch full message
                status, data = imap.uid('FETCH', uid, '(RFC822)')
                if status != 'OK' or not data or not data[0]:
                    continue

                content = data[0][1] if isinstance(data[0], tuple) else data[0]

                # Get date for organizing
                _, _, msg_date = get_message_headers(imap, uid)
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
                batch_successful_uids.append(uid)

                if (i + 1) % 20 == 0:
                    print(f"  Downloaded {i + 1}/{len(batch_uids)}...")

            except Exception as e:
                print(f"  Error on UID {uid}: {e}")
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
        if delete_after and batch_successful_uids:
            print(f"  Deleting {len(batch_successful_uids)} messages...")
            try:
                delete_messages_batch(imap, batch_successful_uids)
                deleted += len(batch_successful_uids)
                print(f"  Deleted {len(batch_successful_uids)} messages.")
            except Exception as e:
                print(f"  Delete failed: {e}")
                consecutive_failures += 1

        print(f"  Progress: {backed_up:,}/{total:,} ({100*backed_up/total:.1f}%)")

        # Brief pause between batches
        if batch_end < total:
            time.sleep(0.5)

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


def delete_messages_robust(imap, folder, uids, config):
    """
    Delete messages with robust error handling and exclusion support.

    Args:
        imap: IMAP connection
        folder: Current IMAP folder
        uids: List of message UIDs to delete
        config: Configuration dict

    Returns:
        Total deleted count
    """
    batch_size = min(config.get("BATCH_SIZE", 100), 1000)
    consecutive_failures = 0
    max_failures = 10

    # Parse exclusions
    subject_keywords, sender_patterns = parse_exclusions(config)
    has_exclusions = subject_keywords or sender_patterns

    total = len(uids)
    deleted = 0
    skipped = 0
    batch_start = 0

    while batch_start < total:
        if consecutive_failures >= max_failures:
            print(f"Too many consecutive failures ({max_failures}), stopping.")
            break

        batch_end = min(batch_start + batch_size, total)
        batch_uids = uids[batch_start:batch_end]

        print(f"\nProcessing batch {batch_start + 1}-{batch_end} ({deleted:,}/{total:,} done)...")

        try:
            # Filter by exclusions if needed
            uids_to_delete = []

            if has_exclusions:
                for uid in batch_uids:
                    subject, sender, _ = get_message_headers(imap, uid)
                    if should_exclude(subject, sender, subject_keywords, sender_patterns):
                        skipped += 1
                        if skipped <= 10:
                            print(f"  KEPT: \"{subject[:50]}\" from {sender[:40]}")
                        elif skipped == 11:
                            print(f"  (suppressing further exclusion messages...)")
                    else:
                        uids_to_delete.append(uid)
            else:
                uids_to_delete = batch_uids

            if uids_to_delete:
                delete_messages_batch(imap, uids_to_delete)
                deleted += len(uids_to_delete)
                print(f"  Deleted {len(uids_to_delete)} messages.")

            consecutive_failures = 0
            batch_start = batch_end

        except imaplib.IMAP4.error as e:
            consecutive_failures += 1
            wait_time = min(30 * consecutive_failures, 120)
            print(f"  IMAP error: {e}")
            print(f"  Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

            # Reconnect
            try:
                imap = connect_imap(config)
                imap.select(f'"{folder}"')
                print("  Reconnected.")
            except Exception as re:
                print(f"  Reconnect failed: {re}")

        except (ConnectionResetError, ConnectionError, OSError) as e:
            consecutive_failures += 1
            wait_time = min(30 * consecutive_failures, 120)
            print(f"  Connection error: {e}")
            print(f"  Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

            # Reconnect
            try:
                imap = connect_imap(config)
                imap.select(f'"{folder}"')
                print("  Reconnected.")
            except Exception as re:
                print(f"  Reconnect failed: {re}")

        except Exception as e:
            consecutive_failures += 1
            wait_time = min(30 * consecutive_failures, 120)
            print(f"  Unexpected error: {e}")
            print(f"  Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

        # Brief pause between successful batches
        if consecutive_failures == 0 and batch_start < total:
            time.sleep(0.5)

    if skipped > 0:
        print(f"\nExcluded {skipped:,} messages matching filters")

    return deleted


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="GmailByeBye Simple - Gmail cleanup via IMAP (App Password)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gmailbyebye-simple.py                         # Preview what would be deleted
  python gmailbyebye-simple.py --preview               # Same as above (explicit)
  python gmailbyebye-simple.py --safe                  # Backup + delete with extra safety checks
  python gmailbyebye-simple.py --delete                # Actually delete emails
  python gmailbyebye-simple.py --backup ./backup       # Backup only (no delete)
  python gmailbyebye-simple.py --backup ./backup --delete  # Backup + delete each batch
  python gmailbyebye-simple.py --unhinged              # No prompts, no mercy
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
    parser.add_argument("--safe", action="store_true",
                        help="Safety mode: backup first, smaller batches, extra confirmations")
    args = parser.parse_args()

    print("=" * 60)
    print("GmailByeBye Simple - Gmail IMAP Email Cleanup")
    print("(App Password version - no OAuth needed)")
    print("=" * 60)

    config = load_config()
    if not config["email"] or not config["password"]:
        print("Error: Could not load credentials from config file")
        print(f"\nCreate {CONFIG_FILE_LOCAL} with:")
        print("  GMAIL_EMAIL=your_email@gmail.com")
        print("  GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx")
        print("\nGenerate an App Password at:")
        print("  https://myaccount.google.com/apppasswords")
        print("  (requires 2-Step Verification enabled)")
        sys.exit(1)

    # Safe mode: backup + delete with extra guardrails
    if args.safe:
        args.delete = True
        if not args.backup:
            args.backup = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_backup")
        config["BATCH_SIZE"] = min(config.get("BATCH_SIZE", 100), 50)
        print("\n" + "=" * 60)
        print("SAFE MODE")
        print("  - All emails will be backed up before deletion")
        print(f"  - Backup directory: {args.backup}")
        print(f"  - Batch size: {config['BATCH_SIZE']} (smaller for safety)")
        print("  - Extra confirmation prompts enabled")
        print("=" * 60)

    # Unhinged mode implies delete
    elif args.unhinged:
        args.delete = True
        print("\n" + "!" * 60)
        print("UNHINGED MODE ACTIVATED")
        print("No prompts. No mercy. Deleting all old emails.")
        print("!" * 60)
    elif args.delete and not args.backup:
        print("\n" + "-" * 60)
        print("TIP: Consider using --safe or --backup to save copies first.")
        print("     Deleted emails cannot be recovered!")
        print("-" * 60)
    elif not args.delete:
        print("\n" + "!" * 60)
        print("PREVIEW MODE - No emails will be deleted")
        print("Run with --delete to actually delete emails")
        print("Run with --safe for guided backup + deletion")
        print("!" * 60)

    # Connect
    print(f"\nConnecting to {IMAP_SERVER}...")
    try:
        imap = connect_imap(config)
    except imaplib.IMAP4.error as e:
        print(f"Login failed: {e}")
        print("\nCheck your email and App Password.")
        print("Make sure IMAP is enabled in Gmail settings.")
        sys.exit(1)

    print(f"Logged in as {config['email']}")

    # Get folders to process
    folders = get_mailbox_folders(config)
    print(f"Target folders: {', '.join(folders)}")

    # Build search criteria
    search_criteria, description = build_imap_search(config)
    print(f"\nSearching for emails: {description}")
    print(f"  IMAP search: {search_criteria}")

    # Log active exclusions
    subject_keywords, sender_patterns = parse_exclusions(config)
    if subject_keywords or sender_patterns:
        exclusion_count = len(subject_keywords or []) + len(sender_patterns or [])
        print(f"\n  Active exclusion filters ({exclusion_count} patterns):")
        print(f"  NOTE: Each message will be checked before deletion (slower).")
        if subject_keywords:
            print(f"  Excluding subjects containing: {', '.join(subject_keywords)}")
        if sender_patterns:
            print(f"  Excluding senders matching: {', '.join(sender_patterns)}")

    # Search all folders
    all_results = {}  # {folder: [uids]}
    total_found = 0

    for folder in folders:
        print(f"\nSearching {folder}...")
        uids = search_messages(imap, folder, search_criteria)
        if uids:
            all_results[folder] = uids
            total_found += len(uids)
            print(f"  Found {len(uids):,} messages")
        else:
            print(f"  No matching messages")

    print()
    print("=" * 60)
    print(f"RESULT: Deleting {description}")
    for folder, uids in all_results.items():
        print(f"  {folder}: {len(uids):,} messages")
    print(f"  TOTAL to DELETE: {total_found:,}")
    print("=" * 60)

    if total_found == 0:
        print(f"\nNothing to delete! No emails match: {description}")
        imap.logout()
        return

    # Handle backup if requested
    if args.backup:
        print("\n" + "=" * 60)
        print("BACKUP REQUESTED")
        print("=" * 60)
        print(f"  Output directory: {args.backup}")
        print(f"  Emails to backup: {total_found:,}")
        if args.delete:
            print("  Mode: Backup + Delete (will delete each batch after backup)")
        else:
            print("  Mode: Backup only")

        est_size_gb = (total_found * 75 * 1024) / (1024**3)
        print(f"  Estimated size: ~{est_size_gb:.1f} GB (varies by email size)")

        if total_found > 10000:
            print(f"\n  WARNING: Backing up {total_found:,} emails will take a while!")

        if not args.unhinged:
            if args.delete:
                confirm = input("\nProceed with backup AND deletion? (y/N): ").strip().lower()
            else:
                confirm = input("\nProceed with backup? (y/N): ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                imap.logout()
                return

        total_backed_up = 0
        total_deleted = 0

        for folder, uids in all_results.items():
            print(f"\n--- Processing {folder} ---")
            imap.select(f'"{folder}"')
            backed_up, deleted_count = backup_emails_to_zip(
                imap, folder, uids, args.backup,
                delete_after=args.delete, config=config
            )
            total_backed_up += backed_up
            total_deleted += deleted_count

        print("\n" + "=" * 60)
        print("COMPLETE!")
        print(f"Backed up {total_backed_up:,} messages")
        if args.delete:
            print(f"Deleted {total_deleted:,} messages")
        print("=" * 60)
        imap.logout()
        return

    # No backup requested
    if not args.delete:
        print(f"\n[DRY RUN] Would delete {total_found:,} messages ({description})")
        print("\nTo actually delete, run with --delete or --unhinged")
        imap.logout()
        return

    # Confirm unless unhinged
    if not args.unhinged:
        print(f"\nAbout to delete {total_found:,} messages ({description}).")
        print("This cannot be undone!")
        confirm = input("Type 'DELETE' to confirm: ").strip()
        if confirm != "DELETE":
            print("Aborted.")
            imap.logout()
            return

    # Delete!
    print("\n" + "=" * 60)
    print(f"DELETING {description}...")
    print("=" * 60)

    grand_total = 0
    for folder, uids in all_results.items():
        print(f"\n--- Processing {folder} ({len(uids):,} messages) ---")
        imap.select(f'"{folder}"')
        folder_deleted = delete_messages_robust(imap, folder, uids, config)
        grand_total += folder_deleted

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print(f"Deleted {grand_total:,} messages")
    print("=" * 60)

    imap.logout()


if __name__ == "__main__":
    main()
