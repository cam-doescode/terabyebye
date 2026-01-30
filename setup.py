#!/usr/bin/env python3
"""
TeraByeBye Setup Wizard
Interactive setup for Yahoo and Gmail email cleanup tools.
Walks you through configuration, dependency installation, and connection testing.
"""

import os
import sys
import subprocess
import getpass
import stat
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
YAHOO_DIR = os.path.join(SCRIPT_DIR, "yahoo")
GMAIL_DIR = os.path.join(SCRIPT_DIR, "gmail")

YAHOO_CONFIG = os.path.join(YAHOO_DIR, ".yahoo_cleanup_config")
GMAIL_OAUTH_CONFIG = os.path.join(GMAIL_DIR, ".gmail_cleanup_config")
GMAIL_SIMPLE_CONFIG = os.path.join(GMAIL_DIR, ".gmail_simple_config")
GMAIL_CREDENTIALS = os.path.join(GMAIL_DIR, "credentials.json")


# ── Helpers ──────────────────────────────────────────────────────────────────

def banner():
    print()
    print("=" * 60)
    print("  TeraByeBye Setup Wizard")
    print("  Bulk email cleanup for Yahoo & Gmail")
    print("=" * 60)
    print()


def ask(prompt, default=None):
    """Ask for input with optional default."""
    if default:
        result = input(f"  {prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"  {prompt}: ").strip()


def ask_choice(prompt, options):
    """Present numbered choices and return the selected value."""
    print(f"\n  {prompt}")
    for i, (label, value) in enumerate(options, 1):
        print(f"    {i}) {label}")
    while True:
        choice = input(f"  Choice [1-{len(options)}]: ").strip()
        try:
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1][1]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}")


def ask_yes_no(prompt, default=True):
    """Ask a yes/no question."""
    suffix = "[Y/n]" if default else "[y/N]"
    result = input(f"  {prompt} {suffix}: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


def secure_write(filepath, content):
    """Write file with owner-only permissions."""
    with open(filepath, 'w') as f:
        f.write(content)
    os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)  # 600
    print(f"  Wrote {filepath} (permissions: 600)")


def config_exists_warning(filepath):
    """Warn if config already exists, ask to overwrite."""
    if os.path.exists(filepath):
        print(f"\n  WARNING: {filepath} already exists!")
        if not ask_yes_no("Overwrite?", default=False):
            print("  Skipping - keeping existing config.")
            return False
    return True


# ── Deletion Method (shared) ────────────────────────────────────────────────

def ask_deletion_method():
    """Ask user how they want to select emails for deletion."""
    method = ask_choice("How do you want to select emails for deletion?", [
        ("Delete by year range (e.g., 2009-2015)", "years"),
        ("Delete before a specific date", "cutoff"),
        ("Delete older than X years", "age"),
    ])

    if method == "years":
        while True:
            years = ask("Year range (e.g., 2009-2015)")
            if re.match(r'^\d{4}-\d{4}$', years):
                start, end = years.split('-')
                if int(start) <= int(end) <= datetime.now().year:
                    return f"DELETE_YEARS={years}"
                print("  Start year must be <= end year, and end year can't be in the future.")
            else:
                print("  Format: YYYY-YYYY (e.g., 2009-2015)")

    elif method == "cutoff":
        while True:
            date_str = ask("Delete before date (DD-Mon-YYYY, e.g., 01-Jan-2024)")
            try:
                datetime.strptime(date_str, "%d-%b-%Y")
                return f"CUTOFF_DATE={date_str}"
            except ValueError:
                print("  Format: DD-Mon-YYYY (e.g., 01-Jan-2024)")

    else:
        while True:
            years = ask("Delete emails older than how many years?", "1")
            try:
                val = int(years)
                if val > 0:
                    return f"YEARS_OLD={val}"
                print("  Must be a positive number.")
            except ValueError:
                print("  Enter a whole number.")


