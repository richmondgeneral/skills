#!/usr/bin/env python3
"""
iMessage/RCS/SMS conversation reader with full sent+received history.
Bypasses MCP tool limitation (incoming only).

Usage: 
  python3 get_imessage_convo.py <phone> [limit]      # 1:1 conversation
  python3 get_imessage_convo.py --chat <id> [limit]  # Group chat
  python3 get_imessage_convo.py --service <phone>    # Get best service
  python3 get_imessage_convo.py --groups             # List group chats
  python3 get_imessage_convo.py --today              # Today's messages summary
  python3 get_imessage_convo.py --check-range        # Check database date range
"""

import sqlite3, os, sys, re
from datetime import datetime, timedelta

DB = os.path.expanduser('~/Library/Messages/chat.db')

SERVICE_IDS = {
    'iMessage': '33900AA6-BFB5-49A8-B34A-2A8F783BE2F4',
    'SMS': 'E0595A22-53AF-4ECC-93BE-D717796D445F',
    'RCS': 'E91298EB-BC75-4C35-9F62-8FADC3564235',
}

def get_database_range():
    """Get the date range of messages in the local database."""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Get oldest message
    c.execute('''SELECT datetime(MIN(date)/1000000000+978307200,'unixepoch','localtime') as oldest
                 FROM message''')
    oldest = c.fetchone()[0]
    
    # Get newest message
    c.execute('''SELECT datetime(MAX(date)/1000000000+978307200,'unixepoch','localtime') as newest
                 FROM message''')
    newest = c.fetchone()[0]
    
    # Get total message count
    c.execute('SELECT COUNT(*) FROM message')
    total = c.fetchone()[0]
    
    conn.close()
    return oldest, newest, total

def check_database_coverage(show_warning=True):
    """Check if database has full history or just recent messages."""
    oldest, newest, total = get_database_range()
    
    if not oldest or not newest:
        return None, None, None
    
    oldest_dt = datetime.strptime(oldest, '%Y-%m-%d %H:%M:%S')
    newest_dt = datetime.strptime(newest, '%Y-%m-%d %H:%M:%S')
    days_coverage = (newest_dt - oldest_dt).days
    
    # If database only goes back less than 6 months, likely using iCloud Messages
    limited_history = days_coverage < 180
    
    if show_warning and limited_history:
        print(f"\n⚠️  DATABASE LIMITATION WARNING")
        print(f"\nLocal database only contains messages from:")
        print(f"  Oldest: {oldest}")
        print(f"  Newest: {newest}")
        print(f"  Coverage: {days_coverage} days ({total:,} messages)")
        print(f"\nIf you have 'Messages in iCloud' enabled, only recent messages")
        print(f"are stored locally. To access full history:")
        print(f"  1. System Settings > Apple ID > iCloud")
        print(f"  2. Turn OFF 'Messages' sync")
        print(f"  3. Wait 10-30 minutes for full download")
        print(f"  4. Run your query")
        print(f"  5. Turn Messages sync back ON")
        print(f"\nMore info: Run with --check-range flag\n")
    
    return oldest, newest, limited_history

def extract_text(blob):
    if not blob: return None
    try:
        idx = blob.find(b"NSString")
        if idx == -1: return None
        plus_idx = blob.find(b"+", idx)
        if plus_idx == -1: return None
        start = plus_idx + 2
        end = len(blob)
        for m in [b"NSDictionary", b"\x00\x00\x00"]:
            p = blob.find(m, start)
            if p != -1 and p < end: end = p
        text = blob[start:end].decode("utf-8", errors="ignore")
        return re.sub(r"iI[A-Z0-9>()]*$", "", text).strip()
    except: return None

def get_service(phone):
    """Get best service type for a phone number."""
    phone = re.sub(r'[^\d]', '', phone)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''SELECT m.service FROM message m JOIN handle h ON m.handle_id=h.ROWID
                 WHERE h.id LIKE ? AND m.is_from_me=1 AND m.is_delivered=1 AND m.error=0
                 ORDER BY m.date DESC LIMIT 1''', (f'%{phone}%',))
    r = c.fetchone()
    conn.close()
    if r and r[0] in SERVICE_IDS:
        return r[0], SERVICE_IDS[r[0]]
    return None, None

def list_groups():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''SELECT c.ROWID, c.display_name, COUNT(chj.handle_id)
                 FROM chat c JOIN chat_handle_join chj ON chj.chat_id=c.ROWID
                 GROUP BY c.ROWID HAVING COUNT(chj.handle_id)>1
                 ORDER BY c.ROWID DESC LIMIT 20''')
    print("\nGroup chats:\n")
    for chat_id, name, n in c.fetchall():
        c.execute('''SELECT h.id FROM handle h 
                     JOIN chat_handle_join chj ON chj.handle_id=h.ROWID
                     WHERE chj.chat_id=?''', (chat_id,))
        parts = [r[0] for r in c.fetchall()]
        print(f"  ID {chat_id}: {name or 'Unnamed'} ({', '.join(parts)})")
    conn.close()

