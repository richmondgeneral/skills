#!/usr/bin/env python3

"""
MongoDB Query Helper
===================

Pre-built MongoDB query templates for common Square cache operations.
Returns mongosh command strings for safe execution.
"""

from typing import Optional


class QueryHelper:
    """Helper class for building MongoDB queries"""
    
    @staticmethod
    def _sanitize(value: str) -> str:
        """Escape single quotes for JS strings"""
        return value.replace("'", "\\'") if value else ""
    
    @staticmethod
    def items_with_images() -> str:
        """Get all items that have images attached"""
        return r"""mongosh square_cache --eval "db.catalog_items.find({'item_data.image_ids': {\$exists: true, \$ne: []}}).pretty()" """
    
    @staticmethod
    def items_without_images() -> str:
        """Get all items missing images"""
        return r"""mongosh square_cache --eval "db.catalog_items.find({\$or: [{'item_data.image_ids': {\$exists: false}}, {'item_data.image_ids': []}]}).pretty()" """
    
    @staticmethod
    def items_without_descriptions() -> str:
        """Get items missing descriptions"""
        return r"""mongosh square_cache --eval "db.catalog_items.find({\$or: [{'item_data.description': {\$exists: false}}, {'item_data.description': ''}, {'item_data.description': null}]}).pretty()" """
    
    @staticmethod
    def items_by_category(category_id: str) -> str:
        """Get items in a specific category"""
        safe_id = QueryHelper._sanitize(category_id)
        return rf"""mongosh square_cache --eval "db.catalog_items.find({{'item_data.categories': {{\\$elemMatch: {{id: '{safe_id}'}}}}}}).pretty()" """
    
    @staticmethod
    def changes_by_date_range(start_date: str, end_date: str) -> str:
        """Get changes between two dates (YYYY-MM-DD format)"""
        s = QueryHelper._sanitize(start_date)
        e = QueryHelper._sanitize(end_date)
        return rf"""mongosh square_cache --eval "db.change_snapshots.find({{timestamp: {{\$gte: new Date('{s}'), \$lte: new Date('{e}')}}}}).sort({{timestamp: -1}}).pretty()" """
    
    @staticmethod
    def changes_by_item(item_id: str) -> str:
        """Get all changes for a specific item"""
        safe_id = QueryHelper._sanitize(item_id)
        return rf"""mongosh square_cache --eval "db.change_snapshots.find({{item_id: '{safe_id}'}}).sort({{timestamp: -1}}).pretty()" """
    
    @staticmethod
    def recent_changes(limit: int = 50) -> str:
        """Get most recent changes"""
        return rf"""mongosh square_cache --eval "db.change_snapshots.find({{}}).sort({{timestamp: -1}}).limit({limit}).pretty()" """
    
    @staticmethod
    def sync_errors() -> str:
        """Get recent sync errors"""
        return r"""mongosh square_cache --eval "db.sync_log.find({error: {\$exists: true}}).sort({timestamp: -1}).limit(10).pretty()" """
    
    @staticmethod
    def last_sync() -> str:
        """Get last sync operation details"""
        return r"""mongosh square_cache --eval "db.sync_log.findOne({}, {sort: {timestamp: -1}})" """
    
    @staticmethod
    def cache_stats() -> str:
        """Get overall cache statistics"""
        return r"""mongosh square_cache --eval "printjson({items: db.catalog_items.countDocuments(), changes: db.change_snapshots.countDocuments(), syncs: db.sync_log.countDocuments(), last_sync: db.sync_log.findOne({}, {sort: {timestamp: -1}})?.timestamp})" """
    
    @staticmethod
    def changes_by_type() -> str:
        """Count changes grouped by type (create/update/delete)"""
        return r"""mongosh square_cache --eval "db.change_snapshots.aggregate([{\\$group: {_id: '\\$change_type', count: {\\$sum: 1}}}])" """
    
    @staticmethod
    def items_updated_recently(days: int = 7) -> str:
        """Get items updated in the last N days"""
        return rf"""mongosh square_cache --eval "db.catalog_items.find({{updated_at: {{\$gte: new Date(Date.now() - {days}*24*60*60*1000)}}}}).sort({{updated_at: -1}}).pretty()" """
    
    @staticmethod
    def search_by_name(pattern: str) -> str:
        """Search items by name pattern (case-insensitive)"""
        safe_pat = QueryHelper._sanitize(pattern)
        return rf"""mongosh square_cache --eval "db.catalog_items.find({{'item_data.name': {{\$regex: '{safe_pat}', \$options: 'i'}}}}).pretty()" """
    
    @staticmethod
    def get_item(item_id: str) -> str:
        """Get specific item by ID"""
        safe_id = QueryHelper._sanitize(item_id)
        return rf"""mongosh square_cache --eval "db.catalog_items.findOne({{id: '{safe_id}'}})" """
    
    @staticmethod
    def items_with_variations() -> str:
        """Get items that have variations"""
        return r"""mongosh square_cache --eval "db.catalog_items.find({'item_data.variations': {\$exists: true, \$ne: []}}).pretty()" """
    
    @staticmethod
    def export_items_json(output_file: str = "items.json") -> str:
        """Export all items to JSON file"""
        return f"""mongoexport --db=square_cache --collection=catalog_items --out={output_file} --jsonArray"""
    
    @staticmethod
    def export_changes_json(output_file: str = "changes.json") -> str:
        """Export all changes to JSON file"""
        return f"""mongoexport --db=square_cache --collection=change_snapshots --out={output_file} --jsonArray"""
    
    @staticmethod
    def count_items_by_field(field: str) -> str:
        """Count items grouped by a specific field value"""
        return rf"""mongosh square_cache --eval "db.catalog_items.aggregate([{{\\$group: {{_id: '\\${field}', count: {{\\$sum: 1}}}}}}])" """


