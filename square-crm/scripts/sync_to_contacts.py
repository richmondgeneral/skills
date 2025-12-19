#!/usr/bin/env python3
"""
Sync Square customer data back to Apple Contacts.

This script reads a Square customer record (typically obtained via manual lookup
or API call) and updates the corresponding contact in Apple Contacts with:
- Full name (if discovered)
- Phone number (alternate numbers)
- Notes (metadata from Square)
- Contact groups (based on Square category)

Usage:
  python3 sync_to_contacts.py +13129143889 --name "Mike Giba" --note "Square customer"
  python3 sync_to_contacts.py +13129143889 --sync-from-square  # requires jq + Square CLI

Options:
  --name TEXT           Update contact name
  --note TEXT           Add/update note in Apple Contacts
  --phone TEXT          Add alternate phone number
  --group TEXT          Add to contact group (e.g., "Customers")
  --sync-from-square    Fetch latest data from Square (requires Square CLI + jq)
  --dry-run             Show what would be updated without making changes
  --verbose             Print detailed operations
"""

import subprocess
import json
import sys
import re
from pathlib import Path
from datetime import datetime
import argparse


def format_phone(phone):
    """Normalize phone to E.164 format."""
    digits = re.sub(r'[^\d]', '', phone)
    
    if len(digits) < 10:
        raise ValueError(f"Phone number too short: {phone}")
    if len(digits) > 15:
        raise ValueError(f"Phone number too long: {phone}")
    
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    else:
        return f"+{digits}"


