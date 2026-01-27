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

# Config
POP3_SERVER = "pop.mail.yahoo.com"
POP3_PORT = 995 
CONFIG_FILE_LOCAL = ".yahoo_cleanup_config"
CONFIG_FILE_HOME = os.path.expanduser("~/.yahoo_cleanup_config")

# Defaults
DEFAULT_CONFIG = {
    "YEARS_OLD": 1,
    "CUTOFF_DATE": None,
    "BATCH_SIZE": 100,  # Keep small - Yahoo rejects large batches
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


def binary_search_cutoff(pop, num_messages, cutoff_date):
    """Binary search to find the first message >= cutoff_date."""
    print(f"Binary searching for cutoff point in {num_messages:,} messages...")

    left = 1
    right = num_messages
    result = num_messages + 1

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

        if msg_date and msg_date >= cutoff_date:
            print(f"  #{mid:,}: {date_str} >= cutoff, searching earlier...")
            result = mid
            right = mid - 1
        else:
            print(f"  #{mid:,}: {date_str} < cutoff, searching later...")
            left = mid + 1

    print(f"Binary search complete in {iterations} iterations")
    return result


def delete_messages_robust(config, messages_to_delete):
    """Delete messages with robust reconnection handling."""
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

        # Calculate how many to delete this batch
        remaining = messages_to_delete - actual_deleted
        batch_count = min(batch_size, remaining, num_messages)

        if batch_count <= 0:
            pop.quit()
            break

        print(f"Marking messages 1-{batch_count} for deletion...")

        marked_count = 0
        errors_this_batch = 0

        for i in range(1, batch_count + 1):
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
        description="Fast Yahoo email cleanup via POP3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pop3_cleanup_fast.py                  # Dry run (preview)
  python pop3_cleanup_fast.py --execute        # Actually delete
  python pop3_cleanup_fast.py --unhinged       # No prompts, just delete
        """
    )
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete emails (default is dry-run)")
    parser.add_argument("--unhinged", action="store_true",
                        help="No prompts, no mercy. Just delete.")
    args = parser.parse_args()

    print("=" * 60)
    print("Yahoo POP3 Email Cleanup - FAST MODE")
    print("=" * 60)

    config = load_config()
    if not config["email"] or not config["password"]:
        print("Error: Could not load credentials from config file")
        sys.exit(1)

    cutoff_date = get_cutoff_date(config)
    print(f"\nCutoff date: {cutoff_date.strftime('%Y-%m-%d')}")
    print(f"(Deleting emails BEFORE this date)")

    # Unhinged mode implies execute
    if args.unhinged:
        args.execute = True
        print("\n" + "!" * 60)
        print("🔥 UNHINGED MODE ACTIVATED 🔥")
        print("No prompts. No mercy. Deleting all old emails.")
        print("!" * 60)
    elif not args.execute:
        print("\n" + "!" * 60)
        print("DRY RUN MODE - No emails will be deleted")
        print("Run with --execute to actually delete emails")
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

    # Binary search to find cutoff point
    cutoff_msg = binary_search_cutoff(pop, num_messages, cutoff_date)
    messages_to_delete = cutoff_msg - 1

    pop.quit()  # Close connection before deletion phase

    print()
    print("=" * 60)
    print(f"RESULT:")
    print(f"  Messages to DELETE: 1 to {messages_to_delete:,} ({messages_to_delete:,} total)")
    print(f"  Messages to KEEP:   {cutoff_msg:,} to {num_messages:,}")
    print("=" * 60)

    if messages_to_delete == 0:
        print("\nNothing to delete! All emails are newer than cutoff.")
        return

    if not args.execute:
        print(f"\n[DRY RUN] Would delete {messages_to_delete:,} messages")
        print("\nTo actually delete, run with --execute or --unhinged")
        return

    # Confirm unless unhinged
    if not args.unhinged:
        print(f"\nAbout to delete {messages_to_delete:,} messages.")
        print("This cannot be undone!")
        confirm = input("Type 'DELETE' to confirm: ").strip()
        if confirm != "DELETE":
            print("Aborted.")
            return

    # Delete!
    print("\n" + "=" * 60)
    print("DELETING...")
    print("=" * 60)

    total_deleted = delete_messages_robust(config, messages_to_delete)

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print(f"Deleted {total_deleted:,} messages")
    print("=" * 60)


if __name__ == "__main__":
    main()
