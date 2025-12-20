# 4-System Sync Quick Reference

**The Complete Workflow:** iMessage → Apple Contacts → contacts.md → Square CRM

---

## When You Discover Customer Info

### Scenario 1: You find their last name via iMessage
```bash
# Run this to update their Apple Contact
python3 ~/.claude/skills/square-crm/scripts/sync_to_apple_contacts.py +13129143889 --last-name "Giba"
```

### Scenario 2: Square shows alternate phone
```bash
# Add alt phone to their Apple Contact
python3 ~/.claude/skills/square-crm/scripts/sync_to_apple_contacts.py +13129143889 --alt-phone "+17085970480"
```

### Scenario 3: Both name + alternate phone
```bash
# Update Apple Contacts with both
python3 ~/.claude/skills/square-crm/scripts/sync_to_apple_contacts.py +13129143889 \
  --last-name "Giba" \
  --alt-phone "+17085970480"
```

---

## The 4 Steps (Daily Workflow)

| Step | System | Action | Tool |
|------|--------|--------|------|
| 1️⃣ | 📱 Apple Contacts | Update name/phone | `sync_to_apple_contacts.py` |
| 2️⃣ | 📄 contacts.md | Add/update profile | Edit file manually |
| 3️⃣ | 🟦 Square CRM | Sync new data | `parse_contacts.py` |
| 4️⃣ | 📚 SKILL.md | Document changes | Edit SKILL.md |

---

## Available Flags

```bash
# Name updates
--last-name "Giba"
--first-name "Mike"
--company "Giba Co"

# Contact info
--alt-phone "+17085970480"
--note "VIP customer"

# Verification
--check               # Just verify contact exists
--json '{"phone": "+13129143889", "last_name": "Giba"}'  # Batch JSON

# Example: Full update
python3 sync_to_apple_contacts.py +13129143889 \
  --first-name "Mike" \
  --last-name "Giba" \
  --alt-phone "+17085970480" \
  --company "Richmond General" \
  --note "Flea market operations"
```

---

## Common Phone Formats (All Work)

Your script handles these automatically:
- `+13129143889` ✅
- `3129143889` ✅  
- `312-914-3889` ✅
- `(312) 914-3889` ✅
- `+1-312-914-3889` ✅

---

## Step-by-Step Example: "414 Guy"

**Current state:** Contact shows as "414 Contact" with phone +14148757568

**You discover:** His name is "Bob Mitchell" via Square signup notes

**What to do:**

```bash
# 1️⃣ Update Apple Contacts
python3 ~/.claude/skills/square-crm/scripts/sync_to_apple_contacts.py +14148757568 \
  --first-name "Bob" \
  --last-name "Mitchell"

# 2️⃣ Update contacts.md
# Edit imessage-assistant/references/contacts.md:
# Change "414 Contact" section to:
### Bob Mitchell (Trades)
- **Phone**: +14148757568
# ... rest of details

# 3️⃣ Update Square
python3 ~/.claude/skills/square-crm/scripts/parse_contacts.py --phone +14148757568

# 4️⃣ Update SKILL.md
# Change the Richmond General Customers quick lookup table
```

Done! All 4 systems now have "Bob Mitchell" instead of "414 Contact".

---

## Batch Updates (for Future Automation)

Run entire batch from JSON:

```bash
python3 ~/.claude/skills/square-crm/scripts/sync_to_apple_contacts.py --json '{
  "phone": "+14148757568",
  "first_name": "Bob",
  "last_name": "Mitchell",
  "company": "Mitchell Trading",
  "note": "Estate sales + trades"
}'
```

---

## File Locations

| File | Purpose | When to Edit |
|------|---------|--------------|
| `~/.claude/skills/imessage-assistant/references/contacts.md` | Master contact reference | When discovering new customer info |
| `~/.claude/skills/square-crm/SKILL.md` | Square skill docs | When new groups/APIs are available |
| `~/.claude/skills/imessage-assistant/SKILL.md` | iMessage skill docs | When adding new contact style notes |

---

## Verification

After syncing, verify all 4 systems match:

```bash
# 1. Apple Contacts — open on iPhone, verify name + phones
# 2. contacts.md — grep for the phone
grep "+14148757568" ~/.claude/skills/imessage-assistant/references/contacts.md

# 3. Square CRM Dashboard — search by phone
# 4. SKILL.md — check Quick Reference tables
grep "Bob Mitchell" ~/.claude/skills/square-crm/SKILL.md
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Contact not found" | Phone might have different format in Apple Contacts. Try `--check` to verify. |
| Name didn't update | Run the command again. Check if contact exists in Contacts.app |
| alt-phone added duplicate | Script checks for duplicates. Run `--check` to verify |
| Want to test first? | Use `--json` with `--dry-run` flag (when implemented) |

---

## Future: Automation

**Phase 3 (Planned):** These steps will run automatically:
- iMessage mentions name → Apple Contacts updated
- Square signup found → contacts.md inserted
- contacts.md updated → Square synced
- All changes → SKILL.md documented

For now, use this quick reference to keep things synchronized manually!

---

## Pro Tips

1. **Add to shell alias** for faster access:
   ```bash
   alias sync-contact="python3 ~/.claude/skills/square-crm/scripts/sync_to_apple_contacts.py"
   
   # Then use: sync-contact +13129143889 --last-name "Giba"
   ```

2. **Bulk upload after discovery:**
   ```bash
   # Once a week, update Square with all new contacts from contacts.md
   python3 ~/.claude/skills/square-crm/scripts/parse_contacts.py
   ```

3. **Keep SKILL.md tables current:**
   - Update Quick Reference whenever someone's name changes
   - Run validation: `python3 ~/.claude/skills/square-crm/scripts/parse_contacts.py --validate`

---

**Last Updated:** December 19, 2025  
**Status:** ✅ Manual sync fully operational (Phase 3 automation planned)
