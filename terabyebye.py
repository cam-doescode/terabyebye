#!/usr/bin/env python3
"""
TeraByeBye - Unified CLI
Auto-detects configured providers (Yahoo/Gmail) and routes to the right script.
Pass any arguments through (--preview, --delete, --backup, --unhinged, etc.)
"""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Provider configs and their corresponding scripts
PROVIDERS = [
    {
        "name": "Yahoo (POP3)",
        "config": os.path.join(SCRIPT_DIR, "yahoo", ".yahoo_cleanup_config"),
        "script": os.path.join(SCRIPT_DIR, "yahoo", "yahoobyebye.py"),
    },
    {
        "name": "Gmail Simple (App Password / IMAP)",
        "config": os.path.join(SCRIPT_DIR, "gmail", ".gmail_simple_config"),
        "script": os.path.join(SCRIPT_DIR, "gmail", "gmailbyebye-simple.py"),
    },
    {
        "name": "Gmail Full (OAuth2 / Gmail API)",
        "config": os.path.join(SCRIPT_DIR, "gmail", ".gmail_cleanup_config"),
        "script": os.path.join(SCRIPT_DIR, "gmail", "gmailbyebye.py"),
    },
]

BANNER = """
╔══════════════════════════════════════════════╗
║             T e r a B y e B y e              ║
║     Bulk email cleanup for Yahoo & Gmail     ║
╚══════════════════════════════════════════════╝
"""


def find_configured_providers():
    """Return list of providers that have config files present."""
    return [p for p in PROVIDERS if os.path.exists(p["config"])]


def pick_provider(configured):
    """Let user choose which configured provider to run."""
    print("  Multiple providers configured:\n")
    for i, p in enumerate(configured, 1):
        print(f"    {i}) {p['name']}")

    while True:
        choice = input(f"\n  Which provider? [1-{len(configured)}]: ").strip()
        try:
            idx = int(choice)
            if 1 <= idx <= len(configured):
                return configured[idx - 1]
        except ValueError:
            pass
        print(f"  Enter a number between 1 and {len(configured)}")


def run_provider(provider, args):
    """Execute the provider script with given arguments."""
    script = provider["script"]

    if not os.path.exists(script):
        print(f"  Error: Script not found: {script}")
        sys.exit(1)

    print(f"  Running: {provider['name']}")
    print(f"  Script:  {os.path.relpath(script, SCRIPT_DIR)}")
    print()

    cmd = [sys.executable, script] + args
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def show_help():
    print(BANNER)
    print("  Usage: python3 terabyebye.py [options]")
    print()
    print("  Options (passed to the underlying cleanup script):")
    print("    --preview       Preview what would be deleted (default)")
    print("    --safe          Backup + delete with extra safety checks (recommended)")
    print("    --delete        Delete emails (with confirmation)")
    print("    --backup DIR    Backup emails to DIR before deletion")
    print("    --unhinged      Delete without any prompts")
    print()
    print("  Wrapper options:")
    print("    --setup         Run the interactive setup wizard")
    print("    --status        Show which providers are configured")
    print("    --yahoo         Force Yahoo provider")
    print("    --gmail         Force Gmail (simple) provider")
    print("    --gmail-oauth   Force Gmail (OAuth2) provider")
    print("    --help, -h      Show this help")
    print()


def show_status():
    print(BANNER)
    print("  Provider Status:")
    print("  " + "-" * 44)
    for p in PROVIDERS:
        exists = os.path.exists(p["config"])
        status = "READY" if exists else "not configured"
        print(f"    {p['name']:40s} [{status}]")
    print()
    configured = find_configured_providers()
    if not configured:
        print("  No providers configured. Run: python3 setup.py")
    else:
        print(f"  {len(configured)} provider(s) ready.")
    print()


def main():
    args = sys.argv[1:]

    # Handle wrapper-level flags
    if "--help" in args or "-h" in args:
        show_help()
        return

    if "--status" in args:
        show_status()
        return

    if "--setup" in args:
        setup_script = os.path.join(SCRIPT_DIR, "setup.py")
        subprocess.run([sys.executable, setup_script])
        return

    # Force a specific provider
    forced = None
    passthrough = list(args)

    if "--yahoo" in passthrough:
        passthrough.remove("--yahoo")
        forced = PROVIDERS[0]
    elif "--gmail" in passthrough:
        passthrough.remove("--gmail")
        forced = PROVIDERS[1]
    elif "--gmail-oauth" in passthrough:
        passthrough.remove("--gmail-oauth")
        forced = PROVIDERS[2]

    if forced:
        if not os.path.exists(forced["config"]):
            print(f"\n  {forced['name']} is not configured.")
            print(f"  Expected config: {forced['config']}")
            print(f"  Run: python3 setup.py")
            sys.exit(1)
        run_provider(forced, passthrough)
        return

    # Auto-detect configured providers
    configured = find_configured_providers()

    if not configured:
        print(BANNER)
        print("  No providers configured yet!")
        print()
        print("  Quick start:")
        print("    python3 setup.py        # Interactive setup wizard")
        print()
        print("  Or manually create config files:")
        print("    cp yahoo/.yahoo_cleanup_config.template yahoo/.yahoo_cleanup_config")
        print("    cp gmail/.gmail_simple_config.template gmail/.gmail_simple_config")
        print()
        sys.exit(1)

    if len(configured) == 1:
        # Only one provider configured - use it directly
        provider = configured[0]
    else:
        # Multiple providers - let user choose
        print(BANNER)
        provider = pick_provider(configured)
        print()

    run_provider(provider, passthrough)


if __name__ == "__main__":
    main()
