#!/usr/bin/env python3

"""
Square Cache Wrapper
====================

Simplified Python interface to square-tools cache system.
Provides common operations without requiring direct CLI usage.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any
from pymongo import MongoClient

# Add square-tools to path
sys.path.insert(0, os.path.expanduser('~/Workspace/square-tools/cache-system'))

class SquareCacheWrapper:
    """Wrapper for Square catalog cache operations"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/"):
        """Initialize cache wrapper with MongoDB connection"""
        self.mongo_uri = mongo_uri
        self.client = MongoClient(mongo_uri)
        self.db = self.client['square_cache']
        self.items = self.db['catalog_items']
        self.changes = self.db['change_snapshots']
        self.sync_log = self.db['sync_log']
        
    def get_status(self) -> Dict[str, Any]:
        """Get current cache status"""
        try:
            # Test MongoDB connection
            self.client.admin.command('ismaster')
            mongodb_running = True
        except Exception as e:
            mongodb_running = False
            
        last_sync = self.sync_log.find_one({}, sort=[('timestamp', -1)])
        
        return {
            'mongodb_running': mongodb_running,
            'items_count': self.items.count_documents({}),
            'changes_count': self.changes.count_documents({}),
            'sync_count': self.sync_log.count_documents({}),
            'last_sync': {
                'timestamp': last_sync['timestamp'].isoformat() if last_sync else None,
                'status': 'success' if last_sync and not last_sync.get('error') else 'failed',
                'error': last_sync.get('error') if last_sync else None,
                'items_processed': last_sync.get('items_processed') if last_sync else 0,
                'changes_detected': last_sync.get('changes_detected') if last_sync else 0
            } if last_sync else None
        }
    
    def search_items(self, pattern: str, limit: int = 50) -> List[Dict]:
        """Search cached items by name pattern"""
        regex = {'$regex': pattern, '$options': 'i'}
        results = self.items.find(
            {'item_data.name': regex},
            limit=limit
        )
        
        items = []
        for item in results:
            items.append({
                'id': item['id'],
                'name': item.get('item_data', {}).get('name', 'Unknown'),
                'description': item.get('item_data', {}).get('description'),
                'updated_at': item.get('updated_at'),
                'version': item.get('version'),
                'image_ids': item.get('item_data', {}).get('image_ids', []),
                'has_variations': bool(item.get('item_data', {}).get('variations'))
            })
            
        return items
    
    def get_item(self, item_id: str) -> Optional[Dict]:
        """Get cached item by ID"""
        item = self.items.find_one({'id': item_id})
        if not item:
            return None
            
        # Remove MongoDB _id
        item.pop('_id', None)
        return item
    
    def get_item_history(self, item_id: str) -> List[Dict]:
        """Get complete change history for an item"""
        changes = self.changes.find(
            {'item_id': item_id},
            sort=[('timestamp', -1)]
        )
        
        history = []
        for change in changes:
            history.append({
                'timestamp': change['timestamp'].isoformat(),
                'change_type': change['change_type'],
                'item_name': change.get('item_name'),
                'differences': change.get('differences'),
                'version_before': change.get('square_version_before'),
                'version_after': change.get('square_version_after')
            })
            
        return history
    
    def get_recent_changes(self, since: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get recent changes, optionally filtered by date"""
        query = {}
        
        if since:
            # Parse date string (YYYY-MM-DD)
            since_date = datetime.fromisoformat(since)
            query['timestamp'] = {'$gte': since_date}
            
        changes = self.changes.find(
            query,
            sort=[('timestamp', -1)],
            limit=limit
        )
        
        results = []
        for change in changes:
            results.append({
                'item_id': change['item_id'],
                'item_name': change.get('item_name'),
                'change_type': change['change_type'],
                'timestamp': change['timestamp'].isoformat(),
                'differences': change.get('differences'),
                'version_before': change.get('square_version_before'),
                'version_after': change.get('square_version_after')
            })
            
        return results
    
    def items_with_images(self) -> List[Dict]:
        """Get all items that have images"""
        items = self.items.find({
            'item_data.image_ids': {'$exists': True, '$ne': []}
        })
        
        return [{
            'id': item['id'],
            'name': item.get('item_data', {}).get('name'),
            'image_count': len(item.get('item_data', {}).get('image_ids', []))
        } for item in items]
    
    def items_without_descriptions(self) -> List[Dict]:
        """Get all items missing descriptions"""
        items = self.items.find({
            '$or': [
                {'item_data.description': {'$exists': False}},
                {'item_data.description': ''},
                {'item_data.description': None}
            ]
        })
        
        return [{
            'id': item['id'],
            'name': item.get('item_data', {}).get('name'),
            'updated_at': item.get('updated_at')
        } for item in items]
    
    def sync_cache(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Trigger cache sync via CLI"""
        token = token or os.environ.get('SQUARE_TOKEN')
        if not token:
            raise ValueError("SQUARE_TOKEN not set")
            
        env = os.environ.copy()
        env['SQUARE_TOKEN'] = token
        
        result = subprocess.run(
            [os.path.expanduser('~/Workspace/square-tools/bin/square_cache.sh'), 'sync'],
            env=env,
            capture_output=True,
            text=True
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }


def main():
    """CLI interface for cache wrapper"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Square Cache Wrapper')
    parser.add_argument('command', choices=['status', 'search', 'item', 'history', 'changes', 'sync'])
    parser.add_argument('--pattern', help='Search pattern')
    parser.add_argument('--item-id', help='Item ID')
    parser.add_argument('--since', help='Date filter (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, default=50, help='Result limit')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    
    args = parser.parse_args()
    
    cache = SquareCacheWrapper()
    
    if args.command == 'status':
        result = cache.get_status()
    elif args.command == 'search':
        if not args.pattern:
            print("Error: --pattern required for search")
            sys.exit(1)
        result = cache.search_items(args.pattern, args.limit)
    elif args.command == 'item':
        if not args.item_id:
            print("Error: --item-id required")
            sys.exit(1)
        result = cache.get_item(args.item_id)
    elif args.command == 'history':
        if not args.item_id:
            print("Error: --item-id required")
            sys.exit(1)
        result = cache.get_item_history(args.item_id)
    elif args.command == 'changes':
        result = cache.get_recent_changes(args.since, args.limit)
    elif args.command == 'sync':
        result = cache.sync_cache()
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)
    
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
