#!/usr/bin/env python3
"""
iMessage Archiver - Archive conversations to Apple Notes with inline media

Usage:
    python3 archive_to_notes.py PHONE_NUMBER [--days N] [--since YYYY-MM-DD] [--title "Custom Title"]
    
Examples:
    python3 archive_to_notes.py +12242308079 --days 3
    python3 archive_to_notes.py 3129143889 --since 2025-11-22 --title "Mike Convo"
"""

import sqlite3
import subprocess
import os
import sys
import re
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

# chat.db is live, WAL-mode, and continuously written by Messages + iCloud.
# Open it read-only AND immutable so reads take no locks and never touch the
# WAL — a plain connection can checkpoint it and disrupt Messages/iCloud sync.
# (Reads only; the archive is written to Apple Notes via AppleScript.)
DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")
TEMP_DIR = os.path.expanduser("~/Desktop")  # Desktop for reliable AppleScript access
MAX_IMAGE_SIZE = 800  # Max dimension for resizing

def normalize_phone(phone: str) -> str:
    """Normalize phone number to digits only."""
    digits = re.sub(r'\D', '', phone)
    return digits[-10:] if len(digits) >= 10 else digits

def get_messages(phone: str, since_date: str, limit: int = 100) -> list:
    """Get messages from chat.db for a phone number since a date."""
    phone_pattern = f"%{normalize_phone(phone)}%"
    
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro&immutable=1", uri=True)
    cursor = conn.cursor()
    
    query = """
    SELECT 
        datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as ts,
        m.is_from_me,
        m.text,
        m.attributedBody,
        m.service,
        m.ROWID as msg_id
    FROM message m
    JOIN handle h ON m.handle_id = h.ROWID
    WHERE h.id LIKE ?
    AND datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') >= ?
    ORDER BY m.date ASC
    LIMIT ?
    """
    
    cursor.execute(query, (phone_pattern, since_date, limit))
    messages = cursor.fetchall()
    conn.close()
    
    return messages

def get_attachments(phone: str, since_date: str) -> list:
    """Get attachments for messages from a phone number since a date."""
    phone_pattern = f"%{normalize_phone(phone)}%"
    
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro&immutable=1", uri=True)
    cursor = conn.cursor()
    
    query = """
    SELECT 
        datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as ts,
        a.filename,
        a.mime_type,
        a.total_bytes,
        m.ROWID as msg_id
    FROM message m
    JOIN handle h ON m.handle_id = h.ROWID
    JOIN message_attachment_join maj ON maj.message_id = m.ROWID
    JOIN attachment a ON maj.attachment_id = a.ROWID
    WHERE h.id LIKE ?
    AND datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') >= ?
    AND a.filename IS NOT NULL
    ORDER BY m.date ASC
    """
    
    cursor.execute(query, (phone_pattern, since_date))
    attachments = cursor.fetchall()
    conn.close()
    
    return attachments

def extract_text_from_blob(blob: bytes) -> str:
    """Extract text from attributedBody blob when text field is NULL."""
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
        for marker in [b"NSDictionary", b"\x00\x00\x00"]:
            pos = blob.find(marker, start)
            if pos != -1 and pos < end:
                end = pos
        text = blob[start:end].decode("utf-8", errors="ignore")
        text = re.sub(r"iI[A-Z0-9>()]*$", "", text).strip()
        # Remove null bytes and control chars
        text = text.replace('\x00', '')
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        return text
    except:
        return None