def ask_exclusion_filters():
    """Ask about optional exclusion filters."""
    lines = []
    if ask_yes_no("Add exclusion filters to protect important emails?", default=False):
        subjects = ask("Subject keywords to keep (comma-separated, or blank to skip)", "")
        if subjects:
            lines.append(f"EXCLUDE_SUBJECTS={subjects}")

        senders = ask("Sender addresses to keep (comma-separated, wildcards OK, or blank)", "")
        if senders:
            lines.append(f"EXCLUDE_SENDERS={senders}")

    return lines


# ── Yahoo Setup ─────────────────────────────────────────────────────────────

def setup_yahoo():
    print("\n" + "-" * 60)
    print("  Yahoo Mail Setup (POP3)")
    print("-" * 60)
    print()
    print("  Before we start, you need two things from Yahoo:")
    print()
    print("  1. Enable POP3 in Yahoo Mail:")
    print("     Open Yahoo Mail > gear icon (top right) > More Settings")
    print("     > 'Ways to access Yahoo Mail' > toggle POP to ON")
    print("     (POP3 is required because Yahoo IMAP hides emails past 10,000)")
    print()
    print("  2. Create an App Password (NOT your regular Yahoo password):")
    print("     Go to: https://login.yahoo.com/account/security")
    print("     Scroll to 'Generate and manage app passwords'")
    print("     > Click 'Generate app password'")
    print("     > Type any name (e.g., 'TeraByeBye') > Generate")
    print("     > Copy the password it shows you")
    print()
    print("  See GETTING_STARTED.md for detailed step-by-step instructions.")
    print()

    if not ask_yes_no("Ready to continue?"):
        return False

    if not config_exists_warning(YAHOO_CONFIG):
        return True

    email = ask("Yahoo email address")
    password = getpass.getpass("  App Password (hidden): ").strip()

    deletion = ask_deletion_method()
    batch_size = "50"  # Yahoo max is 50, no need to confuse users

    exclusions = ask_exclusion_filters()

    # Build config
    lines = [
        "# Yahoo Email Cleanup Configuration",
        f"# Generated by setup.py on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"YAHOO_EMAIL={email}",
        f"YAHOO_APP_PASSWORD={password}",
        "",
        f"# Deletion method",
        deletion,
        "",
        f"BATCH_SIZE={batch_size}",
    ]

    if exclusions:
        lines.append("")
        lines.append("# Exclusion filters")
        lines.extend(exclusions)

    lines.append("")
    secure_write(YAHOO_CONFIG, "\n".join(lines))

    # Test connection
    if ask_yes_no("Test Yahoo POP3 connection?"):
        test_yahoo_connection()

    return True


def test_yahoo_connection():
    """Quick POP3 connection test."""
    print("\n  Testing Yahoo POP3 connection...")
    try:
        import poplib
        import ssl

        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        # Read config we just wrote
        config = {}
        with open(YAHOO_CONFIG) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()

        email = config.get("YAHOO_EMAIL", "")
        password = config.get("YAHOO_APP_PASSWORD", "").replace(" ", "")

        pop = poplib.POP3_SSL("pop.mail.yahoo.com", 995, timeout=30, context=ctx)
        pop.user(email)
        pop.pass_(password)
        count, size = pop.stat()
        pop.quit()

        print(f"  SUCCESS! Connected to Yahoo POP3.")
        print(f"  Mailbox: {count:,} messages ({size / (1024*1024):.1f} MB)")

    except Exception as e:
        print(f"  FAILED: {e}")
        print("  Check your email address and App Password.")
        print("  Make sure POP3 is enabled in Yahoo Mail settings.")


# ── Gmail Setup ─────────────────────────────────────────────────────────────

def setup_gmail():
    print("\n" + "-" * 60)
    print("  Gmail Setup")
    print("-" * 60)

    version = ask_choice("Which setup method?", [
        ("App Password / IMAP (recommended - quick and easy)", "simple"),
        ("OAuth2 / Gmail API (advanced - faster for huge mailboxes)", "oauth"),
    ])

    if version == "simple":
        return setup_gmail_simple()
    else:
        return setup_gmail_oauth()


