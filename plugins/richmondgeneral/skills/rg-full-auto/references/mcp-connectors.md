# MCP Connector Quick Reference

Last updated: 2026-02-15

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

**Use for:** Binary operations, shell commands, git, API scripts

```applescript
do shell script "source ~/.env && python3 ~/.claude/skills/[skill]/scripts/[script].py"
```

| Operation | Example |
|-----------|---------|
| Background removal | `python3 scripts/remove_background.py input.jpg output.png` |
| Image upload to Square | `python3 ~/.claude/skills/square-image-upload/scripts/upload_image.py ...` |
| QR generation | `python3 -c "import qrcode; ..."` |
| Git operations | `cd ~/.claude/skills && git add . && git commit -m "msg" && git push` |
| Open apps | `tell application "Preview" to open ...` |

**Why:** Scripts on Mac have access to `~/.env` (API keys), binary file I/O, and git.

---

## Square MCP (`mcp_square_api:*`)

**Use for:** Square API operations (JSON-first; multipart support depends on connector build)

| Tool | Purpose |
|------|---------|
| `get_service_info` | List available methods |
| `get_type_info` | Get request/response schemas |
| `make_api_request` | Execute API calls |

### Required usage pattern

For new methods (especially catalog/beta features), always use:

1. Discover
```
get_service_info(service: "catalog")
```

2. Understand request shape
```
get_type_info(service: "catalog", method: "list")
```

3. Execute
```
make_api_request(service: "catalog", method: "list", request: {})
```

**Works:** Catalog CRUD, payment links, customers, inventory, orders
**Multipart note:** Official Square MCP server may support `catalog.createImage` and `catalog.updateImage`, but behavior varies by MCP client/version.

### Runtime mode

Configured as Square Remote MCP:
- `npx mcp-remote https://mcp.squareup.com/sse`

This keeps Square auth/runtime managed by Square. If strict API version pinning is required later, switch to the local official server mode.

### Image Upload Default

Use `square-image-upload` as the default production path for image uploads:

```applescript
do shell script "source ~/.env && python3 ~/.claude/skills/square-image-upload/scripts/upload_image.py \
  --image /path/to/hero.png \
  --item-id CATALOG_ITEM_ID \
  --name 'Product Hero' \
  --primary"
```

✅ Deterministic across environments, independent of connector multipart support.

---

## Square Cache MCP (`square_cache_mcp:*`)

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
├─ Call Square API (JSON)? → mcp_square_api
├─ Upload image to Square? → osascript + square-image-upload skill ✅
├─ Search catalog fast? → square_cache_mcp
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
