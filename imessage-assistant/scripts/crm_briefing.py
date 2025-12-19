#!/usr/bin/env python3
"""
CRM Daily Briefing Generator
Reads contacts.md, queries chat.db for activity, outputs to Apple Notes.

Usage:
  python3 crm_briefing.py           # Generate briefing to stdout
  python3 crm_briefing.py --note    # Generate and save to Apple Notes
"""

import sqlite3
import os
import sys
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

DB = os.path.expanduser('~/Library/Messages/chat.db')
CONTACTS_FILE = os.path.expanduser('~/skills/imessage-assistant/references/contacts.md')

def parse_contacts():
    """Parse contacts.md for customer profiles with Promise/Waiting fields."""
    contacts = []
    current_contact = None
    
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
        # Handle both "Dec 19, 2025" and "2025-12-19" formats
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
    """Generate the CRM briefing markdown."""
    today = datetime.now().strftime('%b %d, %Y')
    
    promises = []
    waiting = []
    nurture = []
    alerts = []
    
    for c in contacts:
        # Get live data from chat.db
        msg_info = get_last_message_info(c['phone'])
        
        if msg_info:
            days = days_since(msg_info['last_date'].split()[0])
            whose_turn = "us" if not msg_info['last_was_me'] else "them"
        else:
            days = None
            whose_turn = "unknown"
        
        # Categorize
        if c['promise']:
            promises.append({
                **c,
                'days': days,
                'whose_turn': whose_turn
            })
        
        if c['waiting']:
            cold_warning = " ⚠️" if days and days > 7 else ""
            waiting.append({
                **c,
                'days': days,
                'cold_warning': cold_warning
            })
        
        if c['category'] == 'Nurture':
            nurture.append(c)
        
        if c['reminder']:
            alerts.append(c)
    
    # Build output
    out = []
    out.append(f"# 📬 Daily Briefing — {today}\n")
    
    # Promises section
    out.append("## 🔴 PROMISES TO KEEP\n")
    if promises:
        out.append("| Who | What I Owe Them | Status |")
        out.append("|-----|-----------------|--------|")
        for p in promises:
            status = p.get('status', '') or ''
            out.append(f"| {p['name']} | {p['promise']} | {status} |")
    else:
        out.append("*None — you're all caught up!*")
    out.append("")
    
    # Waiting section
    out.append("## 🟡 THEIR TURN\n")
    if waiting:
        out.append("| Who | Waiting For | Days |")
        out.append("|-----|-------------|------|")
        for w in waiting:
            days_str = str(w['days']) if w['days'] is not None else "?"
            out.append(f"| {w['name']} | {w['waiting']} | {days_str}{w['cold_warning']} |")
    else:
        out.append("*Nothing pending*")
    out.append("")
    
    # Nurture section
    out.append("## 🟢 NURTURE (no action needed)\n")
    if nurture:
        for n in nurture:
            note = n.get('status', '') or n.get('note', '') or ''
            out.append(f"- {n['name']} — {note}")
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


def save_to_apple_notes(content, title="Daily CRM Briefing"):
    """Save briefing to Apple Notes."""
    # Escape for AppleScript
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
        if save_to_apple_notes(briefing):
            print("✅ Briefing saved to Apple Notes (CRM Briefings folder)")
        else:
            print("❌ Failed to save to Apple Notes")
            print(briefing)
    else:
        print(briefing)