def setup_gmail_simple():
    print()
    print("  Before we start, you need to do three things in Google:")
    print()
    print("  1. Turn on 2-Step Verification (if not already on):")
    print("     Go to: https://myaccount.google.com/security")
    print("     Find '2-Step Verification' and turn it on")
    print("     (usually sends a text to your phone)")
    print()
    print("  2. Create an App Password:")
    print("     Go to: https://myaccount.google.com/apppasswords")
    print("     Type any name (e.g., 'TeraByeBye') > Create")
    print("     Copy the 16-character password it shows you")
    print()
    print("  3. Enable IMAP in Gmail:")
    print("     Open Gmail > gear icon (top right) > 'See all settings'")
    print("     > 'Forwarding and POP/IMAP' tab > Enable IMAP > Save")
    print()
    print("  See GETTING_STARTED.md for detailed step-by-step instructions.")
    print()

    if not ask_yes_no("Ready to continue?"):
        return False

    if not config_exists_warning(GMAIL_SIMPLE_CONFIG):
        return True

    email = ask("Gmail address")
    password = getpass.getpass("  App Password (hidden): ").strip()

    deletion = ask_deletion_method()

    # Labels
    print("\n  Which Gmail folders do you want to clean?")
    print("  Common choices:")
    print("    INBOX                  - Your main inbox")
    print("    CATEGORY_PROMOTIONS    - Marketing/promotional emails")
    print("    CATEGORY_SOCIAL        - Social media notifications")
    print("    ALL                    - Everything")
    print("  You can pick multiple, separated by commas.")
    labels = ask("Folders to clean", "INBOX")

    batch_size = ask("Batch size", "100")
    try:
        bs = int(batch_size)
        if bs <= 0:
            batch_size = "100"
    except ValueError:
        batch_size = "100"

    exclusions = ask_exclusion_filters()

    lines = [
        "# Gmail Simple Cleanup Configuration",
        f"# Generated by setup.py on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"GMAIL_EMAIL={email}",
        f"GMAIL_APP_PASSWORD={password}",
        "",
        deletion,
        "",
        f"LABELS={labels}",
        f"BATCH_SIZE={batch_size}",
    ]

    if exclusions:
        lines.append("")
        lines.append("# Exclusion filters")
        lines.extend(exclusions)

    lines.append("")
    secure_write(GMAIL_SIMPLE_CONFIG, "\n".join(lines))

    # Test connection
    if ask_yes_no("Test Gmail IMAP connection?"):
        test_gmail_imap(email, password)

    return True


def test_gmail_imap(email, password):
    """Quick IMAP connection test."""
    print("\n  Testing Gmail IMAP connection...")
    try:
        import imaplib
        import ssl

        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx)
        imap.login(email, password.replace(" ", ""))
        status, data = imap.select("INBOX", readonly=True)
        count = int(data[0]) if status == "OK" else 0
        imap.logout()

        print(f"  SUCCESS! Connected to Gmail IMAP.")
        print(f"  Inbox: {count:,} messages")

    except Exception as e:
        print(f"  FAILED: {e}")
        print("  Check your email, App Password, and that IMAP is enabled.")


