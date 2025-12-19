#!/usr/bin/env python3
"""
CRM Daily Briefing Generator
Reads contacts.md, queries chat.db for activity, outputs to Apple Notes.

Uses macOS 26+ native markdown import for rich formatting (tables, headers, etc.)

Usage:
  python3 crm_briefing.py           # Generate briefing to stdout
  python3 crm_briefing.py --note    # Generate and save to Apple Notes (rich formatting)
"""

import sqlite3
import os
import sys
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

DB = os.path.expanduser('~/Library/Messages/chat.db')
CONTACTS_FILE = os.path.expanduser('~/skills/imessage-assistant/references/contacts.md')
TEMP_MD_FILE = '/tmp/crm_daily_briefing.md'


def parse_contacts():
    """Parse contacts.md for customer profiles with Promise/Waiting fields."""
    contacts = []
    
    with open(CONTACTS_FILE, 'r') as f:
        content = f.read()
    
    # Find the Richmond General Customers section
    customer_section = re.search(
        r'## Detailed Profiles - Richmond General Customers\n(.+?)(?=\n---|\n## |$)', 
        content, 
        re.DOTALL
    )
    
    if not customer_section:
        return contacts
    
    section_text = customer_section.group(1)
    
    # Split by ### headers
    profiles = re.split(r'\n### ', section_text)
    
    for profile in profiles:
        if not profile.strip():
            continue
            
        lines = profile.strip().split('\n')
        name = lines[0].strip()
        
        contact = {
            'name': name,
            'phone': None,
            'category': None,
            'promise': None,
            'waiting': None,
            'status': None,
            'last_contact': None,
            'reminder': None
        }
        
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('- **Phone**:'):
                contact['phone'] = re.search(r'\+\d+', line)
                if contact['phone']:
                    contact['phone'] = contact['phone'].group()
            elif line.startswith('- **Category**:'):
                contact['category'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Promise**:'):
                val = line.split(':', 1)[1].strip()
                contact['promise'] = None if val.lower() == 'null' else val
            elif line.startswith('- **Waiting**:'):
                val = line.split(':', 1)[1].strip()
                contact['waiting'] = None if val.lower() == 'null' else val
            elif line.startswith('- **Status**:'):
                contact['status'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Last Contact**:'):
                contact['last_contact'] = line.split(':', 1)[1].strip()
            elif '⚠️' in line or 'REMINDER' in line:
                contact['reminder'] = line.replace('- **⚠️ REMINDER**:', '').strip()
        
        if contact['phone']:
            contacts.append(contact)
    
    return contacts


def get_last_message_info(phone):
    """Get last message date & who sent it for a phone number."""
    phone_digits = re.sub(r'[^\d]', '', phone)
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''
        SELECT datetime(m.date/1000000000+978307200,'unixepoch','localtime'),
               m.is_from_me
        FROM message m 
        JOIN handle h ON m.handle_id=h.ROWID
        WHERE h.id LIKE ?
        ORDER BY m.date DESC LIMIT 1
    ''', (f'%{phone_digits}%',))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'last_date': result[0],
            'last_was_me': result[1] == 1
        }
    return None


def days_since(date_str):
    """Calculate days since a date string."""
    try:
        if not date_str:
            return None
        for fmt in ['%b %d, %Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S']:
            try:
                dt = datetime.strptime(date_str.split()[0] if ' ' in date_str and ':' in date_str else date_str, fmt)
                return (datetime.now() - dt).days
            except:
                continue
        return None
    except:
        return None


def generate_briefing(contacts):
    """Generate the CRM briefing in markdown format for macOS 26 Notes import."""
    today = datetime.now().strftime('%b %d, %Y')
    
    promises = []
    waiting = []
    nurture = []
    alerts = []
    
    for c in contacts:
        msg_info = get_last_message_info(c['phone'])
        
        if msg_info:
            days = days_since(msg_info['last_date'].split()[0])
            whose_turn = "us" if not msg_info['last_was_me'] else "them"
        else:
            days = None
            whose_turn = "unknown"
        
        if c['promise']:
            promises.append({**c, 'days': days, 'whose_turn': whose_turn})
        
        if c['waiting']:
            cold_warning = " ⚠️" if days and days > 7 else ""
            waiting.append({**c, 'days': days, 'cold_warning': cold_warning})
        
        if c['category'] == 'Nurture':
            nurture.append(c)
        
        if c['reminder']:
            alerts.append(c)
    
    # Build markdown
    out = []
    out.append(f"# 📬 Daily CRM Briefing — {today}\n")
    
    # Priority callout if there are urgent items
    urgent = [p for p in promises if 'TOMORROW' in (p.get('status', '') or '').upper()]
    if urgent:
        out.append(f"> **Priority Focus:** {urgent[0]['promise']}\n")
    
    out.append("---\n")
    
    # Promises section with table
    out.append("## 🔴 PROMISES TO KEEP\n")
    if promises:
        out.append("| Contact | What I Owe | Status |")
        out.append("|---------|-----------|--------|")
        for p in promises:
            status = p.get('status', '') or ''
            out.append(f"| **{p['name']}** | {p['promise']} | {status} |")
    else:
        out.append("*None — you're all caught up!*")
    out.append("")
    
    # Waiting section with table
    out.append("## 🟡 THEIR TURN\n")
    if waiting:
        out.append("| Contact | Waiting For | Days |")
        out.append("|---------|-------------|------|")
        for w in waiting:
            days_str = str(w['days']) if w['days'] is not None else "?"
            bold_days = f"**{days_str}**" if w['days'] and w['days'] > 7 else days_str
            out.append(f"| {w['name']} | {w['waiting']} | {bold_days}{w['cold_warning']} |")
    else:
        out.append("*Nothing pending*")
    out.append("")
    
    # Nurture section as list
    out.append("## 🟢 NURTURE (no action needed)\n")
    if nurture:
        for i, n in enumerate(nurture, 1):
            note = n.get('status', '') or ''
            out.append(f"{i}. **{n['name']}** — {note}")
    else:
        out.append("*None*")
    out.append("")
    
    # Alerts section
    if alerts:
        out.append("## ⚠️ DON'T FORGET\n")
        for a in alerts:
            out.append(f"- **{a['name']}**: {a['reminder']}")
        out.append("")
    
    # Footer
    out.append("---")
    out.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    
    return '\n'.join(out)


def check_accessibility():
    """Check if System Events has accessibility permissions for UI automation."""
    check_script = '''
    tell application "System Events"
        try
            set frontApp to name of first process whose frontmost is true
            return "ok"
        on error errMsg
            return "error: " & errMsg
        end try
    end tell
    '''
    result = subprocess.run(['osascript', '-e', check_script], 
                           capture_output=True, text=True)
    return 'ok' in result.stdout.lower()


def save_to_apple_notes_macos26(markdown_content):
    """
    Save briefing to Apple Notes using macOS 26 markdown import.
    This provides rich formatting (tables, headers, bold, etc.)
    Returns: True on success, False on failure, None if accessibility missing
    """
    # Pre-flight: Check accessibility permissions
    if not check_accessibility():
        print("❌ System Events lacks accessibility permissions.", file=sys.stderr)
        print("   Grant access in: System Settings → Privacy & Security → Accessibility", file=sys.stderr)
        return None  # Signal to skip to legacy without retry
    
    # Step 1: Write markdown to temp file
    with open(TEMP_MD_FILE, 'w') as f:
        f.write(markdown_content)
    
    # Step 2: Quit Notes if running (cleaner import)
    subprocess.run(['osascript', '-e', 'tell application "Notes" to quit'], 
                   capture_output=True)
    time.sleep(0.5)
    
    # Step 3: Open markdown file with Notes (triggers import dialog)
    subprocess.run(['open', '-a', 'Notes', TEMP_MD_FILE], capture_output=True)
    time.sleep(1.5)
    
    # Step 4: Click the Import button
    click_import_script = '''
    tell application "System Events"
        tell process "Notes"
            try
                click button "Import" of sheet 1 of window 1
                return "clicked"
            on error
                try
                    keystroke return
                    return "keystroke"
                on error errMsg
                    return "error: " & errMsg
                end try
            end try
        end tell
    end tell
    '''
    result = subprocess.run(['osascript', '-e', click_import_script], 
                           capture_output=True, text=True)
    
    if 'error' in result.stdout.lower():
        print(f"Warning: Import click issue: {result.stdout}", file=sys.stderr)
    
    time.sleep(1)
    
    # Step 5: Find and move the imported note to CRM Briefings
    # NOTE: Direct folder reference works; iteration over folders/notes is buggy in Notes AppleScript
    move_script = '''
    tell application "Notes"
        tell account "iCloud"
            -- Ensure CRM Briefings folder exists
            if not (exists folder "CRM Briefings") then
                make new folder with properties {name:"CRM Briefings"}
            end if
            
            -- Delete existing daily briefings in CRM Briefings
            tell folder "CRM Briefings"
                set existingNotes to (notes whose name contains "Daily CRM Briefing")
                repeat with n in existingNotes
                    delete n
                end repeat
            end tell
            
            -- Find and move from Imported Notes folders (direct reference, not iteration)
            set movedNote to false
            set sourceFolder to ""
            
            -- Try each possible Imported Notes folder directly
            repeat with i from 0 to 10
                try
                    if i = 0 then
                        set folderName to "Imported Notes"
                    else
                        set folderName to "Imported Notes " & i
                    end if
                    
                    set n to first note of folder folderName whose name contains "Daily CRM Briefing"
                    move n to folder "CRM Briefings"
                    set movedNote to true
                    set sourceFolder to folderName
                    exit repeat
                end try
            end repeat
            
            -- Clean up empty Imported Notes folders
            repeat with i from 0 to 10
                try
                    if i = 0 then
                        set folderName to "Imported Notes"
                    else
                        set folderName to "Imported Notes " & i
                    end if
                    
                    set f to folder folderName
                    if (count of notes of f) = 0 then
                        delete f
                    end if
                end try
            end repeat
            
            if movedNote then
                return "✅ Moved to CRM Briefings from " & sourceFolder
            else
                return "⚠️ Note not found in Imported Notes folders"
            end if
        end tell
    end tell
    '''
    
    result = subprocess.run(['osascript', '-e', move_script], 
                           capture_output=True, text=True)
    
    # Step 6: Clean up temp file
    try:
        os.remove(TEMP_MD_FILE)
    except:
        pass
    
    return "✅" in result.stdout


def save_to_apple_notes_legacy(content, title="Daily CRM Briefing"):
    """Legacy method: Save briefing using AppleScript text injection (raw, no formatting)."""
    escaped = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            if not (exists folder "CRM Briefings") then
                make new folder with properties {{name:"CRM Briefings"}}
            end if
            tell folder "CRM Briefings"
                set existingNotes to (notes whose name is "{title}")
                if (count of existingNotes) > 0 then
                    delete (item 1 of existingNotes)
                end if
                make new note with properties {{name:"{title}", body:"{escaped}"}}
            end tell
        end tell
    end tell
    '''
    
    try:
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error saving to Notes: {e.stderr.decode()}", file=sys.stderr)
        return False


if __name__ == '__main__':
    contacts = parse_contacts()
    briefing = generate_briefing(contacts)
    
    if '--note' in sys.argv:
        # Use macOS 26 markdown import for rich formatting
        result = save_to_apple_notes_macos26(briefing)
        
        if result is True:
            print("✅ Briefing saved to Apple Notes (CRM Briefings folder)")
        elif result is None:
            # Accessibility missing — go straight to legacy (no retry)
            print("Falling back to legacy method...", file=sys.stderr)
            if save_to_apple_notes_legacy(briefing):
                print("✅ Saved via legacy method (no rich formatting)")
            else:
                print("❌ Failed to save to Apple Notes")
                print(briefing)
        else:
            # result is False — import failed, try legacy
            print("❌ macOS 26 import failed")
            print("Trying legacy method...", file=sys.stderr)
            if save_to_apple_notes_legacy(briefing):
                print("✅ Saved via legacy method (no rich formatting)")
            else:
                print(briefing)
    
    elif '--legacy' in sys.argv:
        # Force legacy method (raw text, no formatting)
        if save_to_apple_notes_legacy(briefing):
            print("✅ Briefing saved to Apple Notes (legacy mode)")
        else:
            print("❌ Failed to save to Apple Notes")
            print(briefing)
    
    else:
        # Default: output markdown to stdout
        print(briefing)
