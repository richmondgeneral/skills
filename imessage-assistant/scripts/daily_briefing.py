#!/usr/bin/env python3
"""
Daily Briefing Generator v0.2
Unified briefing: iMessage activity + property alerts + CRM

Usage:
  python3 daily_briefing.py           # Generate briefing to stdout
  python3 daily_briefing.py --note    # Generate and save to Apple Notes
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
TEMP_MD_FILE = '/tmp/daily_briefing.md'

# Property-related keywords to flag from Sue Miller
PROPERTY_KEYWORDS = [
    'alley', 'water', 'utility', 'utilities', 'village', 'building', 
    'maintenance', 'shut-off', 'shutoff', 'shut off', 'notice', 
    'richmond', 'complaint', 'inspector', 'code', 'permit', 'rent',
    'lease', 'repair', 'fix', 'broken', 'hvac', 'heat', 'electric'
]

# Known contacts for name resolution
KNOWN_CONTACTS = {
    '+18152362387': 'Sue Miller',
    '+18472871148': 'Dawn',
    '+18475677182': 'Jeff Thompson',
    '+16305444884': 'Jennifer',
    '+12242308079': 'Freeman (Dad)',
    '+13129143889': 'Mike Giba',
    '+17736763930': 'Amy D (HOA)',
    '+18474179386': 'Gary Goza Sr',
    '+16519834441': 'Jamie Boutain',
    '+13124483219': 'Walid Bandar',
    '+18473383408': 'Lynn',
    '+12623082827': 'Steven (Elmhurst)',
    '+14148757568': '414 Contact',
    '+12246276323': 'Laura (First REO)',
    '+18477747698': 'Bill North',
    '+18479803301': 'Josh (White Dually)',
    '+18082228761': 'Pete (eBay)',
}

SUE_PHONE = '+18152362387'


def extract_text(blob):
    """Extract text from attributedBody blob (for RCS/iMessage)."""
    if not blob:
        return None
    try:
        idx = blob.find(b"NSString")
        if idx == -1:
            return None
        plus_idx = blob.find(b"+", idx)
        if plus_idx == -1:
            return None
        start = plus_idx + 2
        end = len(blob)
        for m in [b"NSDictionary", b"\x00\x00\x00"]:
            p = blob.find(m, start)
            if p != -1 and p < end:
                end = p
        text = blob[start:end].decode("utf-8", errors="ignore")
        # Strip various trailing artifacts from blob extraction
        text = re.sub(r"iI[A-Za-z0-9>()]*$", "", text)
        text = re.sub(r"\s*iI.*$", "", text)
        return text.strip()
    except:
        return None


def get_todays_messages(target_date=None):
    """Get message activity summary for a given date.
    
    Args:
        target_date: YYYY-MM-DD string, defaults to today
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    if target_date is None:
        target_date = datetime.now().strftime('%Y-%m-%d')
    
    c.execute('''
        SELECT 
            h.id,
            MAX(datetime(m.date/1000000000+978307200,'unixepoch','localtime')) as last_msg,
            SUM(CASE WHEN m.is_from_me = 0 THEN 1 ELSE 0 END) as inbound,
            SUM(CASE WHEN m.is_from_me = 1 THEN 1 ELSE 0 END) as outbound,
            COUNT(*) as total
        FROM message m
        JOIN handle h ON m.handle_id = h.ROWID
        WHERE date(m.date/1000000000+978307200,'unixepoch','localtime') = ?
        GROUP BY h.id
        ORDER BY last_msg DESC
    ''', (target_date,))
    
    results = c.fetchall()
    conn.close()
    
    activity = []
    for row in results:
        phone = row[0]
        # Normalize phone for lookup
        phone_normalized = '+' + re.sub(r'[^\d]', '', phone)[-10:] if phone else phone
        phone_full = '+1' + re.sub(r'[^\d]', '', phone)[-10:] if phone else phone
        
        name = KNOWN_CONTACTS.get(phone_full, KNOWN_CONTACTS.get(phone_normalized, phone))
        
        activity.append({
            'phone': phone,
            'name': name,
            'last': row[1].split()[1][:5] if row[1] else '?',  # Just HH:MM
            'inbound': row[2],
            'outbound': row[3],
            'total': row[4]
        })
    
    return activity


