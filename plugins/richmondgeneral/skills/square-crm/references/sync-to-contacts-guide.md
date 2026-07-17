# Syncing Square CRM → Apple Contacts

When you discover new information about a customer in Square (like their last name), sync it back to Apple Contacts to keep your address book current.

---

## Quick Start

**When you find a customer's last name in Square:**

```bash
# Update name + add alternate phone
${CLAUDE_PLUGIN_ROOT}/skills/square-crm/scripts/update_contact_simple.sh "+13129143889" "Mike Giba" "+17085970480"

# Just update name
${CLAUDE_PLUGIN_ROOT}/skills/square-crm/scripts/update_contact_simple.sh "+13129143889" "Mike Giba"
```

That's it! Your Apple Contacts will be updated instantly.

---

## The 4-System Sync Pattern

When you discover customer info, it cascades through all systems:

```
Square CRM → Apple Contacts → contacts.md → SKILL.md
   (1)          (2)              (3)          (4)
```

### Step 1: Square CRM (discovery)
```
Mike (Richmond) has 2 phones on file
Phone: +13129143889
Alt:   +17085970480
```

### Step 2: Apple Contacts (update)
```bash
./update_contact_simple.sh "+13129143889" "Mike Giba" "+17085970480"
```

Result:
- Name: "Mike" → "Mike Giba"
- Phone added: +17085970480 (other)

### Step 3: contacts.md (reference)

Manually add to your contacts reference file:

```markdown
### Mike Giba (Richmond)
- **Phone**: +13129143889
- **Alt**: +17085970480
- **Service**: RCS
- **Context**: Store operations, flea market, food truck
- **Note**: Found full name + alt phone via Square CRM
```

### Step 4: SKILL.md (documentation)

Update the Richmond General Customers section in the contacts-manager SKILL.md to reflect the change.

---

## Using the Script

### Arguments

```
./update_contact_simple.sh <primary_phone> [full_name] [alternate_phone]

<primary_phone>   = Phone to match (E.164 format: +1XXXXXXXXXX)
[full_name]       = What to name the contact (optional)
[alternate_phone] = Extra phone to add (optional)
```

### Examples

**Update name only:**
```bash
./update_contact_simple.sh "+13124483219" "Walid Bandar"
```

**Add alternate phone:**
```bash
./update_contact_simple.sh "+14148757568" "414 Contact" "+16085551234"
```

**Both name and phone:**
```bash
./update_contact_simple.sh "+18477747698" "Bill North" "+17085554321"
```

---

## How It Works

The script:
1. Takes your primary phone number from Square
2. Finds the contact in Apple Contacts by matching digits
3. Updates the name (if provided)
4. Adds an alternate phone (if provided)

All using native macOS AppleScript (no external tools needed).

---

## Common Scenarios

### Scenario: You discover a customer's last name

**Square:**
```
Contact: Mike
Note: Mike Giba from North Construction
Phone: +1-312-914-3889
```

**Do this:**
```bash
./update_contact_simple.sh "+13129143889" "Mike Giba"
```

**Result:**
- Apple Contacts: "Mike" → "Mike Giba"
- contacts.md: Add "Mike Giba" reference for next updates
- SKILL.md: Update documentation

---

### Scenario: Customer has multiple phone numbers

**Square note shows:**
```
Main: +13124483219
Work: +17085551234
```

**Do this:**
```bash
# First sync (main number + name)
./update_contact_simple.sh "+13124483219" "Walid Bandar" "+17085551234"
```

**Result:**
- Walid appears in Contacts with both numbers
- Both linked in contacts.md for reference

---

### Scenario: Contact already has the correct name

**Apple Contacts already shows "Steven Elmhurst"**

**Do this:**
```bash
# It's safe to re-run - won't cause duplicates
./update_contact_simple.sh "+12623082827" "Steven Elmhurst"
```

**Result:**
- No change (name already matches)
- Safe idempotency

---

## Workflow Integration

### Daily Sync Workflow

1. **Morning**: Check Square Customers dashboard for staff notes
2. **If you find a last name**: 
   ```bash
   ./update_contact_simple.sh "+1<phone>" "<Full Name>" "[+1<alt>]"
   ```
3. **Update contacts.md** with the new info
4. **Update SKILL.md** if needed
5. **Commit changes** to git

### When Setting Up New Customers

1. Add to Square with phone
2. Run update script with discovered name
3. Add reference to contacts.md
4. Done!

---

## Troubleshooting

### Phone not found in Apple Contacts

**Problem:** Script says contact not found, but you know they're there

**Solution:**
- Check the phone format in Apple Contacts
- Try with different phone format:
  ```bash
  # Try with just digits
  ./update_contact_simple.sh "3129143889" "Mike Giba"
  
  # Try with dashes
  ./update_contact_simple.sh "312-914-3889" "Mike Giba"
  ```

### Name didn't update

**Problem:** Ran the script but the name didn't change

**Possible causes:**
- Contact might be stored differently in Contacts.app
- Try running it again
- Or update manually in Contacts.app

### Want to add more info?

The script currently handles:
- ✅ Name updates
- ✅ Alternate phone numbers
- ❌ Notes (use Contacts.app directly for now)
- ❌ Email (use Contacts.app directly for now)
- ❌ Contact groups (use Contacts.app directly for now)

For other updates, edit the contact directly in Apple Contacts.

---

## Reference: Phone Formats

The script handles all common formats:

| Input | Stored As |
|-------|-----------|
| `+13129143889` | +13129143889 |
| `13129143889` | +13129143889 |
| `3129143889` | +13129143889 |
| `312-914-3889` | +13129143889 |
| `(312) 914-3889` | +13129143889 |

Just use whatever format is easiest!

---

## The Bigger Picture

This script is part of your **manual sync workflow**:

```
Square CRM (truth for transactions)
    ↓ (discover/update)
Apple Contacts (unified contact book)
    ↓ (reference)
contacts.md (relationship context)
    ↓ (documentation)
SKILL.md (skill documentation)
```

When **Phase 3** (bidirectional sync) is implemented, this will be automated. For now, use this simple script to keep everything in sync.

---

## Next Steps

- Run `./update_contact_simple.sh --help` to see options
- Check `${CLAUDE_PLUGIN_ROOT}/skills/square-crm/scripts/` for other tools
- See `manual-sync-sop.md` for full 4-system sync workflow
- See `bidirectional-sync-design.md` for planned automation (Phase 3)
