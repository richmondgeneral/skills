#!/usr/bin/env python3
"""
Send iMessage/RCS/SMS to contacts or group chats.
Handles service detection and group chat routing automatically.

Usage: 
  python3 send_message.py <phone_number> "message"
  python3 send_message.py --chat <chat_id> "message"
  python3 send_message.py --guid <chat_guid> "message"
  python3 send_message.py --lookup <chat_id>
"""

import sqlite3
import os
import sys
import subprocess
import re

DB_PATH = os.path.expanduser('~/Library/Messages/chat.db')

SERVICE_IDS = {
    'iMessage': '33900AA6-BFB5-49A8-B34A-2A8F783BE2F4',
    'SMS': 'E0595A22-53AF-4ECC-93BE-D717796D445F',
    'RCS': 'E91298EB-BC75-4C35-9F62-8FADC3564235',
}

def get_best_service(phone_number):
    """Get the last successful service type for a contact."""
    phone_clean = re.sub(r'[^\d]', '', phone_number)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = '''
    SELECT m.service FROM message m
    JOIN handle h ON m.handle_id = h.ROWID
    WHERE h.id LIKE ? AND m.is_from_me = 1 AND m.is_delivered = 1 AND m.error = 0
    ORDER BY m.date DESC LIMIT 1
    '''
    
    cursor.execute(query, (f'%{phone_clean}%',))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0] in SERVICE_IDS:
        return row[0], SERVICE_IDS[row[0]]
    return 'iMessage', SERVICE_IDS['iMessage']

def get_chat_guid(chat_id):
    """Get the GUID for a chat by its ROWID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT guid, chat_identifier FROM chat WHERE ROWID = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return (row[0], row[1]) if row else (None, None)

def send_to_group_chat(guid, message):
    """Send message to a group chat using its GUID."""
    escaped_msg = message.replace('\\', '\\\\').replace('"', '\\"')
    
    applescript = f'''
    tell application "Messages"
        set targetChat to chat id "{guid}"
        send "{escaped_msg}" to targetChat
    end tell
    '''
    
    result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
    
    if result.returncode == 0:
        return True, "Message sent to group chat"
    return False, f"Failed: {result.stderr}"

def send_to_contact(phone_number, message, service_id=None):
    """Send message to a 1:1 contact with correct service."""
    phone_clean = re.sub(r'[^\d+]', '', phone_number)
    if not phone_clean.startswith('+'):
        if len(phone_clean) == 10:
            phone_clean = '+1' + phone_clean
        elif len(phone_clean) == 11 and phone_clean.startswith('1'):
            phone_clean = '+' + phone_clean
    
    if not service_id:
        svc_type, service_id = get_best_service(phone_number)
        print(f"Using service: {svc_type}")
    
    escaped_msg = message.replace('\\', '\\\\').replace('"', '\\"')
    
    applescript = f'''
    tell application "Messages"
        send "{escaped_msg}" to buddy "{phone_clean}" of service id "{service_id}"
    end tell
    '''
    
    result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
    
    if result.returncode == 0:
        return True, f"Message sent to {phone_clean}"
    return False, f"Failed: {result.stderr}"

def lookup_chat(chat_id):
    """Look up a chat's GUID and identifier."""
    guid, identifier = get_chat_guid(chat_id)
    if guid:
        print(f"Chat ID: {chat_id}")
        print(f"GUID: {guid}")
        print(f"Identifier: {identifier}")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT h.id FROM handle h
            JOIN chat_handle_join chj ON chj.handle_id = h.ROWID
            WHERE chj.chat_id = ?
        ''', (chat_id,))
        participants = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        print(f"Participants: {', '.join(participants)}")
        return True
    print(f"Chat {chat_id} not found")
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 send_message.py <phone_number> \"message\"")
        print("  python3 send_message.py --chat <chat_id> \"message\"")
        print("  python3 send_message.py --guid <chat_guid> \"message\"")
        print("  python3 send_message.py --lookup <chat_id>")
        sys.exit(1)
    
    if sys.argv[1] == "--lookup":
        chat_id = int(sys.argv[2])
        lookup_chat(chat_id)
        sys.exit(0)
    
    if sys.argv[1] == "--chat":
        if len(sys.argv) < 4:
            print("Error: Need chat_id and message")
            sys.exit(1)
        chat_id = int(sys.argv[2])
        message = sys.argv[3]
        
        guid, _ = get_chat_guid(chat_id)
        if not guid:
            print(f"Error: Chat {chat_id} not found")
            sys.exit(1)
        
        success, result = send_to_group_chat(guid, message)
        print(result)
        sys.exit(0 if success else 1)
    
    if sys.argv[1] == "--guid":
        if len(sys.argv) < 4:
            print("Error: Need guid and message")
            sys.exit(1)
        guid = sys.argv[2]
        message = sys.argv[3]
        
        success, result = send_to_group_chat(guid, message)
        print(result)
        sys.exit(0 if success else 1)
    
    if len(sys.argv) < 3:
        print("Error: Need phone_number and message")
        sys.exit(1)
    
    phone = sys.argv[1]
    message = sys.argv[2]
    
    success, result = send_to_contact(phone, message)
    print(result)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
