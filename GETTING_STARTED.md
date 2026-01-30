# Getting Started with TeraByeBye

**No programming experience needed.** This guide walks you through everything step by step.

---

## Step 1: Install Python

TeraByeBye is a Python script. Most computers have Python already — let's check.

### Check if Python is installed

Open your terminal:
- **Mac**: Open **Terminal** (search for it in Spotlight, or find it in Applications > Utilities)
- **Windows**: Open **Command Prompt** (search "cmd" in the Start menu)

Type this and press Enter:
```
python3 --version
```

If you see something like `Python 3.10.4`, you're good — skip to Step 2.

If you get an error ("command not found"):
- **Mac**: Install from https://www.python.org/downloads/ (click the big yellow button)
- **Windows**: Install from https://www.python.org/downloads/ — **check the box that says "Add Python to PATH"** during install

After installing, close and reopen your terminal, then try `python3 --version` again.

---

## Step 2: Download TeraByeBye

### Option A: Download as ZIP (easiest)

1. Go to the project page on GitHub
2. Click the green **"Code"** button
3. Click **"Download ZIP"**
4. Unzip the downloaded file to wherever you want (e.g., your Desktop)

### Option B: Clone with Git (if you have Git)

```
git clone <repository-url>
```

---

## Step 3: Open a Terminal in the TeraByeBye Folder

You need to navigate your terminal to wherever you unzipped/cloned the files.

**Mac**:
1. Open Terminal
2. Type `cd ` (with a space after it)
3. Drag the TeraByeBye folder from Finder into the Terminal window — it will paste the path
4. Press Enter

**Windows**:
1. Open the TeraByeBye folder in File Explorer
2. Click in the address bar at the top
3. Type `cmd` and press Enter — a Command Prompt will open in that folder

You should see the TeraByeBye files if you type `ls` (Mac) or `dir` (Windows).

---

## Step 4: Run the Setup Wizard

This is the easy part. Just type:

```
python3 setup.py
```

The wizard will ask you questions and guide you through everything:

1. **Which email provider?** — Pick Yahoo or Gmail
2. **Your credentials** — It will tell you exactly where to get them (see below)
3. **What to delete** — Pick a date range or age threshold
4. **Test the connection** — Verifies everything works before you delete anything

That's it! The wizard creates the config file for you.

---

## Step 5: Getting Your App Password

Both Yahoo and Gmail require an "App Password" — this is a special password that only works for this tool, separate from your regular login password. It's safer than using your real password.

### For Yahoo Mail

1. Go to https://login.yahoo.com/account/security
2. Sign in with your regular Yahoo password
3. Scroll down to **"Generate and manage app passwords"** (or "App passwords")
4. If you don't see this option, you need to turn on **Two-Step Verification** first:
   - It's on the same security page
   - Click it, follow the prompts to set it up (usually sends a text to your phone)
   - Then come back and look for App passwords
5. Click **"Generate app password"**
6. For "App name" type anything — like "TeraByeBye" or "Email Cleanup"
7. Click **"Generate"**
8. You'll see a password like `abcd efgh ijkl mnop` — **copy this immediately**
   - You won't be able to see it again after closing the window
   - The spaces don't matter, the tool handles them

**Also enable POP3:**
1. In Yahoo Mail, click the **gear icon** (top right)
2. Click **"More Settings"**
3. Click **"Ways to access Yahoo Mail"** in the left sidebar
4. Find **POP** and make sure it says **"Enable"** or is toggled on

### For Gmail

1. Go to https://myaccount.google.com/security
2. Make sure **2-Step Verification** is turned ON
   - If it's off, click it and follow the setup (usually sends a text to your phone)
3. Once 2-Step Verification is on, go to https://myaccount.google.com/apppasswords
4. You may need to sign in again
5. Under "App name", type anything — like "TeraByeBye"
6. Click **"Create"**
7. You'll see a 16-character password — **copy this immediately**

**Also enable IMAP (for the simple version):**
1. In Gmail, click the **gear icon** (top right)
2. Click **"See all settings"**
3. Click the **"Forwarding and POP/IMAP"** tab
4. Under "IMAP access", select **"Enable IMAP"**
5. Click **"Save Changes"** at the bottom

---

## Step 6: Preview Before Deleting

**Always preview first.** This shows you what *would* be deleted without actually deleting anything:

```
python3 terabyebye.py
```

This will connect to your email, count the messages that match your criteria, and show you a summary. Nothing is deleted in preview mode.

Read the output carefully. Does the count look right? Is the date range correct?

---

## Step 7: Delete (When Ready)

Once you've previewed and everything looks correct:

### Safest option: Backup first, then delete

```
python3 terabyebye.py --safe
```

This will:
1. Show you exactly what will be deleted
2. Back up all emails to ZIP files on your computer (so you can recover them if needed)
3. Ask for confirmation before deleting anything
4. Delete in small batches, confirming along the way

The backup creates `.zip` files organized by month (e.g., `emails_2015-03.zip`). Each contains `.eml` files that any email program can open.

### Standard delete (with confirmation)

```
python3 terabyebye.py --delete
```

This skips the backup but still asks for confirmation.

### Backup only (no deletion)

```
python3 terabyebye.py --backup ./my_backup
```

Just downloads your old emails to your computer. Nothing is deleted.

---

## Troubleshooting

### "python3: command not found"
Python isn't installed or isn't in your PATH. See Step 1.

### "Could not load credentials"
The config file wasn't created or is in the wrong place. Run `python3 setup.py` again.

### "Login failed" or "Authentication failed"
- Double-check your App Password (not your regular password)
- Make sure you copied the full password including all characters
- For Yahoo: Make sure POP3 is enabled in Yahoo Mail settings
- For Gmail: Make sure IMAP is enabled and 2-Step Verification is on

### "Connection refused" or "Timeout"
- Check your internet connection
- Your firewall or antivirus might be blocking the connection
- Try again in a few minutes — email servers sometimes have temporary issues

### "SYS/TEMP error" (Yahoo)
This is normal — Yahoo's servers get overwhelmed. The tool automatically retries. Just let it run.

### The tool seems stuck or slow
- Yahoo limits connections to 50 emails at a time, with a pause between batches
- Large mailboxes (100,000+ emails) will take a while — this is normal
- You can stop the tool anytime (Ctrl+C) and restart it later; it picks up where it left off

### I accidentally deleted emails I wanted to keep
- If you used `--backup`, check your backup folder for the ZIP files
- Yahoo: Deleted emails may be recoverable from Trash for a short time
- Gmail: Check the Trash folder — deleted emails stay there for 30 days

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `python3 setup.py` | Interactive setup wizard |
| `python3 terabyebye.py` | Preview (no deletion) |
| `python3 terabyebye.py --safe` | Backup + delete with confirmation at every step |
| `python3 terabyebye.py --delete` | Delete with confirmation |
| `python3 terabyebye.py --backup ./folder` | Backup only (no deletion) |
| `python3 terabyebye.py --backup ./folder --delete` | Backup then delete |
| `python3 terabyebye.py --status` | Show which providers are configured |

---

## Still Stuck?

Open an issue on the GitHub page with:
- What command you ran
- What error message you got (copy/paste the whole thing)
- Your operating system (Mac/Windows/Linux)

We'll help you out.
