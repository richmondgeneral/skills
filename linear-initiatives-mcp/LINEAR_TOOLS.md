# Linear MCP Server Tools Reference

Comprehensive documentation of all 25 tools available in the Linear MCP server for project management operations.

## Comments
### list_comments
List comments on issues, projects, or other Linear entities.

### create_comment
Create a new comment on an issue or project.

## Cycles
### list_cycles
List all cycles (sprints) in the workspace.

## Documents
### get_document
Retrieve a specific Linear document by ID.

### list_documents
List all documents in the workspace.

### create_document
Create a new Linear document.

### update_document
Update an existing Linear document.

### search_documentation
Search through Linear documentation.

## Issues
### get_issue
Get details of a specific issue by ID.

### list_issues
List issues with optional filters (status, assignee, project, etc.).

### create_issue
Create a new issue in Linear.

### update_issue
Update an existing issue (status, assignee, priority, etc.).

### list_issue_statuses
List all available issue statuses in the workspace.

### get_issue_status
Get details of a specific issue status.

### list_issue_labels
List all issue labels in the workspace.

### create_issue_label
Create a new issue label.

## Projects
### list_projects
List all projects in the workspace.

### get_project
Get details of a specific project by ID.

### create_project
Create a new Linear project.

### update_project
Update an existing project.

### list_project_labels
List all labels available for projects.

## Teams
### list_teams
List all teams in the Linear workspace.

### get_team
Get details of a specific team by ID.

## Users
### list_users
List all users in the workspace.

### get_user
Get details of a specific user by ID.

## Usage Examples

### Create an Issue
```json
{
  "title": "Add WARP.md documentation",
  "description": "Create comprehensive documentation for AI agents",
  "teamId": "team-id-here",
  "priority": 1
}
```

### List Projects with Filters
```json
{
  "first": 20,
  "includeArchived": false
}
```

### Update Issue Status
```json
{
  "id": "issue-id-here",
  "stateId": "state-id-here"
}
```

### Create a Document
```json
{
  "title": "Architecture Documentation",
  "content": "# Overview\n\nDetailed architecture...",
  "projectId": "project-id-here"
}
```

## Key Concepts

### IDs Required
Most operations require specific IDs:
- `teamId`: Required when creating issues
- `projectId`: Links entities to projects
- `stateId`: For issue status updates
- `userId`: For assignments

### Common Filters
Many list operations support:
- `first`: Limit number of results (default 50, max 250)
- `includeArchived`: Include archived items (default false)
- Status/state filters
- Team filters

### Pagination
List operations return:
- `nodes`: Array of results
- `pageInfo`: Contains `hasNextPage` and `endCursor` for pagination

## Integration Notes

The Linear MCP server connects to Linear's GraphQL API and provides these tools through the Model Context Protocol (MCP), making Linear operations available to AI agents in Warp and Claude.

**Server Configuration**: See `~/.claude/skills/linear-initiatives-mcp/` for the MCP server implementation.

**Authentication**: Requires `LINEAR_API_KEY` environment variable from https://linear.app/settings/api

## Quick Start

### 1. Test the connection
```bash
# List all projects
list_projects
```

### 2. Create your first issue
```bash
# Get your team ID first
list_teams

# Create an issue
create_issue with teamId, title, and description
```

### 3. Explore documentation
```bash
# Search for specific topics
search_documentation with query="roadmap"

# List all documents
list_documents
```

## Tool Categories Summary

| Category | Tools | Primary Use |
|----------|-------|-------------|
| **Issues** | 7 tools | Create, read, update issues and manage labels/statuses |
| **Projects** | 4 tools | Full project lifecycle management |
| **Documents** | 4 tools | Knowledge base and documentation |
| **Comments** | 2 tools | Collaboration and discussion |
| **Teams** | 2 tools | Team organization |
| **Users** | 2 tools | User management |
| **Cycles** | 1 tool | Sprint/cycle tracking |
| **Labels** | 3 tools | Organization and categorization |

**Total**: 25 tools for complete Linear workspace management