def prepare_image(src_path: str, index: int) -> str:
    """Resize image and copy to temp directory. Returns new path."""
    if not src_path or not os.path.exists(src_path.replace("~", os.path.expanduser("~"))):
        return None
    
    src_path = src_path.replace("~", os.path.expanduser("~"))
    ext = Path(src_path).suffix.lower()
    
    # Handle HEIC conversion
    if ext == '.heic':
        dest_path = os.path.join(TEMP_DIR, f"archive_img_{index}.png")
        subprocess.run([
            "sips", "-s", "format", "png", "-Z", str(MAX_IMAGE_SIZE),
            src_path, "--out", dest_path
        ], capture_output=True)
    else:
        dest_path = os.path.join(TEMP_DIR, f"archive_img_{index}{ext}")
        subprocess.run([
            "sips", "-Z", str(MAX_IMAGE_SIZE),
            src_path, "--out", dest_path
        ], capture_output=True)
    
    return dest_path if os.path.exists(dest_path) else None

def prepare_pdf(src_path: str, index: int) -> str:
    """Copy PDF to temp directory. Returns new path."""
    if not src_path:
        return None
    src_path = src_path.replace("~", os.path.expanduser("~"))
    if not os.path.exists(src_path):
        return None
    
    dest_path = os.path.join(TEMP_DIR, f"archive_pdf_{index}.pdf")
    subprocess.run(["cp", src_path, dest_path], capture_output=True)
    
    return dest_path if os.path.exists(dest_path) else None

def sanitize_text(text: str) -> str:
    """Remove null bytes and other problematic characters."""
    if not text:
        return ""
    # Remove null bytes and other control characters
    text = text.replace('\x00', '')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    # Escape quotes and backslashes for AppleScript
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    return text

def run_applescript(script: str) -> bool:
    """Run AppleScript and return success status."""
    # Remove any null bytes from the script itself
    script = script.replace('\x00', '')
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def create_note(title: str, initial_body: str) -> bool:
    """Create a new note with initial content."""
    # Sanitize body
    body_escaped = sanitize_text(initial_body)
    
    script = f'''
    tell application "Notes"
        make new note at folder "Notes" with properties {{name:"{title}", body:"{body_escaped}"}}
    end tell
    '''
    result = run_applescript(script)
    # Give Notes time to create the note
    time.sleep(0.5)
    return result

def add_text_to_note(title: str, text: str) -> bool:
    """Append text to existing note."""
    text_escaped = sanitize_text(text)
    
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            set theNote to first note whose name is "{title}"
            set currentBody to body of theNote
            set body of theNote to currentBody & "{text_escaped}"
        end tell
    end tell
    '''
    return run_applescript(script)

def add_attachment_to_note(title: str, file_path: str) -> bool:
    """Add attachment to note with delay for processing."""
    # Verify file exists
    if not os.path.exists(file_path):
        print(f"  ⚠️ File not found: {file_path}")
        return False
    
    # Use absolute path
    abs_path = os.path.abspath(file_path)
    
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            set theNote to first note whose name is "{title}"
            tell theNote
                make new attachment at end of attachments with data (POSIX file "{abs_path}")
            end tell
        end tell
    end tell
    '''
    result = run_applescript(script)
    # Give Notes time to process the attachment
    time.sleep(1.0)
    return result

def format_timestamp(ts: str) -> str:
    """Format timestamp for display."""
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %I:%M %p")
    except:
        return ts

