# MCP Connector Quick Reference

Last updated: 2024-12-20

## Filesystem MCP (`Filesystem:*`)

**Use for:** Text files on user's Mac

| Tool | Use Case |
|------|----------|
| `read_file` | Read text files |
| `write_file` | Create/overwrite files |
| `list_directory` | Check folder contents |
| `create_directory` | Make new folders |

**Paths:** Absolute paths only: `/Users/scottybe/workspace/square/items/`
**DO NOT USE:** `~` tilde expansion (unreliable across sessions)

**Works:** HTML, CSV, MD, JSON, Python scripts
**Fails:** Binary files from Claude's container

---

## osascript (`Control your Mac:osascript`)

**Use for:** Binary operations, shell commands, git

```applescript
do shell script "source ~/.env && python3 ~/.claude/skills/[skill]/scripts/[script].py"
```

| Operation | Example |
|-----------|---------|
| Background removal | `python3 scripts/remove_background.py input.jpg output.png` |
| QR generation | `python3 -c "import qrcode; ..."` |
| Git operations | `cd ~/.claude/skills && git add . && git commit -m "msg" && git push` |
| Open apps | `tell application "Preview" to open ...` |

**Why:** Scripts on Mac have access to `~/.env` (API keys), binary file I/O, and git.

---

## Square MCP (`Square:*`)

**Use for:** JSON-only API operations

| Tool | Purpose |
|------|---------|
| `get_service_info` | List available methods |
| `get_type_info` | Get request/response schemas |
| `make_api_request` | Execute API calls |

**Works:** Catalog CRUD, payment links, customers, inventory, orders
**Fails:** Image uploads (requires multipart/form-data)

### Image Upload Limitation

Square MCP **cannot upload images**. Options:

1. ✅ **Manual:** Square Dashboard → Catalog → Item → Images
2. ⚠️ **Script:** `square-image-upload` skill (currently 403 - token scope issue)
3. ✅ **Skip:** GitHub Pages flipcard shows image; Square listing works without

---

## square-cache MCP (`square-cache:*`)

**Use for:** Fast catalog lookups (100x faster than API)

| Tool | Purpose |
|------|---------|
| `square_cache_search` | Search by name or SKU |
| `square_cache_get_item` | Get full item details |
| `square_cache_status` | Check cache health |
| `square_cache_changes` | View recent changes |
| `square_cache_sync` | Trigger sync from Square |

**When to use:** SKU lookups, checking if item exists, finding item IDs

---

## Linear MCP (`Linear:*`)

**Use for:** Project/issue management

- 17 read tools: `get_issue`, `list_issues`, `list_projects`, etc.
- 8 write tools: `create_issue`, `update_issue`, `create_comment`, etc.

---

## Decision Tree

```
Need to...
│
├─ Read/write text file on Mac? → Filesystem MCP
├─ Process binary image? → osascript + Python script
├─ Call Square API (JSON)? → Square MCP
├─ Upload image to Square? → Manual (Dashboard) or skip
├─ Search catalog fast? → square-cache MCP
├─ Git commit/push? → osascript
└─ Create Linear issue? → Linear MCP
```

---

## Two-Environment Architecture

| Environment | Paths | Access |
|-------------|-------|--------|
| **Claude's container** | `/mnt/skills/`, `/home/claude/` | `bash_tool`, `view`, `create_file` |
| **User's Mac** | `/Users/scottybe/`, `~/.claude/skills/` | `Filesystem:*`, `osascript` |

**Rule:** Files don't transfer between environments. Process everything on Mac.
