#!/usr/bin/env python3
"""
Yahoo Email Cleanup via POP3 - FAST VERSION
Uses binary search to find the cutoff point, then bulk deletes.
"""
import poplib
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
import time
import sys
import os
import zipfile
from collections import defaultdict

# Config
POP3_SERVER = "pop.mail.yahoo.com"
POP3_PORT = 995 
CONFIG_FILE_LOCAL = ".yahoo_cleanup_config"
CONFIG_FILE_HOME = os.path.expanduser("~/.yahoo_cleanup_config")

# Defaults
DEFAULT_CONFIG = {
    "YEARS_OLD": 1,
    "CUTOFF_DATE": None,
    "DELETE_YEARS": None,  # Format: "2009-2015" (deletes emails from those years)
    "BATCH_SIZE": 50,  # Keep small - Yahoo kills connections on larger batches
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

                    if key == "YAHOO_EMAIL":
                        config["email"] = value
                    elif key == "YAHOO_APP_PASSWORD":
                        config["password"] = value.replace(" ", "")
                    elif key == "CUTOFF_DATE":
                        config["CUTOFF_DATE"] = value
                    elif key == "YEARS_OLD":
                        config["YEARS_OLD"] = int(value)
                    elif key == "BATCH_SIZE":
                        config["BATCH_SIZE"] = int(value)
                    elif key == "DELETE_YEARS":
                        config["DELETE_YEARS"] = value

        print(f"Loaded config from {config_file}")

    return config


def get_cutoff_date(config):
    """Calculate cutoff date from config."""
    if config.get("CUTOFF_DATE"):
        # Parse DD-Mon-YYYY format
        return datetime.strptime(config["CUTOFF_DATE"], "%d-%b-%Y")
    # Calculate from YEARS_OLD
    years = config.get("YEARS_OLD", 1)
    return datetime.now() - timedelta(days=years * 365)


def connect_pop3(config, timeout=60):
    """Connect to Yahoo POP3 with timeout."""
    pop = poplib.POP3_SSL(POP3_SERVER, POP3_PORT, timeout=timeout)
    pop.user(config["email"])
    pop.pass_(config["password"])
    return pop


def get_message_date(pop, msg_num):
    """Get the date of a message using TOP command."""
    try:
        response, lines, octets = pop.top(msg_num, 0)
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='replace')
            if line.lower().startswith('date:'):
                date_str = line[5:].strip()
                try:
                    dt = parsedate_to_datetime(date_str)
                    if dt.tzinfo:
                        dt = dt.replace(tzinfo=None)
                    return dt
                except:
                    pass
    except:
        pass
    return None


def binary_search_date(pop, num_messages, target_date, find_first_gte=True, label="cutoff"):
    """
    Binary search to find message boundary by date.

    Args:
        pop: POP3 connection
        num_messages: Total messages in mailbox
        target_date: Date to search for
        find_first_gte: If True, find first message >= target_date
                        If False, find last message < target_date
        label: Label for log output

    Returns:
        Message number of the boundary
    """
    print(f"Binary searching for {label} in {num_messages:,} messages...")

    left = 1
    right = num_messages
    result = num_messages + 1 if find_first_gte else 0

    iterations = 0
    while left <= right:
        iterations += 1
        mid = (left + right) // 2

        msg_date = get_message_date(pop, mid)

        if msg_date is None:
            print(f"  #{mid}: no date, trying neighbors...")
            found = False
            for offset in [1, -1, 2, -2, 5, -5]:
                test_msg = mid + offset
                if 1 <= test_msg <= num_messages:
                    msg_date = get_message_date(pop, test_msg)
                    if msg_date:
                        mid = test_msg
                        found = True
                        break
            if not found:
                left = mid + 10
                continue

        date_str = msg_date.strftime('%Y-%m-%d') if msg_date else "unknown"

        if find_first_gte:
            # Finding first message >= target_date
            if msg_date and msg_date >= target_date:
                print(f"  #{mid:,}: {date_str} >= {label}, searching earlier...")
                result = mid
                right = mid - 1
            else:
                print(f"  #{mid:,}: {date_str} < {label}, searching later...")
                left = mid + 1
        else:
            # Finding last message < target_date
            if msg_date and msg_date < target_date:
                print(f"  #{mid:,}: {date_str} < {label}, searching later...")
                result = mid
                left = mid + 1
            else:
                print(f"  #{mid:,}: {date_str} >= {label}, searching earlier...")
                right = mid - 1

    print(f"Binary search complete in {iterations} iterations")
    return result


