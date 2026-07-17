#!/usr/bin/env python3
"""
Unified Daily Briefing Generator
Personal contacts first, then CRM. One chat.db pass.

Usage:
  python3 daily_briefing.py              # Output to terminal
  python3 daily_briefing.py --note       # Save to Apple Notes (rich formatting)
  python3 daily_briefing.py --verbose    # Debug output
"""

import sqlite3
import os
import sys
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

# chat.db is live, WAL-mode, and continuously written by Messages + iCloud.
# Open it read-only AND immutable so reads take no locks and never touch the
# WAL — a plain connection can checkpoint it and disrupt Messages/iCloud sync.
DB = '/Users/scottybe/Library/Messages/chat.db'
# contacts-manager is a sibling skill; resolve relative to this script so the
# briefing works from the repo clone or the installed plugin (no hardcoded path).
CONTACTS_FILE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'contacts-manager', 'references', 'contacts.md'))
TEMP_MD_FILE = '/tmp/daily_briefing.md'
VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv


def log(msg):
    if VERBOSE:
        print(f"[DEBUG] {msg}", file=sys.stderr)


def parse_all_contacts():
    """Parse contacts.md for both Core and CRM contacts."""
    contacts = {'core': [], 'crm': []}
    
    try:
        with open(CONTACTS_FILE, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        log(f"Contacts file not found: {CONTACTS_FILE}")
        return contacts
    
    # Parse Core contacts
    core_section = re.search(
        r'## Detailed Profiles - Core\n(.+?)(?=\n---|\n## Detailed Profiles - Richmond|$)', 
        content, re.DOTALL
    )
    if core_section:
        contacts['core'] = parse_profiles(core_section.group(1), 'core')
        log(f"Parsed {len(contacts['core'])} core contacts")
    
    # Parse CRM contacts
    crm_section = re.search(
        r'## Detailed Profiles - Richmond General Customers\n(.+?)(?=\n---|\n## |$)', 
        content, re.DOTALL
    )
    if crm_section:
        contacts['crm'] = parse_profiles(crm_section.group(1), 'crm')
        log(f"Parsed {len(contacts['crm'])} CRM contacts")
    
    return contacts


def parse_profiles(section_text, contact_type):
    """Parse profile blocks from a section."""
    contacts = []
    profiles = re.split(r'\n### ', section_text)
    
    for profile in profiles:
        if not profile.strip():
            continue
        
        lines = profile.strip().split('\n')
        name = lines[0].strip()
        
        contact = {
            'name': name,
            'phone': None,
            'relationship': None,
            'category': None,
            'promise': None,
            'waiting': None,
            'status': None,
            'reminder': None,
            'type': contact_type
        }
        
        for line in lines[1:]:
            line = line.strip()
            
            # Phone - multiple formats
            if line.startswith('- **Phone**:'):
                phone_match = re.search(r'\+[\d]+', line)
                if phone_match:
                    contact['phone'] = phone_match.group()
            
            # Relationship (core contacts)
            elif line.startswith('- **Relationship**:'):
                contact['relationship'] = line.split(':', 1)[1].strip()
            
            # Category (CRM contacts)
            elif line.startswith('- **Category**:'):
                contact['category'] = line.split(':', 1)[1].strip()
            
            # Promise
            elif line.startswith('- **Promise**:'):
                val = line.split(':', 1)[1].strip()
                contact['promise'] = None if val.lower() == 'null' else val
            
            # Waiting
            elif line.startswith('- **Waiting**:'):
                val = line.split(':', 1)[1].strip()
                contact['waiting'] = None if val.lower() == 'null' else val
            
            # Status
            elif line.startswith('- **Status**:'):
                contact['status'] = line.split(':', 1)[1].strip()
            
            # Reminders/warnings
            elif '⚠️' in line and 'REMINDER' in line.upper():
                contact['reminder'] = re.sub(r'- \*\*⚠️\s*REMINDER\*\*:\s*', '', line).strip()
        
        if contact['phone']:
            contacts.append(contact)
            log(f"  Parsed: {name} ({contact['phone']})")
        else:
            log(f"  Skipped (no phone): {name}")
    
    return contacts


def get_message_status_batch(phones):
    """Query chat.db once for all phone numbers. Returns dict of phone -> status."""
    if not os.path.exists(DB):
        log(f"Messages database not found: {DB}")
        return {}
    
    results = {}
    try:
        conn = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
    except sqlite3.Error as e:
        # chat.db needs Full Disk Access for the running process; launchd agents
        # often lack it. Degrade gracefully — skip message status and keep the
        # rest of the briefing instead of crashing the whole run.
        log(f"chat.db unreadable ({e}); skipping message status "
            f"(grant Full Disk Access to enable it).")
        return {}
    c = conn.cursor()
    
    for phone in phones:
        phone_digits = re.sub(r'[^\d]', '', phone)
        # Use last 10 digits (US number without country code) for matching
        # Require it to be at the END of the handle to avoid partial matches
        search_digits = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
        
        c.execute('''
            SELECT datetime(m.date/1000000000+978307200,'unixepoch','localtime'),
                   m.is_from_me
            FROM message m 
            JOIN handle h ON m.handle_id=h.ROWID
            WHERE h.id LIKE ?
            ORDER BY m.date DESC LIMIT 1
        ''', (f'%{search_digits}',))  # Match at end of handle ID
        
        row = c.fetchone()
        if row:
            results[phone] = {
                'last_date': row[0],
                'is_from_me': row[1] == 1
            }
            log(f"  {phone}: last {row[0]}, from_me={row[1]}")
    
    conn.close()
    return results


def days_since(date_str):
    """Calculate days since a date string."""
    if not date_str:
        return None
    try:
        # Handle "2025-12-22 14:30:00" format from SQLite
        dt_str = date_str.split()[0] if ' ' in date_str else date_str
        for fmt in ['%Y-%m-%d', '%b %d, %Y']:
            try:
                dt = datetime.strptime(dt_str, fmt)
                return (datetime.now() - dt).days
            except ValueError:
                continue
        return None
    except Exception as e:
        log(f"Date parse error: {e}")
        return None


def generate_briefing(contacts, msg_status):
    """Generate unified daily briefing."""
    today = datetime.now().strftime('%A, %b %d, %Y')
    now_time = datetime.now().strftime('%H:%M')
    
    out = []
    out.append(f"# 📬 Daily Briefing — {today}\n")
    
    # ===== PERSONAL CONTACTS =====
    out.append("## 👥 PERSONAL\n")
    
    personal_rows = []
    for c in contacts['core']:
        status = msg_status.get(c['phone'], {})
        days = days_since(status.get('last_date'))
        is_from_me = status.get('is_from_me')
        
        # Determine status emoji and action
        if days is None:
            emoji = "❓"
            turn = "unknown"
            action = "—"
        elif is_from_me:
            # I sent last - their turn
            if days > 7:
                emoji = "🔵"  # Cold, their turn
                turn = "them"
                action = "cold"
            elif days > 3:
                emoji = "🟡"
                turn = "them"
                action = "—"
            else:
                emoji = "✅"
                turn = "them"
                action = "—"
        else:
            # They sent last - my turn
            if days > 3:
                emoji = "🔴"
                turn = "me"
                action = "**reply needed**"
            elif days > 1:
                emoji = "🟠"
                turn = "me"
                action = "reply soon"
            else:
                emoji = "🟡"
                turn = "me"
                action = "reply"
        
        days_str = f"{days}d" if days is not None else "?"
        personal_rows.append((c['name'], emoji, turn, days_str, action))
    
    if personal_rows:
        out.append("| Contact | | Turn | Last | Action |")
        out.append("|---------|--|------|------|--------|")
        for name, emoji, turn, days_str, action in personal_rows:
            out.append(f"| {name} | {emoji} | {turn} | {days_str} | {action} |")
    else:
        out.append("*No personal contacts configured*")
    out.append("")
    
    # ===== CRM SECTION =====
    out.append("---\n")
    out.append("## 🏪 RICHMOND GENERAL CRM\n")
    
    # Split CRM into promises, waiting, nurture
    promises = []
    waiting = []
    nurture = []
    
    for c in contacts['crm']:
        status = msg_status.get(c['phone'], {})
        days = days_since(status.get('last_date'))
        c['_days'] = days
        c['_is_from_me'] = status.get('is_from_me')
        
        if c['promise']:
            promises.append(c)
        if c['waiting']:
            waiting.append(c)
        if c['category'] == 'Nurture' and not c['promise'] and not c['waiting']:
            nurture.append(c)
    
    # Promises (what I owe them)
    out.append("### 🔴 Promises to Keep\n")
    if promises:
        out.append("| Contact | What I Owe | Days |")
        out.append("|---------|-----------|------|")
        for p in promises:
            days_str = f"{p['_days']}" if p['_days'] is not None else "?"
            out.append(f"| {p['name']} | {p['promise']} | {days_str} |")
    else:
        out.append("*All clear!*")
    out.append("")
    
    # Waiting (what they owe me)
    out.append("### 🟡 Their Turn\n")
    if waiting:
        out.append("| Contact | Waiting For | Days |")
        out.append("|---------|-------------|------|")
        for w in waiting:
            days_str = f"{w['_days']}" if w['_days'] is not None else "?"
            cold = " ⚠️" if w['_days'] and w['_days'] > 7 else ""
            out.append(f"| {w['name']} | {w['waiting']} | {days_str}{cold} |")
    else:
        out.append("*Nothing pending*")
    out.append("")
    
    # Nurture
    if nurture:
        out.append("### 🟢 Nurture\n")
        for n in nurture:
            note = n.get('status', '') or ''
            out.append(f"- {n['name']} — {note}")
        out.append("")
    
    # ===== ALERTS =====
    all_contacts = contacts['core'] + contacts['crm']
    alerts = [c for c in all_contacts if c.get('reminder')]
    if alerts:
        out.append("---\n")
        out.append("## ⚠️ DON'T FORGET\n")
        for a in alerts:
            out.append(f"- **{a['name']}**: {a['reminder']}")
        out.append("")
    
    # Footer
    out.append("---")
    out.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    
    return '\n'.join(out)


def check_accessibility():
    """Check System Events accessibility permissions."""
    script = '''
    tell application "System Events"
        try
            set frontApp to name of first process whose frontmost is true
            return "ok"
        on error
            return "error"
        end try
    end tell
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return 'ok' in result.stdout.lower()


def save_to_apple_notes(markdown_content):
    """Save briefing to Apple Notes using macOS 26 markdown import."""
    if not check_accessibility():
        print("❌ System Events lacks accessibility permissions.", file=sys.stderr)
        print("   Grant in: System Settings → Privacy & Security → Accessibility", file=sys.stderr)
        return None
    
    # Write markdown to temp file
    with open(TEMP_MD_FILE, 'w') as f:
        f.write(markdown_content)
    
    # Quit Notes if running
    subprocess.run(['osascript', '-e', 'tell application "Notes" to quit'], capture_output=True)
    time.sleep(0.5)
    
    # Open markdown with Notes (triggers import)
    subprocess.run(['open', '-a', 'Notes', TEMP_MD_FILE], capture_output=True)
    time.sleep(1.5)
    
    # Click Import button
    click_script = '''
    tell application "System Events"
        tell process "Notes"
            try
                click button "Import" of sheet 1 of window 1
                return "clicked"
            on error
                keystroke return
                return "keystroke"
            end try
        end tell
    end tell
    '''
    subprocess.run(['osascript', '-e', click_script], capture_output=True)
    time.sleep(1)
    
    # Move to Daily Briefings folder
    move_script = '''
    tell application "Notes"
        tell account "iCloud"
            if not (exists folder "Daily Briefings") then
                make new folder with properties {name:"Daily Briefings"}
            end if
            
            -- Delete existing daily briefings
            tell folder "Daily Briefings"
                set existingNotes to (notes whose name contains "Daily Briefing")
                repeat with n in existingNotes
                    delete n
                end repeat
            end tell
            
            -- Find and move from Imported Notes
            repeat with i from 0 to 10
                try
                    if i = 0 then
                        set folderName to "Imported Notes"
                    else
                        set folderName to "Imported Notes " & i
                    end if
                    set n to first note of folder folderName whose name contains "Daily Briefing"
                    move n to folder "Daily Briefings"
                    
                    -- Clean empty folder
                    set f to folder folderName
                    if (count of notes of f) = 0 then delete f
                    
                    return "✅ Moved to Daily Briefings"
                end try
            end repeat
            return "⚠️ Note not found"
        end tell
    end tell
    '''
    result = subprocess.run(['osascript', '-e', move_script], capture_output=True, text=True)
    
    # Cleanup
    try:
        os.remove(TEMP_MD_FILE)
    except:
        pass
    
    return "✅" in result.stdout


def save_legacy(content):
    """Fallback: plain text Apple Notes save."""
    escaped = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            if not (exists folder "Daily Briefings") then
                make new folder with properties {{name:"Daily Briefings"}}
            end if
            tell folder "Daily Briefings"
                set existingNotes to (notes whose name contains "Daily Briefing")
                repeat with n in existingNotes
                    delete n
                end repeat
                make new note with properties {{name:"Daily Briefing", body:"{escaped}"}}
            end tell
        end tell
    end tell
    '''
    try:
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Legacy save failed: {e.stderr.decode() if e.stderr else str(e)}")
        return False


if __name__ == '__main__':
    log("Starting daily briefing generation")
    
    # Parse contacts
    contacts = parse_all_contacts()
    all_phones = [c['phone'] for c in contacts['core'] + contacts['crm']]
    
    # Query message status (one pass)
    log(f"Querying chat.db for {len(all_phones)} contacts")
    msg_status = get_message_status_batch(all_phones)
    
    # Generate briefing
    briefing = generate_briefing(contacts, msg_status)
    
    if '--note' in sys.argv:
        result = save_to_apple_notes(briefing)
        if result is True:
            print("✅ Briefing saved to Apple Notes (Daily Briefings folder)")
        elif result is None:
            print("Falling back to legacy...", file=sys.stderr)
            if save_legacy(briefing):
                print("✅ Saved via legacy method")
            else:
                print("❌ Failed to save")
                print(briefing)
        else:
            print("Trying legacy...", file=sys.stderr)
            if save_legacy(briefing):
                print("✅ Saved via legacy method")
            else:
                print(briefing)
    else:
        print(briefing)
