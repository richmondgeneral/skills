#!/usr/bin/env python3
"""
iMessage/RCS/SMS conversation reader with full sent+received history.
Bypasses MCP tool limitation (incoming only).

Usage: 
  python3 get_imessage_convo.py <phone> [limit]      # 1:1 conversation
  python3 get_imessage_convo.py --chat <id> [limit]  # Group chat
  python3 get_imessage_convo.py --service <phone>    # Get best service
  python3 get_imessage_convo.py --groups             # List group chats
"""

import sqlite3, os, sys, re

DB = os.path.expanduser('~/Library/Messages/chat.db')

SERVICE_IDS = {
    'iMessage': '33900AA6-BFB5-49A8-B34A-2A8F783BE2F4',
    'SMS': 'E0595A22-53AF-4ECC-93BE-D717796D445F',
    'RCS': 'E91298EB-BC75-4C35-9F62-8FADC3564235',
}

CONTACTS = {
    '+12242308079': 'FREEMAN',
    '+18472871148': 'DAWN',
    '+16305444884': 'JENNIFER',
}

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
    phone = re.sub(r'[^\d]', '', phone)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''SELECT service FROM message m JOIN handle h ON m.handle_id=h.ROWID
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
        parts = [CONTACTS.get(r[0], r[0]) for r in c.fetchall()]
        print(f"  ID {chat_id}: {name or 'Unnamed'} ({', '.join(parts)})\n")
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
        name = "ME" if me else CONTACTS.get(sender, sender or "?")
        msgs.append((ts, name, content, att))
    conn.close()
    msgs.reverse()
    print(f"\n=== Group Chat {chat_id} ===\n")
    for ts, name, content, att in msgs:
        mark = " 📎" if att else ""
        print(f"[{ts}] {name}{mark}:\n  {content}\n")

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
    print(f"\n=== {phone} ===\n")
    for ts, who, content, svc, status, att in msgs:
        mark = " 📎" if att else ""
        st = f" [{status}]" if status else ""
        print(f"[{ts}] {who} ({svc[:3]}){mark}{st}:\n  {content}\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "--service":
        svc, sid = get_service(sys.argv[2])
        print(f"Service: {svc}\nID: {sid}" if svc else "No successful sends found")
    elif sys.argv[1] == "--groups":
        list_groups()
    elif sys.argv[1] == "--chat":
        get_group(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 25)
    else:
        get_convo(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 25)