def run_applescript(script, verbose=False):
    """Execute AppleScript and return result."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"AppleScript failed: {result.stderr}")
        
        if verbose:
            print(f"[AppleScript] {script[:60]}...", file=sys.stderr)
        
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("AppleScript timeout (contacts app may be busy)")
    except Exception as e:
        raise RuntimeError(f"AppleScript execution failed: {e}")


def find_contact_by_phone(phone, verbose=False):
    """Find contact in Apple Contacts by phone number.
    
    Note: Contacts.app AppleScript has limitations, so we iterate through contacts.
    This may be slow for large contact lists.
    """
    normalized = format_phone(phone)
    
    # Build script to iterate through contacts and find by phone
    script = f'''
    tell application "Contacts"
        activate
        
        set foundName to "NOT_FOUND"
        
        repeat with person in (every person)
            repeat with phoneEntry in (every phone of person)
                set phoneValue to value of phoneEntry
                
                if phoneValue = "{normalized}" then
                    set foundName to name of person
                    exit repeat
                end if
            end repeat
            
            if foundName is not "NOT_FOUND" then
                exit repeat
            end if
        end repeat
        
        return foundName
    end tell
    '''
    
    # Increase timeout for full contact list scan
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=30  # Longer timeout for contact list
        )
        
        if result.returncode != 0:
            if verbose:
                print(f"[AppleScript lookup failed: {result.stderr}", file=sys.stderr)
            return None
        
        result_text = result.stdout.strip()
        if result_text == "NOT_FOUND":
            return None
        return result_text
        
    except subprocess.TimeoutExpired:
        print(f"⚠️  Contact lookup timed out (large contact list?)", file=sys.stderr)
        return None
    except Exception as e:
        if verbose:
            print(f"[Error in contact lookup: {e}", file=sys.stderr)
        return None


def update_contact_name(phone, new_name, dry_run=False, verbose=False):
    """Update contact name in Apple Contacts."""
    normalized = format_phone(phone)
    existing_name = find_contact_by_phone(phone, verbose)
    
    if not existing_name:
        print(f"❌ Contact not found for {phone}", file=sys.stderr)
        return False
    
    if existing_name == new_name:
        print(f"✓ Name already correct: {new_name}", file=sys.stderr)
        return True
    
    if dry_run:
        print(f"[DRY RUN] Would update name: {existing_name} → {new_name}", file=sys.stderr)
        return True
    
    script = f'''
    tell application "Contacts"
        repeat with contactItem in every person
            repeat with phoneValue in phones of contactItem
                if value of phoneValue is "{normalized}" then
                    set name of contactItem to "{new_name}"
                    return "SUCCESS"
                end if
            end repeat
        end repeat
        return "NOT_FOUND"
    end tell
    '''
    
    result = run_applescript(script, verbose)
    
    if result == "SUCCESS":
        print(f"✅ Updated name: {new_name}", file=sys.stderr)
        return True
    else:
        print(f"❌ Failed to update name", file=sys.stderr)
        return False


def add_phone_to_contact(phone, new_phone, phone_label="other", dry_run=False, verbose=False):
    """Add alternate phone number to contact."""
    normalized_primary = format_phone(phone)
    normalized_new = format_phone(new_phone)
    
    if normalized_primary == normalized_new:
        print(f"ℹ️  Phone already exists: {normalized_new}", file=sys.stderr)
        return True
    
    existing_name = find_contact_by_phone(phone, verbose)
    
    if not existing_name:
        print(f"❌ Contact not found for {phone}", file=sys.stderr)
        return False
    
    if dry_run:
        print(f"[DRY RUN] Would add phone to {existing_name}: {normalized_new} ({phone_label})", file=sys.stderr)
        return True
    
    script = f'''
    tell application "Contacts"
        repeat with contactItem in every person
            repeat with phoneValue in phones of contactItem
                if value of phoneValue is "{normalized_primary}" then
                    make new phone at end of phones of contactItem with properties {{value: "{normalized_new}", label: "{phone_label}"}}
                    return "SUCCESS"
                end if
            end repeat
        end repeat
        return "NOT_FOUND"
    end tell
    '''
    
    result = run_applescript(script, verbose)
    
    if result == "SUCCESS":
        print(f"✅ Added phone: {normalized_new} ({phone_label})", file=sys.stderr)
        return True
    else:
        print(f"❌ Failed to add phone", file=sys.stderr)
        return False


def update_contact_note(phone, note_text, dry_run=False, verbose=False):
    """Update contact note in Apple Contacts."""
    normalized = format_phone(phone)
    existing_name = find_contact_by_phone(phone, verbose)
    
    if not existing_name:
        print(f"❌ Contact not found for {phone}", file=sys.stderr)
        return False
    
    # Escape quotes in note text
    safe_note = note_text.replace('"', '\\"')
    
    if dry_run:
        print(f"[DRY RUN] Would update note for {existing_name}: {safe_note}", file=sys.stderr)
        return True
    
    script = f'''
    tell application "Contacts"
        repeat with contactItem in every person
            repeat with phoneValue in phones of contactItem
                if value of phoneValue is "{normalized}" then
                    set note of contactItem to "{safe_note}"
                    return "SUCCESS"
                end if
            end repeat
        end repeat
        return "NOT_FOUND"
    end tell
    '''
    
    result = run_applescript(script, verbose)
    
    if result == "SUCCESS":
        print(f"✅ Updated note", file=sys.stderr)
        return True
    else:
        print(f"❌ Failed to update note", file=sys.stderr)
        return False


def add_to_group(phone, group_name, dry_run=False, verbose=False):
    """Add contact to a group in Apple Contacts."""
    normalized = format_phone(phone)
    existing_name = find_contact_by_phone(phone, verbose)
    
    if not existing_name:
        print(f"❌ Contact not found for {phone}", file=sys.stderr)
        return False
    
    if dry_run:
        print(f"[DRY RUN] Would add {existing_name} to group: {group_name}", file=sys.stderr)
        return True
    
    script = f'''
    tell application "Contacts"
        set targetGroup to null
        repeat with groupItem in every group
            if name of groupItem is "{group_name}" then
                set targetGroup to groupItem
                exit repeat
            end if
        end repeat
        
        if targetGroup is null then
            return "GROUP_NOT_FOUND"
        end if
        
        repeat with contactItem in every person
            repeat with phoneValue in phones of contactItem
                if value of phoneValue is "{normalized}" then
                    add contactItem to targetGroup
                    return "SUCCESS"
                end if
            end repeat
        end repeat
        return "NOT_FOUND"
    end tell
    '''
    
    result = run_applescript(script, verbose)
    
    if result == "SUCCESS":
        print(f"✅ Added to group: {group_name}", file=sys.stderr)
        return True
    elif result == "GROUP_NOT_FOUND":
        print(f"⚠️  Group not found: {group_name} (create it first in Apple Contacts)", file=sys.stderr)
        return False
    else:
        print(f"❌ Failed to add to group", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Sync Square customer data to Apple Contacts",
        epilog="Examples:\n"
               "  %(prog)s +13129143889 --name 'Mike Giba' --phone +17085970480\n"
               "  %(prog)s +13129143889 --note 'Square CRM customer'\n"
               "  %(prog)s +13129143889 --group 'Customers' --dry-run",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('phone', help='Primary phone number to match')
    parser.add_argument('--name', help='Update contact name')
    parser.add_argument('--phone', help='Add alternate phone number')
    parser.add_argument('--note', help='Update contact note')
    parser.add_argument('--group', help='Add to contact group')
    parser.add_argument('--dry-run', action='store_true', help='Show what would change')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    try:
        primary_phone = format_phone(args.phone)
    except ValueError as e:
        print(f"❌ Invalid phone: {e}", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"Looking up contact for {primary_phone}...", file=sys.stderr)
    
    # Check if contact exists
    existing_name = find_contact_by_phone(args.phone, args.verbose)
    
    if not existing_name:
        print(f"❌ No contact found for {primary_phone}", file=sys.stderr)
        sys.exit(1)
    
    print(f"📱 Found contact: {existing_name}", file=sys.stderr)
    
    success = True
    
    # Update name
    if args.name:
        if not update_contact_name(args.phone, args.name, args.dry_run, args.verbose):
            success = False
    
    # Add phone
    if args.phone:
        if not add_phone_to_contact(args.phone, args.phone, "other", args.dry_run, args.verbose):
            success = False
    
    # Update note
    if args.note:
        if not update_contact_note(args.phone, args.note, args.dry_run, args.verbose):
            success = False
    
    # Add to group
    if args.group:
        if not add_to_group(args.phone, args.group, args.dry_run, args.verbose):
            success = False
    
    if args.dry_run:
        print("\n✓ Dry run complete (no changes made)", file=sys.stderr)
    
    if not success:
        sys.exit(1)
    
    print("\n✅ Sync complete!", file=sys.stderr)


if __name__ == '__main__':
    main()