def setup_gmail_oauth():
    print()
    print("  Prerequisites:")
    print("    1. Create a Google Cloud project:")
    print("       https://console.cloud.google.com/")
    print("    2. Enable the Gmail API")
    print("    3. Create OAuth2 Desktop credentials")
    print("    4. Download credentials.json to: gmail/credentials.json")
    print()

    # Check for credentials.json
    if not os.path.exists(GMAIL_CREDENTIALS):
        print(f"  credentials.json not found at: {GMAIL_CREDENTIALS}")
        print("  Download it from Google Cloud Console first.")
        if not ask_yes_no("Continue anyway?", default=False):
            return False

    # Install dependencies
    print("\n  Checking Python dependencies...")
    try:
        import google.auth  # noqa: F401
        print("  Google API libraries already installed.")
    except ImportError:
        if ask_yes_no("Install google-api-python-client and dependencies?"):
            print("  Installing...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "google-api-python-client",
                "google-auth-httplib2",
                "google-auth-oauthlib"
            ])
            print("  Dependencies installed.")
        else:
            print("  Skipping - you'll need to install them manually:")
            print("  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

    if not config_exists_warning(GMAIL_OAUTH_CONFIG):
        return True

    email = ask("Gmail address (for reference)")

    deletion = ask_deletion_method()

    print("\n  Which Gmail labels to clean?")
    print("  Available: INBOX, SENT, SPAM, TRASH, CATEGORY_PROMOTIONS,")
    print("             CATEGORY_SOCIAL, CATEGORY_UPDATES, CATEGORY_FORUMS")
    labels = ask("Labels (comma-separated)", "INBOX,CATEGORY_PROMOTIONS,CATEGORY_SOCIAL")

    batch_size = ask("Batch size (max 1000)", "100")
    try:
        bs = int(batch_size)
        if bs <= 0 or bs > 1000:
            batch_size = "100"
    except ValueError:
        batch_size = "100"

    exclusions = ask_exclusion_filters()

    lines = [
        "# Gmail OAuth Cleanup Configuration",
        f"# Generated by setup.py on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"GMAIL_EMAIL={email}",
        "",
        deletion,
        "",
        f"LABELS={labels}",
        f"BATCH_SIZE={batch_size}",
    ]

    if exclusions:
        lines.append("")
        lines.append("# Exclusion filters")
        lines.extend(exclusions)

    lines.append("")
    secure_write(GMAIL_OAUTH_CONFIG, "\n".join(lines))

    print("\n  On first run, a browser window will open for Google authorization.")
    return True


# ── Status ──────────────────────────────────────────────────────────────────

def show_status():
    """Show what's configured and ready."""
    print("\n  Current Configuration Status:")
    print("  " + "-" * 40)

    configs = [
        ("Yahoo (POP3)", YAHOO_CONFIG, "yahoo/yahoobyebye.py"),
        ("Gmail Simple (IMAP)", GMAIL_SIMPLE_CONFIG, "gmail/gmailbyebye-simple.py"),
        ("Gmail Full (OAuth2)", GMAIL_OAUTH_CONFIG, "gmail/gmailbyebye.py"),
    ]

    for name, config_path, script in configs:
        exists = os.path.exists(config_path)
        icon = "READY" if exists else "not configured"
        print(f"  {name:25s} [{icon}]")
        if exists:
            print(f"    Config: {config_path}")
            print(f"    Script: {script}")

    if os.path.exists(GMAIL_OAUTH_CONFIG) and not os.path.exists(GMAIL_CREDENTIALS):
        print("\n  NOTE: Gmail OAuth config exists but credentials.json is missing!")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    banner()

    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        show_status()
        print()
        return

    print("  What would you like to set up?\n")

    while True:
        choice = ask_choice("Select a provider:", [
            ("Yahoo Mail (POP3)", "yahoo"),
            ("Gmail", "gmail"),
            ("Show current status", "status"),
            ("Exit", "exit"),
        ])

        if choice == "yahoo":
            setup_yahoo()
        elif choice == "gmail":
            setup_gmail()
        elif choice == "status":
            show_status()
        elif choice == "exit":
            break

        print()
        if not ask_yes_no("Set up another provider?", default=False):
            break

    print("\n  Setup complete! Here's what to do next:")
    print()
    print("    python3 terabyebye.py          # Preview what would be deleted (safe, no changes)")
    print("    python3 terabyebye.py --safe   # Backup + delete with extra safety checks")
    print("    python3 terabyebye.py --delete # Delete (asks for confirmation)")
    print()
    print("  We recommend starting with a preview to see what will be affected.")
    print()


if __name__ == "__main__":
    main()