def parse_delete_years(delete_years_str):
    """Parse DELETE_YEARS config value into start and end dates."""
    if "-" in delete_years_str:
        # Range format: "2009-2015"
        parts = delete_years_str.split("-")
        start_year = int(parts[0].strip())
        end_year = int(parts[1].strip())
    else:
        # Single year: "2015"
        start_year = end_year = int(delete_years_str.strip())

    # Start of start_year and end of end_year
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year + 1, 1, 1)  # First day of next year

    return start_year, end_year, start_date, end_date


def get_deletion_range(pop, num_messages, config, oldest_date=None, newest_date=None):
    """
    Determine what messages to delete based on config.

    Args:
        pop: POP3 connection
        num_messages: Total messages in mailbox
        config: Configuration dict
        oldest_date: Date of oldest message (optimization - skip search if known)
        newest_date: Date of newest message (optimization - skip search if known)

    Returns:
        (start_pos, end_pos, count, description)
        - start_pos: First message to delete
        - end_pos: Last message to delete
        - count: Number of messages to delete
        - description: Human-readable description
    """
    delete_years = config.get("DELETE_YEARS")

    if delete_years:
        # Year range mode
        start_year, end_year, start_date, end_date = parse_delete_years(delete_years)

        print(f"\nMode: Delete emails from years {start_year}-{end_year}")

        # Optimize: skip binary search if we already know the boundaries
        # If requested start_year is at or before oldest email, start from message 1
        if oldest_date and start_year <= oldest_date.year:
            print(f"  Oldest email is {oldest_date.year}, starting from message 1")
            start_pos = 1
        else:
            start_pos = binary_search_date(pop, num_messages, start_date,
                                            find_first_gte=True, label=f"start of {start_year}")

        # If requested end_year is at or after newest email, end at last message
        if newest_date and end_year >= newest_date.year:
            print(f"  Newest email is {newest_date.year}, ending at message {num_messages:,}")
            end_pos = num_messages
        else:
            # Find first message AFTER end_year (first message of end_year+1)
            end_pos = binary_search_date(pop, num_messages, end_date,
                                          find_first_gte=True, label=f"end of {end_year}")
            end_pos -= 1  # Last message of the target range

        if start_pos > end_pos or start_pos > num_messages:
            return None, None, 0, f"years {start_year}-{end_year}"

        count = end_pos - start_pos + 1
        description = f"years {start_year}-{end_year}"

        return start_pos, end_pos, count, description

    else:
        # Cutoff date mode (existing behavior)
        if config.get("CUTOFF_DATE"):
            cutoff_date = datetime.strptime(config["CUTOFF_DATE"], "%d-%b-%Y")
        else:
            years = config.get("YEARS_OLD", 1)
            cutoff_date = datetime.now() - timedelta(days=years * 365)

        print(f"\nMode: Delete emails BEFORE {cutoff_date.strftime('%Y-%m-%d')}")

        # Optimize: if cutoff is before oldest email, nothing to delete
        if oldest_date and cutoff_date <= oldest_date:
            print(f"  Cutoff {cutoff_date.strftime('%Y-%m-%d')} is before oldest email {oldest_date.strftime('%Y-%m-%d')}")
            return None, None, 0, f"before {cutoff_date.strftime('%Y-%m-%d')}"

        # Optimize: if cutoff is after newest email, delete everything
        if newest_date and cutoff_date > newest_date:
            print(f"  Cutoff is after newest email, deleting all {num_messages:,} messages")
            return 1, num_messages, num_messages, f"before {cutoff_date.strftime('%Y-%m-%d')}"

        # Find first message >= cutoff_date
        cutoff_msg = binary_search_date(pop, num_messages, cutoff_date,
                                         find_first_gte=True, label="cutoff")

        if cutoff_msg <= 1:
            return None, None, 0, f"before {cutoff_date.strftime('%Y-%m-%d')}"

        start_pos = 1
        end_pos = cutoff_msg - 1
        count = end_pos
        description = f"before {cutoff_date.strftime('%Y-%m-%d')}"

        return start_pos, end_pos, count, description