def main():
    """CLI interface for query helper"""
    import argparse
    import subprocess
    import sys
    
    helper = QueryHelper()
    
    parser = argparse.ArgumentParser(description='MongoDB Query Helper for Square Cache')
    parser.add_argument('query_type', choices=[
        'items-with-images',
        'items-without-images',
        'items-without-descriptions',
        'items-by-category',
        'changes-by-date',
        'changes-by-item',
        'recent-changes',
        'sync-errors',
        'last-sync',
        'cache-stats',
        'changes-by-type',
        'items-updated-recently',
        'search',
        'get-item',
        'items-with-variations',
        'export-items',
        'export-changes'
    ])
    parser.add_argument('--category-id', help='Category ID for filtering')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--item-id', help='Item ID')
    parser.add_argument('--pattern', help='Search pattern')
    parser.add_argument('--days', type=int, default=7, help='Number of days')
    parser.add_argument('--limit', type=int, default=50, help='Result limit')
    parser.add_argument('--output', help='Output file for exports')
    parser.add_argument('--execute', action='store_true', help='Execute query immediately')
    parser.add_argument('--dry-run', action='store_true', help='Print query without executing')
    
    args = parser.parse_args()
    
    # Build query based on type
    query = None
    
    if args.query_type == 'items-with-images':
        query = helper.items_with_images()
    elif args.query_type == 'items-without-images':
        query = helper.items_without_images()
    elif args.query_type == 'items-without-descriptions':
        query = helper.items_without_descriptions()
    elif args.query_type == 'items-by-category':
        if not args.category_id:
            print("Error: --category-id required")
            sys.exit(1)
        query = helper.items_by_category(args.category_id)
    elif args.query_type == 'changes-by-date':
        if not args.start_date or not args.end_date:
            print("Error: --start-date and --end-date required")
            sys.exit(1)
        query = helper.changes_by_date_range(args.start_date, args.end_date)
    elif args.query_type == 'changes-by-item':
        if not args.item_id:
            print("Error: --item-id required")
            sys.exit(1)
        query = helper.changes_by_item(args.item_id)
    elif args.query_type == 'recent-changes':
        query = helper.recent_changes(args.limit)
    elif args.query_type == 'sync-errors':
        query = helper.sync_errors()
    elif args.query_type == 'last-sync':
        query = helper.last_sync()
    elif args.query_type == 'cache-stats':
        query = helper.cache_stats()
    elif args.query_type == 'changes-by-type':
        query = helper.changes_by_type()
    elif args.query_type == 'items-updated-recently':
        query = helper.items_updated_recently(args.days)
    elif args.query_type == 'search':
        if not args.pattern:
            print("Error: --pattern required")
            sys.exit(1)
        query = helper.search_by_name(args.pattern)
    elif args.query_type == 'get-item':
        if not args.item_id:
            print("Error: --item-id required")
            sys.exit(1)
        query = helper.get_item(args.item_id)
    elif args.query_type == 'items-with-variations':
        query = helper.items_with_variations()
    elif args.query_type == 'export-items':
        output = args.output or 'items.json'
        query = helper.export_items_json(output)
    elif args.query_type == 'export-changes':
        output = args.output or 'changes.json'
        query = helper.export_changes_json(output)
    
    if not query:
        print(f"Error: Unknown query type: {args.query_type}")
        sys.exit(1)
    
    # Print or execute
    if args.dry_run:
        print(f"Query: {query}")
    elif args.execute:
        print(f"Executing: {query}")
        result = subprocess.run(query, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"Error: {result.stderr}", file=sys.stderr)
    else:
        # Default: print query for user to execute
        print(query)


if __name__ == '__main__':
    main()