def get_group(chat_id, limit=25):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''SELECT datetime(m.date/1000000000+978307200,'unixepoch','localtime'),
                        m.is_from_me, h.id, m.text, m.attributedBody, m.cache_has_attachments
                 FROM message m JOIN chat_message_join cmj ON cmj.message_id=m.ROWID
                 LEFT JOIN handle h ON m.handle_id=h.ROWID
                 WHERE cmj.chat_id=? ORDER BY m.date DESC LIMIT ?''', (chat_id, limit))
    msgs = []
    for ts, me, sender, txt, blob, att in c.fetchall():
        content = txt or extract_text(blob) or ("[📎]" if att else "[empty]")
        name = "ME" if me else (sender or "?")
        msgs.append((ts, name, content, att))
    conn.close()
    msgs.reverse()
    print(f"\n=== Group Chat {chat_id} ===")
    for ts, name, content, att in msgs:
        mark = " 📎" if att else ""
        print(f"[{ts}] {name}{mark}:  {content}")

def get_convo(phone, limit=25):
    phone = re.sub(r'[^\d]', '', phone)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''SELECT datetime(m.date/1000000000+978307200,'unixepoch','localtime'),
                        m.is_from_me, m.text, m.attributedBody, m.cache_has_attachments,
                        m.service, m.is_delivered, m.error
                 FROM message m JOIN handle h ON m.handle_id=h.ROWID
                 WHERE h.id LIKE ? ORDER BY m.date DESC LIMIT ?''', (f'%{phone}%', limit))
    msgs = []
    for ts, me, txt, blob, att, svc, dlv, err in c.fetchall():
        content = txt or extract_text(blob) or ("[📎]" if att else "[empty]")
        if me:
            status = "FAIL" if err else ("✓" if dlv else "?")
        else:
            status = ""
        msgs.append((ts, "ME" if me else "THEM", content, svc, status, att))
    conn.close()
    msgs.reverse()
    print(f"\n=== {phone} ===")
    for ts, who, content, svc, status, att in msgs:
        mark = " 📎" if att else ""
        st = f" [{status}]" if status else ""
        print(f"[{ts}] {who} ({svc[:3]}){mark}{st}:  {content}")

def today_summary():
    """Get summary of today's messages by contact."""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute('''SELECT h.id, 
                        datetime(MAX(m.date)/1000000000+978307200,'unixepoch','localtime') as last_msg,
                        COUNT(*) as msg_count,
                        SUM(CASE WHEN m.is_from_me=0 THEN 1 ELSE 0 END) as incoming,
                        SUM(CASE WHEN m.is_from_me=1 THEN 1 ELSE 0 END) as outgoing
                 FROM message m JOIN handle h ON m.handle_id=h.ROWID
                 WHERE datetime(m.date/1000000000+978307200,'unixepoch','localtime') >= ?
                 GROUP BY h.id ORDER BY MAX(m.date) DESC''', (f'{today} 00:00:00',))
    
    print(f"\n=== Messages for {today} ===\n")
    print(f"{'Phone/ID':<20} {'Last Msg':<12} {'In':>4} {'Out':>4} {'Tot':>4}")
    print("-" * 50)
    for phone, last, total, inc, out in c.fetchall():
        time_part = last.split()[1][:5] if ' ' in last else last
        print(f"{phone:<20} {time_part:<12} {inc or 0:>4} {out or 0:>4} {total:>4}")
    conn.close()

def check_range_command():
    """Display detailed database range information."""
    oldest, newest, total = get_database_range()
    
    if not oldest or not newest:
        print("No messages found in database.")
        return
    
    oldest_dt = datetime.strptime(oldest, '%Y-%m-%d %H:%M:%S')
    newest_dt = datetime.strptime(newest, '%Y-%m-%d %H:%M:%S')
    days_coverage = (newest_dt - oldest_dt).days
    years = days_coverage / 365.25
    
    print("\n=== Local Messages Database Range ===")
    print(f"\nOldest message: {oldest}")
    print(f"Newest message: {newest}")
    print(f"Total messages: {total:,}")
    print(f"Coverage: {days_coverage} days ({years:.1f} years)")
    
    if days_coverage < 180:
        print("\n⚠️  LIMITED HISTORY DETECTED")
        print("\nYour database only contains ~6 months or less of messages.")
        print("This typically means 'Messages in iCloud' is enabled and")
        print("older messages are stored in iCloud but not synced locally.")
        print("\n📋 TO ACCESS FULL HISTORY:")
        print("\n1. Check iCloud Messages status:")
        print("   System Settings > Apple ID > iCloud > Messages")
        print("\n2. To download all messages:")
        print("   - Turn OFF 'Messages' in iCloud settings")
        print("   - Wait 10-30 minutes (or longer for years of messages)")
        print("   - Messages will download to local database")
        print("   - Run your queries")
        print("   - Turn Messages sync back ON when done")
        print("\n⚠️  Note: This is a manual process - no automation available.")
        print("   Apple doesn't provide API access to force iCloud message sync.")
    else:
        print("\n✅ FULL HISTORY AVAILABLE")
        print(f"\nYour database contains {years:.1f} years of messages.")
        print("You likely have iCloud Messages disabled or all messages")
        print("have been downloaded locally.")
    print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    if sys.argv[1] == "--check-range":
        check_range_command()
    elif sys.argv[1] == "--service":
        svc, sid = get_service(sys.argv[2])
        print(f"Service: {svc}\nID: {sid}" if svc else "No successful sends found")
    elif sys.argv[1] == "--groups":
        list_groups()
    elif sys.argv[1] == "--chat":
        # Check database range and show warning if limited
        check_database_coverage(show_warning=True)
        get_group(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 25)
    elif sys.argv[1] == "--today":
        today_summary()
    else:
        # Check database range and show warning if limited
        check_database_coverage(show_warning=True)
        get_convo(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 25)