def backup_emails_to_zip(config, start_pos, end_pos, output_dir, delete_after=False):
    """
    Backup emails to monthly ZIP files containing EML files.
    Writes incrementally to avoid memory issues with large mailboxes.
    Optionally deletes each batch after successful backup.

    Args:
        config: Configuration dict
        start_pos: First message to backup
        end_pos: Last message to backup
        output_dir: Directory to write ZIP files to
        delete_after: If True, delete each batch after backing up

    Returns:
        (backed_up, deleted) tuple
    """
    os.makedirs(output_dir, exist_ok=True)

    total_to_process = end_pos - start_pos + 1
    print(f"\nBacking up {total_to_process:,} emails to {output_dir}/")
    if delete_after:
        print("(Will delete each batch after backup)")

    # Track which ZIPs we've created and email counts
    zip_email_counts = defaultdict(int)  # {zip_filename: count}

    backed_up = 0
    deleted = 0
    consecutive_failures = 0
    max_failures = 5
    batch_size = 50  # Download in batches to handle reconnection

    # When deleting, we always read from start_pos since messages shift down
    # When not deleting, we advance current_msg
    remaining = total_to_process

    while remaining > 0:
        # Connect for this batch
        try:
            pop = connect_pop3(config)
        except Exception as e:
            print(f"Connection failed: {e}")
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                print(f"Too many failures, stopping.")
                break
            time.sleep(30 * consecutive_failures)
            continue

        # Check current mailbox state
        try:
            num_messages, _ = pop.stat()
        except Exception as e:
            print(f"STAT failed: {e}")
            try:
                pop.quit()
            except:
                pass
            consecutive_failures += 1
            continue

        # Determine batch range
        # When deleting, always start from start_pos (messages shift down)
        # When not deleting, calculate position based on progress
        if delete_after:
            current_start = start_pos
        else:
            current_start = start_pos + backed_up

        if current_start > num_messages:
            print("No more messages to process.")
            try:
                pop.quit()
            except:
                pass
            break

        batch_count = min(batch_size, remaining, num_messages - current_start + 1)
        batch_end = current_start + batch_count - 1

        print(f"Downloading messages {current_start:,}-{batch_end:,} ({backed_up:,}/{total_to_process:,} done)...")

        # Collect batch in memory, then write (keeps ZIP operations efficient)
        batch_emails = []  # [(zip_filename, eml_filename, content), ...]
        batch_msg_nums = []  # Track which messages to delete

        for msg_num in range(current_start, batch_end + 1):
            try:
                # Get full message
                _, lines, _ = pop.retr(msg_num)
                content = b'\r\n'.join(lines)

                # Get date for organizing
                msg_date = get_message_date(pop, msg_num)
                if msg_date:
                    year, month = msg_date.year, msg_date.month
                    date_str = msg_date.strftime('%Y%m%d')
                else:
                    year, month = 1970, 1  # Unknown dates
                    date_str = "unknown"

                # Use backed_up counter for unique filenames (not msg_num which resets)
                file_index = backed_up + len(batch_emails) + 1
                zip_filename = os.path.join(output_dir, f"emails_{year:04d}-{month:02d}.zip")
                eml_filename = f"msg_{file_index:06d}_{date_str}.eml"
                batch_emails.append((zip_filename, eml_filename, content))
                batch_msg_nums.append(msg_num)

            except Exception as e:
                print(f"  Error on #{msg_num}: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    break

        if consecutive_failures >= max_failures:
            try:
                pop.quit()
            except:
                pass
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
        remaining -= len(batch_emails)

        # Delete batch if requested
        if delete_after and batch_msg_nums:
            print(f"  Marking {len(batch_msg_nums)} messages for deletion...")
            for msg_num in batch_msg_nums:
                try:
                    pop.dele(msg_num)
                except Exception as e:
                    print(f"  Delete error on #{msg_num}: {e}")

            # Commit deletions
            try:
                pop.quit()
                deleted += len(batch_msg_nums)
                consecutive_failures = 0
                print(f"  Deleted {len(batch_msg_nums)} messages.")
            except Exception as e:
                print(f"  Commit FAILED: {e} - will retry batch")
                consecutive_failures += 1
                # Roll back our counters since delete failed
                backed_up -= len(batch_emails)
                remaining += len(batch_emails)
                time.sleep(30 * consecutive_failures)
                continue
        else:
            try:
                pop.quit()
            except:
                pass
            consecutive_failures = 0

        print(f"  Progress: {backed_up:,}/{total_to_process:,} ({100*backed_up/total_to_process:.1f}%)")

        # Brief pause between batches
        if remaining > 0:
            time.sleep(2)

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


def delete_messages_robust(config, messages_to_delete, start_position=1):
    """
    Delete messages with robust reconnection handling.

    Args:
        config: Configuration dict
        messages_to_delete: Total number of messages to delete
        start_position: Message number to start deleting from (default 1)
                        For year ranges, this may be > 1
    """
    batch_size = min(config.get("BATCH_SIZE", 50), 50)  # Cap at 50 - Yahoo kills connections on larger batches
    consecutive_failures = 0
    max_failures = 5

    # Track progress by checking actual mailbox count
    initial_count = None

    while True:
        # Connect fresh for each batch
        print(f"\nConnecting for batch...")
        try:
            pop = connect_pop3(config)
        except Exception as e:
            print(f"Connection failed: {e}")
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                print(f"Too many consecutive failures ({max_failures}), stopping.")
                break
            wait_time = min(30 * consecutive_failures, 120)
            print(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
            continue

        # Check current message count
        try:
            num_messages, _ = pop.stat()
        except Exception as e:
            print(f"STAT failed: {e}")
            try:
                pop.quit()
            except:
                pass
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                print(f"Too many consecutive failures ({max_failures}), stopping.")
                break
            wait_time = min(30 * consecutive_failures, 120)
            print(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
            continue

        # Track initial count for progress
        if initial_count is None:
            initial_count = num_messages

        # Calculate actual deletions based on mailbox shrinking
        actual_deleted = initial_count - num_messages
        print(f"Mailbox has {num_messages:,} messages (deleted {actual_deleted:,} so far)")

        if num_messages == 0:
            print("Mailbox empty!")
            pop.quit()
            break

        # Check if we've deleted enough
        if actual_deleted >= messages_to_delete:
            print("Target reached!")
            pop.quit()
            break

        # For year range deletion, check if start_position is still valid
        # (After deletions, the range shifts down)
        current_start = start_position
        if start_position > 1:
            # Adjust start position based on how much the mailbox has shrunk
            # Since we always delete from start_position, after deletions
            # the start_position stays the same (earlier messages are preserved)
            current_start = start_position

        if current_start > num_messages:
            print("Start position beyond mailbox, done!")
            pop.quit()
            break

        # Calculate how many to delete this batch
        remaining = messages_to_delete - actual_deleted
        batch_count = min(batch_size, remaining, num_messages - current_start + 1)

        if batch_count <= 0:
            pop.quit()
            break

        end_msg = current_start + batch_count - 1
        print(f"Marking messages {current_start}-{end_msg} for deletion...")

        marked_count = 0
        errors_this_batch = 0

        for i in range(current_start, current_start + batch_count):
            try:
                pop.dele(i)
                marked_count += 1

                if marked_count % 50 == 0:
                    print(f"  Marked {marked_count:,}/{batch_count:,}...")

            except Exception as e:
                errors_this_batch += 1
                if errors_this_batch <= 3:
                    print(f"  Error on #{i}: {e}")
                if errors_this_batch > 10:
                    print(f"  Too many errors, trying to commit what we have...")
                    break

        # Commit by quitting - this is where Yahoo may reject
        print(f"Committing {marked_count:,} deletions...")
        try:
            pop.quit()
            consecutive_failures = 0  # Reset on success
            print("Commit successful.")
        except Exception as e:
            print(f"Commit FAILED: {e}")
            print("Deletions were NOT applied. Will retry...")
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                print(f"Too many consecutive failures ({max_failures}), stopping.")
                break
            # Longer pause after commit failure
            wait_time = min(60 * consecutive_failures, 300)
            print(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
            continue

        # Brief pause between successful batches
        print("Pausing 3 seconds...")
        time.sleep(3)

    # Final count
    try:
        pop = connect_pop3(config)
        final_count, _ = pop.stat()
        pop.quit()
        total_deleted = initial_count - final_count if initial_count else 0
        return total_deleted
    except:
        return initial_count - num_messages if initial_count else 0


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="TeraByeBye - Bulk delete Yahoo emails via POP3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python terabyebye.py                         # Preview what would be deleted
  python terabyebye.py --preview               # Same as above (explicit)
  python terabyebye.py --delete                # Actually delete emails
  python terabyebye.py --backup ./backup       # Backup only (no delete)
  python terabyebye.py --backup ./backup --delete  # Backup + delete each batch
  python terabyebye.py --unhinged              # No prompts, no mercy
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
    print("TeraByeBye - Yahoo POP3 Email Cleanup")
    print("=" * 60)

    config = load_config()
    if not config["email"] or not config["password"]:
        print("Error: Could not load credentials from config file")
        sys.exit(1)

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

    print(f"\nConnecting to {POP3_SERVER}...")
    pop = connect_pop3(config)

    num_messages, total_size = pop.stat()
    print(f"Mailbox: {num_messages:,} messages ({total_size/1024/1024/1024:.1f} GB)")

    if num_messages == 0:
        print("No messages to process!")
        pop.quit()
        return

    # Show first and last message dates
    print("\nChecking message date range...")
    first_date = get_message_date(pop, 1)
    last_date = get_message_date(pop, num_messages)
    print(f"  Oldest (#{1}): {first_date.strftime('%Y-%m-%d') if first_date else 'unknown'}")
    print(f"  Newest (#{num_messages:,}): {last_date.strftime('%Y-%m-%d') if last_date else 'unknown'}")

    # Determine what to delete based on config (pass dates to optimize searches)
    start_pos, end_pos, messages_to_delete, description = get_deletion_range(
        pop, num_messages, config, oldest_date=first_date, newest_date=last_date
    )

    pop.quit()  # Close connection before deletion phase

    print()
    print("=" * 60)
    print(f"RESULT: Deleting {description}")
    if messages_to_delete > 0:
        print(f"  Messages to DELETE: {start_pos:,} to {end_pos:,} ({messages_to_delete:,} total)")
        if start_pos > 1:
            print(f"  Messages to KEEP (before): 1 to {start_pos - 1:,}")
        if end_pos < num_messages:
            print(f"  Messages to KEEP (after):  {end_pos + 1:,} to {num_messages:,}")
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

        # Estimate size (rough: ~50KB average per email)
        est_size_gb = (messages_to_delete * 50 * 1024) / (1024**3)
        print(f"  Estimated size: ~{est_size_gb:.1f} GB (varies by email size)")

        # Warning for large backups
        if messages_to_delete > 10000:
            print(f"\n  WARNING: Backing up {messages_to_delete:,} emails will take a while!")
            print("  Consider starting with a smaller date range to test.")

        if not args.unhinged:
            if args.delete:
                confirm = input("\nProceed with backup AND deletion? (y/N): ").strip().lower()
            else:
                confirm = input("\nProceed with backup? (y/N): ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                return

        # Backup (and optionally delete in same pass)
        backed_up, deleted = backup_emails_to_zip(
            config, start_pos, end_pos, args.backup,
            delete_after=args.delete
        )

        if backed_up < messages_to_delete:
            print(f"\nWARNING: Only backed up {backed_up:,} of {messages_to_delete:,} emails!")
            if args.delete and not args.unhinged:
                print("Some emails may not have been deleted.")

        print("\n" + "=" * 60)
        print("COMPLETE!")
        print(f"Backed up {backed_up:,} messages")
        if args.delete:
            print(f"Deleted {deleted:,} messages")
        print("=" * 60)
        return  # Done - backup handled everything

    # No backup requested - handle dry run / execute normally
    if not args.delete:
        print(f"\n[DRY RUN] Would delete {messages_to_delete:,} messages ({description})")
        print("\nTo actually delete, run with --execute or --unhinged")
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

    total_deleted = delete_messages_robust(config, messages_to_delete, start_pos)

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print(f"Deleted {total_deleted:,} messages")
    print("=" * 60)


if __name__ == "__main__":
    main()
