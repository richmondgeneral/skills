# Linear Initiatives MCP Server

An MCP (Model Context Protocol) server that enables creation, management, and monitoring of Linear initiatives through the Linear GraphQL API.

## Features

This MCP server provides the following tools:

- **create_initiative** - Create a new Linear initiative
- **list_initiatives** - List all initiatives in your workspace
- **get_initiative** - Get detailed information about a specific initiative
- **update_initiative** - Update an existing initiative
- **archive_initiative** - Archive an initiative
- **link_project_to_initiative** - Link a project to an initiative
- **create_initiative_update** - Create status updates for initiatives (with health tracking)

## Prerequisites

- Node.js 18 or higher
- A Linear API key

## Installation

1. Install dependencies:

```bash
npm install
```

2. Get your Linear API key:
   - Go to https://linear.app/settings/api
   - Create a new Personal API key
   - Copy the key

3. Set your Linear API key as an environment variable:

```bash
export LINEAR_API_KEY="lin_api_xxxxxxxxxxxxx"
```

## Configuration

Add this server to your Warp MCP configuration file (`~/.config/warp/mcp_config.json`):

```json
{
  "mcpServers": {
    "linear-initiatives": {
      "command": "node",
      "args": ["/Users/scottybe/.claude/skills/linear-initiatives-mcp/index.js"],
      "env": {
        "LINEAR_API_KEY": "your_linear_api_key_here"
      }
    }
  }
}
```

Or if using Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "linear-initiatives": {
      "command": "node",
      "args": ["/Users/scottybe/.claude/skills/linear-initiatives-mcp/index.js"],
      "env": {
        "LINEAR_API_KEY": "your_linear_api_key_here"
      }
    }
  }
}
```

## Usage Examples

### Create an Initiative

```javascript
{
  "name": "Q1 2024 Platform Improvements",
  "description": "Major platform upgrades for Q1",
  "status": "Active",
  "targetDate": "2024-03-31"
}
```

### List Initiatives

```javascript
{
  "first": 20,
  "status": "Active",
  "includeArchived": false
}
```

### Create an Initiative Update

```javascript
{
  "initiativeId": "initiative-id-here",
  "body": "Made significant progress this week on the authentication system.",
  "health": "onTrack"
}
```

### Link a Project to an Initiative

```javascript
{
  "initiativeId": "initiative-id-here",
  "projectId": "project-id-here"
}
```

## Tools Reference

### create_initiative

Creates a new initiative in Linear.

**Parameters:**
- `name` (required): Initiative name
- `description`: Initiative description
- `content`: Full content in markdown
- `status`: One of "Active", "Completed", "Planned" (default: "Planned")
- `ownerId`: User ID of the owner
- `targetDate`: Target completion date (ISO 8601 format)
- `color`: Hex color code
- `icon`: Icon identifier

### list_initiatives

Lists initiatives in the workspace.

**Parameters:**
- `first`: Number of results (max 250, default 50)
- `status`: Filter by status ("Active", "Completed", "Planned")
- `includeArchived`: Include archived initiatives (default: false)

### get_initiative

Gets detailed information about a specific initiative.

**Parameters:**
- `id` (required): Initiative ID

### update_initiative

Updates an existing initiative.

**Parameters:**
- `id` (required): Initiative ID
- All other parameters from `create_initiative` are optional

### archive_initiative

Archives an initiative.

**Parameters:**
- `id` (required): Initiative ID

### link_project_to_initiative

Links a project to an initiative.

**Parameters:**
- `initiativeId` (required): Initiative ID
- `projectId` (required): Project ID
- `sortOrder`: Optional sort order

### create_initiative_update

Creates a status update for an initiative.

**Parameters:**
- `initiativeId` (required): Initiative ID
- `body` (required): Update content in markdown
- `health`: Health status ("onTrack", "atRisk", "offTrack")

## Development

To test the server locally:

```bash
npm start
```

The server runs on stdio and communicates using the MCP protocol.

## Security

- Never commit your LINEAR_API_KEY to version control
- Store API keys securely using environment variables
- The API key should have appropriate permissions in Linear

## License

MIT
