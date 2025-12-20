#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import fetch from 'node-fetch';

const LINEAR_API_URL = 'https://api.linear.app/graphql';

class LinearInitiativesServer {
  constructor() {
    this.server = new Server(
      {
        name: 'linear-initiatives',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
    this.server.onerror = (error) => console.error('[MCP Error]', error);
    process.on('SIGINT', async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  async makeLinearRequest(query, variables = {}) {
    const apiKey = process.env.LINEAR_API_KEY;
    if (!apiKey) {
      throw new Error('LINEAR_API_KEY environment variable is required');
    }

    const response = await fetch(LINEAR_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': apiKey,
      },
      body: JSON.stringify({ query, variables }),
    });

    const result = await response.json();
    
    if (result.errors) {
      throw new Error(`Linear API error: ${JSON.stringify(result.errors)}`);
    }

    return result.data;
  }

  setupToolHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'create_initiative',
          description: 'Create a new Linear initiative',
          inputSchema: {
            type: 'object',
            properties: {
              name: {
                type: 'string',
                description: 'The name of the initiative (required)',
              },
              description: {
                type: 'string',
                description: 'The description of the initiative',
              },
              content: {
                type: 'string',
                description: 'The initiative content in markdown format',
              },
              status: {
                type: 'string',
                enum: ['Active', 'Completed', 'Planned'],
                description: 'The initiative status (default: Planned)',
              },
              ownerId: {
                type: 'string',
                description: 'The ID of the user who owns this initiative',
              },
              targetDate: {
                type: 'string',
                description: 'Target completion date (ISO 8601 format)',
              },
              color: {
                type: 'string',
                description: 'Color for the initiative (hex format)',
              },
              icon: {
                type: 'string',
                description: 'Icon for the initiative',
              },
            },
            required: ['name'],
          },
        },
        {
          name: 'list_initiatives',
          description: 'List all initiatives in the Linear workspace',
          inputSchema: {
            type: 'object',
            properties: {
              first: {
                type: 'number',
                description: 'Number of initiatives to return (max 250, default 50)',
                default: 50,
              },
              status: {
                type: 'string',
                enum: ['Active', 'Completed', 'Planned'],
                description: 'Filter by status',
              },
              includeArchived: {
                type: 'boolean',
                description: 'Include archived initiatives',
                default: false,
              },
            },
          },
        },
        {
          name: 'get_initiative',
          description: 'Get details of a specific initiative',
          inputSchema: {
            type: 'object',
            properties: {
              id: {
                type: 'string',
                description: 'The initiative ID',
              },
            },
            required: ['id'],
          },
        },
        {
          name: 'update_initiative',
          description: 'Update an existing initiative',
          inputSchema: {
            type: 'object',
            properties: {
              id: {
                type: 'string',
                description: 'The initiative ID',
              },
              name: {
                type: 'string',
                description: 'The name of the initiative',
              },
              description: {
                type: 'string',
                description: 'The description of the initiative',
              },
              content: {
                type: 'string',
                description: 'The initiative content in markdown format',
              },
              status: {
                type: 'string',
                enum: ['Active', 'Completed', 'Planned'],
                description: 'The initiative status',
              },
              ownerId: {
                type: 'string',
                description: 'The ID of the user who owns this initiative',
              },
              targetDate: {
                type: 'string',
                description: 'Target completion date (ISO 8601 format)',
              },
              color: {
                type: 'string',
                description: 'Color for the initiative (hex format)',
              },
              icon: {
                type: 'string',
                description: 'Icon for the initiative',
              },
            },
            required: ['id'],
          },
        },
        {
          name: 'archive_initiative',
          description: 'Archive an initiative',
          inputSchema: {
            type: 'object',
            properties: {
              id: {
                type: 'string',
                description: 'The initiative ID',
              },
            },
            required: ['id'],
          },
        },
        {
          name: 'link_project_to_initiative',
          description: 'Link a project to an initiative',
          inputSchema: {
            type: 'object',
            properties: {
              initiativeId: {
                type: 'string',
                description: 'The initiative ID',
              },
              projectId: {
                type: 'string',
                description: 'The project ID',
              },
              sortOrder: {
                type: 'number',
                description: 'Sort order for the project within the initiative',
              },
            },
            required: ['initiativeId', 'projectId'],
          },
        },
        {
          name: 'create_initiative_update',
          description: 'Create a status update for an initiative',
          inputSchema: {
            type: 'object',
            properties: {
              initiativeId: {
                type: 'string',
                description: 'The initiative ID',
              },
              body: {
                type: 'string',
                description: 'The update body in markdown format',
              },
              health: {
                type: 'string',
                enum: ['onTrack', 'atRisk', 'offTrack'],
                description: 'The health status of the initiative',
              },
            },
            required: ['initiativeId', 'body'],
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      try {
        const { name, arguments: args } = request.params;

        switch (name) {
          case 'create_initiative':
            return await this.createInitiative(args);
          case 'list_initiatives':
            return await this.listInitiatives(args);
          case 'get_initiative':
            return await this.getInitiative(args);
          case 'update_initiative':
            return await this.updateInitiative(args);
          case 'archive_initiative':
            return await this.archiveInitiative(args);
          case 'link_project_to_initiative':
            return await this.linkProjectToInitiative(args);
          case 'create_initiative_update':
            return await this.createInitiativeUpdate(args);
          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: 'text',
              text: `Error: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    });
  }

  async createInitiative(args) {
    const query = `
      mutation CreateInitiative($input: InitiativeCreateInput!) {
        initiativeCreate(input: $input) {
          success
          initiative {
            id
            name
            description
            content
            status
            targetDate
            color
            icon
            url
            owner {
              id
              name
              email
            }
            projects {
              nodes {
                id
                name
              }
            }
          }
        }
      }
    `;

    const input = {
      name: args.name,
      description: args.description,
      content: args.content,
      status: args.status || 'Planned',
      ownerId: args.ownerId,
      targetDate: args.targetDate,
      color: args.color,
      icon: args.icon,
    };

    // Remove undefined values
    Object.keys(input).forEach(key => input[key] === undefined && delete input[key]);

    const data = await this.makeLinearRequest(query, { input });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data.initiativeCreate, null, 2),
        },
      ],
    };
  }

  async listInitiatives(args) {
    const query = `
      query ListInitiatives($first: Int, $filter: InitiativeFilter) {
        initiatives(first: $first, filter: $filter) {
          nodes {
            id
            name
            description
            status
            targetDate
            color
            icon
            url
            owner {
              id
              name
              email
            }
            projects {
              nodes {
                id
                name
              }
            }
            createdAt
            updatedAt
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    `;

    const filter = {};
    if (args.status) {
      filter.status = { eq: args.status };
    }
    if (args.includeArchived === false) {
      filter.isArchived = { eq: false };
    }

    const variables = {
      first: args.first || 50,
      filter: Object.keys(filter).length > 0 ? filter : undefined,
    };

    const data = await this.makeLinearRequest(query, variables);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data.initiatives, null, 2),
        },
      ],
    };
  }

  async getInitiative(args) {
    const query = `
      query GetInitiative($id: String!) {
        initiative(id: $id) {
          id
          name
          description
          content
          status
          targetDate
          color
          icon
          url
          owner {
            id
            name
            email
          }
          projects {
            nodes {
              id
              name
              description
              state {
                name
              }
            }
          }
          initiativeUpdates {
            nodes {
              id
              body
              health
              createdAt
              user {
                name
              }
            }
          }
          createdAt
          updatedAt
          archivedAt
        }
      }
    `;

    const data = await this.makeLinearRequest(query, { id: args.id });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data.initiative, null, 2),
        },
      ],
    };
  }

  async updateInitiative(args) {
    const query = `
      mutation UpdateInitiative($id: String!, $input: InitiativeUpdateInput!) {
        initiativeUpdate(id: $id, input: $input) {
          success
          initiative {
            id
            name
            description
            content
            status
            targetDate
            color
            icon
            url
            owner {
              id
              name
              email
            }
          }
        }
      }
    `;

    const input = {
      name: args.name,
      description: args.description,
      content: args.content,
      status: args.status,
      ownerId: args.ownerId,
      targetDate: args.targetDate,
      color: args.color,
      icon: args.icon,
    };

    // Remove undefined values
    Object.keys(input).forEach(key => input[key] === undefined && delete input[key]);

    const data = await this.makeLinearRequest(query, { id: args.id, input });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data.initiativeUpdate, null, 2),
        },
      ],
    };
  }

  async archiveInitiative(args) {
    const query = `
      mutation ArchiveInitiative($id: String!) {
        initiativeArchive(id: $id) {
          success
        }
      }
    `;

    const data = await this.makeLinearRequest(query, { id: args.id });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data.initiativeArchive, null, 2),
        },
      ],
    };
  }

  async linkProjectToInitiative(args) {
    const query = `
      mutation LinkProjectToInitiative($input: InitiativeToProjectCreateInput!) {
        initiativeToProjectCreate(input: $input) {
          success
          initiativeToProject {
            id
            initiative {
              id
              name
            }
            project {
              id
              name
            }
            sortOrder
          }
        }
      }
    `;

    const input = {
      initiativeId: args.initiativeId,
      projectId: args.projectId,
      sortOrder: args.sortOrder,
    };

    // Remove undefined values
    Object.keys(input).forEach(key => input[key] === undefined && delete input[key]);

    const data = await this.makeLinearRequest(query, { input });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data.initiativeToProjectCreate, null, 2),
        },
      ],
    };
  }

  async createInitiativeUpdate(args) {
    const query = `
      mutation CreateInitiativeUpdate($input: InitiativeUpdateCreateInput!) {
        initiativeUpdateCreate(input: $input) {
          success
          initiativeUpdate {
            id
            body
            health
            createdAt
            initiative {
              id
              name
            }
            user {
              id
              name
            }
          }
        }
      }
    `;

    const input = {
      initiativeId: args.initiativeId,
      body: args.body,
      health: args.health,
    };

    // Remove undefined values
    Object.keys(input).forEach(key => input[key] === undefined && delete input[key]);

    const data = await this.makeLinearRequest(query, { input });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data.initiativeUpdateCreate, null, 2),
        },
      ],
    };
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Linear Initiatives MCP server running on stdio');
  }
}

const server = new LinearInitiativesServer();
server.run().catch(console.error);
