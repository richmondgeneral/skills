#!/usr/bin/env python3
"""
Check delivery status of messages sent today.
Useful for auditing failed sends (error=22 means wrong service).

Usage:
  python3 sent_today.py           # Show all sent today
  python3 sent_today.py --failed  # Show only failed/pending
"""

import sqlite3
import os
import sys
from datetime import datetime

# chat.db is live, WAL-mode, and continuously written by Messages + iCloud.
# Open it read-only AND immutable so reads take no locks and never touch the
# WAL — a plain connection can checkpoint it and disrupt Messages/iCloud sync.
DB = os.path.expanduser('~/Library/Messages/chat.db')

def sent_today(failed_only=False):
    conn = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
    c = conn.cursor()
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    timestamp = (today_start - datetime(2001, 1, 1)).total_seconds() * 1e9
    
    c.execute('''
        SELECT datetime(m.date/1000000000+978307200,'unixepoch','localtime') as ts,
               h.id as phone,
               SUBSTR(COALESCE(m.text, '[attachment]'), 1, 60) as preview,
               m.service,
               m.is_delivered,
               m.error
        FROM message m 
        JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.date > ? AND m.is_from_me = 1
        ORDER BY m.date DESC
    ''', (timestamp,))
    
    results = c.fetchall()
    conn.close()
    
    print(f"\n=== Messages SENT Today ({datetime.now().strftime('%Y-%m-%d')}) ===\n")
    
    for ts, phone, preview, service, delivered, error in results:
        if failed_only and delivered and not error:
            continue
            
        time_str = ts[11:16]
        if error:
            status = f'[FAILED err={error}]'
        elif delivered:
            status = '[DELIVERED]'
        else:
            status = '[PENDING]'
        
        svc = service[:3] if service else '???'
        print(f'{time_str} -> {phone} ({svc}) {status}')
        print(f'       "{preview}"')
        print()

if __name__ == '__main__':
    failed_only = '--failed' in sys.argv
    sent_today(failed_only)