def get_sue_property_messages():
    """Get recent messages from Sue Miller that mention property-related keywords."""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    sue_digits = re.sub(r'[^\d]', '', SUE_PHONE)
    
    # Get messages from last 7 days - include attributedBody for RCS
    c.execute('''
        SELECT 
            datetime(m.date/1000000000+978307200,'unixepoch','localtime') as msg_time,
            m.text,
            m.attributedBody,
            m.is_from_me
        FROM message m
        JOIN handle h ON m.handle_id = h.ROWID
        WHERE h.id LIKE ?
        AND m.date/1000000000+978307200 > CAST(strftime('%s', 'now', '-7 days') AS INTEGER)
        ORDER BY m.date DESC
    ''', (f'%{sue_digits}%',))
    
    results = c.fetchall()
    conn.close()
    
    property_messages = []
    for row in results:
        msg_time, text, blob, is_from_me = row
        # Try text field first, then attributedBody blob (for RCS)
        content = text or extract_text(blob)
        if not content:
            continue
        
        content_lower = content.lower()
        # Check if message contains property keywords
        if any(kw in content_lower for kw in PROPERTY_KEYWORDS):
            property_messages.append({
                'time': msg_time,
                'text': content,
                'from_me': is_from_me == 1
            })
    
    return property_messages


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


def extract_urgent_items(contacts, property_messages, todays_activity):
    """Extract time-sensitive urgent items."""
    urgent = []
    
    # Check CRM contacts for TOMORROW or time-sensitive status
    for c in contacts:
        status = (c.get('status', '') or '').upper()
        if 'TOMORROW' in status or 'TODAY' in status:
            urgent.append(f"{c['name']}: {c['promise'] or c['status']}")
    
    # Check property messages for action items
    for msg in property_messages:
        if msg['from_me']:
            continue
        text_lower = msg['text'].lower()
        # Look for action requests
        if any(phrase in text_lower for phrase in ['please', 'need to', 'call', 'clean up', 'fix']):
            # Truncate long messages
            display_text = msg['text'][:80] + '...' if len(msg['text']) > 80 else msg['text']
            urgent.append(f"Sue Miller: {display_text}")
            break  # Only show most recent property action
    
    return urgent