def archive_conversation(phone: str, since_date: str, title: str = None, contact_name: str = None):
    """Main function to archive a conversation to Apple Notes."""
    
    # Get data
    messages = get_messages(phone, since_date)
    attachments = get_attachments(phone, since_date)
    
    if not messages:
        print(f"No messages found for {phone} since {since_date}")
        return False
    
    # Build attachment lookup by message ID
    attachment_map = {}
    for att in attachments:
        ts, filename, mime_type, size, msg_id = att
        if msg_id not in attachment_map:
            attachment_map[msg_id] = []
        attachment_map[msg_id].append({
            'ts': ts,
            'filename': filename,
            'mime_type': mime_type or '',
            'size': size
        })
    
    # Generate title
    if not title:
        name = contact_name or normalize_phone(phone)
        title = f"Messages with {name} - {since_date}"
    
    # Build content and prepare attachments
    prepared_files = []
    img_index = 0
    
    print(f"Processing {len(messages)} messages...")
    
    # Create initial note
    first_msg = messages[0]
    ts, is_from_me, text, blob, service, msg_id = first_msg
    
    if not text and blob:
        text = extract_text_from_blob(blob)
    
    sender = "Me" if is_from_me else (contact_name or "Them")
    initial_body = f"<h1>{title}</h1>"
    initial_body += f"<p><b>{format_timestamp(ts)} - {sender}:</b> {text or '[media]'}</p>"
    
    # Check for attachment on first message
    if msg_id in attachment_map:
        att = attachment_map[msg_id][0]
        if 'image' in att['mime_type']:
            prep_path = prepare_image(att['filename'], img_index)
            if prep_path:
                initial_body += "<p>⬇️</p>"
                prepared_files.append(('image', prep_path, msg_id))
                img_index += 1
        elif 'pdf' in att['mime_type']:
            prep_path = prepare_pdf(att['filename'], img_index)
            if prep_path:
                initial_body += "<p>📄 PDF attached ⬇️</p>"
                prepared_files.append(('pdf', prep_path, msg_id))
                img_index += 1
    
    print(f"Creating note: {title}")
    if not create_note(title, initial_body):
        print("Failed to create note")
        return False
    
    # Add first attachment if present
    if prepared_files:
        file_type, file_path, _ = prepared_files[0]
        print(f"Adding attachment: {os.path.basename(file_path)}")
        add_attachment_to_note(title, file_path)
    
    # Process remaining messages
    for i, msg in enumerate(messages[1:], 1):
        ts, is_from_me, text, blob, service, msg_id = msg
        
        if not text and blob:
            text = extract_text_from_blob(blob)
        
        sender = "Me" if is_from_me else (contact_name or "Them")
        
        # Build message HTML
        msg_html = f"<p><b>{format_timestamp(ts)} - {sender}:</b> {text or '[media]'}</p>"
        
        # Check for attachments
        has_attachment = False
        if msg_id in attachment_map:
            for att in attachment_map[msg_id]:
                if 'image' in att['mime_type']:
                    prep_path = prepare_image(att['filename'], img_index)
                    if prep_path:
                        msg_html += "<p>⬇️</p>"
                        prepared_files.append(('image', prep_path, msg_id))
                        has_attachment = True
                        img_index += 1
                elif 'pdf' in att['mime_type']:
                    prep_path = prepare_pdf(att['filename'], img_index)
                    if prep_path:
                        msg_html += "<p>📄 PDF attached ⬇️</p>"
                        prepared_files.append(('pdf', prep_path, msg_id))
                        has_attachment = True
                        img_index += 1
        
        # Add text to note
        add_text_to_note(title, msg_html)
        
        # Add attachment if present (sequential pattern!)
        if has_attachment:
            # Get the most recently prepared file
            file_type, file_path, _ = prepared_files[-1]
            print(f"Adding attachment: {os.path.basename(file_path)}")
            add_attachment_to_note(title, file_path)
    
    print(f"\n✅ Archived {len(messages)} messages with {len(prepared_files)} attachments to '{title}'")
    return True

def main():
    parser = argparse.ArgumentParser(description='Archive iMessage conversations to Apple Notes')
    parser.add_argument('phone', help='Phone number to archive')
    parser.add_argument('--days', type=int, default=3, help='Number of days to look back (default: 3)')
    parser.add_argument('--since', help='Start date (YYYY-MM-DD format)')
    parser.add_argument('--title', help='Custom note title')
    parser.add_argument('--name', help='Contact name for display')
    
    args = parser.parse_args()
    
    # Calculate since date
    if args.since:
        since_date = args.since
    else:
        since_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    
    archive_conversation(
        args.phone,
        since_date,
        title=args.title,
        contact_name=args.name
    )

if __name__ == "__main__":
    main()