def generate_briefing(test_date=None):
    """Generate the unified daily briefing.
    
    Args:
        test_date: Optional YYYY-MM-DD string for testing historical dates
    """
    if test_date:
        target_date = datetime.strptime(test_date, '%Y-%m-%d')
        today_display = target_date.strftime('%b %d, %Y')
        today_sql = test_date
    else:
        target_date = datetime.now()
        today_display = target_date.strftime('%b %d, %Y')
        today_sql = target_date.strftime('%Y-%m-%d')
    
    # Gather data
    todays_activity = get_todays_messages(today_sql)
    property_messages = get_sue_property_messages()
    contacts = parse_contacts()
    urgent_items = extract_urgent_items(contacts, property_messages, todays_activity)
    
    # Process CRM data
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
    
    # Build markdown output
    out = []
    out.append(f"# 📋 Daily Briefing — {today_display}\n")
    
    # URGENT section
    if urgent_items:
        out.append("## 🚨 URGENT\n")
        for item in urgent_items:
            out.append(f"- {item}")
        out.append("")
    
    # PROPERTY/BUILDING section
    today_property = [m for m in property_messages if today_sql in m['time']]
    if today_property:
        out.append("## 🏢 PROPERTY/BUILDING\n")
        for msg in today_property[:5]:  # Limit to 5 most recent
            direction = "→" if msg['from_me'] else "←"
            time_short = msg['time'].split()[1][:5]
            text_short = msg['text'][:100] + '...' if len(msg['text']) > 100 else msg['text']
            out.append(f"- **{time_short}** {direction} {text_short}")
        out.append("")
    
    # TODAY'S MESSAGES section
    if todays_activity:
        out.append("## 💬 TODAY'S MESSAGES\n")
        out.append("| Contact | In | Out | Last |")
        out.append("|---------|---:|----:|------|")
        for a in todays_activity[:15]:  # Limit to 15 rows
            # Flag potential unreads
            unread_flag = " 📩" if a['inbound'] > 0 and a['outbound'] == 0 else ""
            out.append(f"| {a['name']}{unread_flag} | {a['inbound']} | {a['outbound']} | {a['last']} |")
        out.append("")
    
    out.append("---\n")
    
    # CRM PROMISES section
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
    
    # THEIR TURN section
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
    
    # NURTURE section
    out.append("## 🟢 NURTURE (no action needed)\n")
    if nurture:
        for i, n in enumerate(nurture, 1):
            note = n.get('status', '') or ''
            out.append(f"{i}. **{n['name']}** — {note}")
    else:
        out.append("*None*")
    out.append("")
    
    # DON'T FORGET section
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
    """Check if System Events has accessibility permissions."""
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
    """Save briefing using macOS 26 markdown import for rich formatting."""
    if not check_accessibility():
        print("❌ System Events lacks accessibility permissions.", file=sys.stderr)
        return None
    
    # Write markdown to temp file
    with open(TEMP_MD_FILE, 'w') as f:
        f.write(markdown_content)
    
    # Quit Notes if running
    subprocess.run(['osascript', '-e', 'tell application "Notes" to quit'],
                    capture_output=True)
    time.sleep(0.5)
    
    # Open markdown file with Notes
    subprocess.run(['open', '-a', 'Notes', TEMP_MD_FILE], capture_output=True)
    time.sleep(1.5)
    
    # Click Import button
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
    subprocess.run(['osascript', '-e', click_import_script],
                    capture_output=True, text=True)
    time.sleep(1)
    
    # Move to Daily Briefings folder
    move_script = '''
    tell application "Notes"
        tell account "iCloud"
            if not (exists folder "Daily Briefings") then
                make new folder with properties {name:"Daily Briefings"}
            end if
            
            tell folder "Daily Briefings"
                set existingNotes to (notes whose name contains "Daily Briefing")
                repeat with n in existingNotes
                    delete n
                end repeat
            end tell
            
            set movedNote to false
            set sourceFolder to ""
            
            repeat with i from 0 to 10
                try
                    if i = 0 then
                        set folderName to "Imported Notes"
                    else
                        set folderName to "Imported Notes " & i
                    end if
                    
                    set n to first note of folder folderName whose name contains "Daily Briefing"
                    move n to folder "Daily Briefings"
                    set movedNote to true
                    set sourceFolder to folderName
                    exit repeat
                end try
            end repeat
            
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
                return "✅ Moved to Daily Briefings from " & sourceFolder
            else
                return "⚠️ Note not found"
            end if
        end tell
    end tell
    '''
    
    result = subprocess.run(['osascript', '-e', move_script],
                            capture_output=True, text=True)
    
    try:
        os.remove(TEMP_MD_FILE)
    except:
        pass
    
    return "✅" in result.stdout


def save_to_apple_notes_legacy(content, title="Daily Briefing"):
    """Legacy method: raw text, no formatting."""
    escaped = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            if not (exists folder "Daily Briefings") then
                make new folder with properties {{name:"Daily Briefings"}}
            end if
            tell folder "Daily Briefings"
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
        print(f"Error: {e.stderr.decode()}", file=sys.stderr)
        return False


if __name__ == '__main__':
    # Parse optional --date YYYY-MM-DD for testing historical dates
    test_date = None
    for i, arg in enumerate(sys.argv):
        if arg == '--date' and i + 1 < len(sys.argv):
            test_date = sys.argv[i + 1]
    
    briefing = generate_briefing(test_date=test_date)
    
    # Generate note title based on date
    if test_date:
        note_date = datetime.strptime(test_date, '%Y-%m-%d')
        note_title = f"Daily Briefing — {note_date.strftime('%b %d, %Y')}"
    else:
        note_title = f"Daily Briefing — {datetime.now().strftime('%b %d, %Y')}"
    
    if '--note' in sys.argv:
        # For historical dates, use legacy method to avoid overwriting today's note
        if test_date:
            if save_to_apple_notes_legacy(briefing, title=note_title):
                print(f"✅ {note_title} saved to Apple Notes")
            else:
                print("❌ Failed to save")
                print(briefing)
        else:
            result = save_to_apple_notes_macos26(briefing)
            
            if result is True:
                print("✅ Daily Briefing saved to Apple Notes (Daily Briefings folder)")
            elif result is None:
                print("Falling back to legacy method...", file=sys.stderr)
                if save_to_apple_notes_legacy(briefing, title=note_title):
                    print("✅ Saved via legacy method")
                else:
                    print("❌ Failed to save")
                    print(briefing)
            else:
                print("❌ macOS 26 import failed, trying legacy...", file=sys.stderr)
                if save_to_apple_notes_legacy(briefing, title=note_title):
                    print("✅ Saved via legacy method")
                else:
                    print(briefing)
    else:
        print(briefing)
