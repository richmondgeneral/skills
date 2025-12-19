# Claude Skills Documentation - Downloaded December 19, 2025

This directory contains the latest official documentation about Claude Skills and the Agent Skills open standard.

## Key Documentation Files

### Official Specifications & Standards
- **agent-skills-specification.html** (379 KB) - The official Agent Skills open standard specification from agentskills.io
- **agent-skills-overview.html** (439 KB) - Platform documentation overview from platform.claude.com

### Implementation Guides
- **claude-skills-docs.html** (879 KB) - Complete guide to Agent Skills in Claude Code from docs.claude.com
- **anthropic-skills-README.md** (5.2 KB) - README from the official Anthropic Skills GitHub repository

### Announcements & Blog Posts
- **claude-skills-announcement.html** (591 KB) - Official Anthropic announcement of Skills feature
- **engineering-blog-agent-skills.html** (126 KB) - Engineering blog post: "Equipping agents for the real world with Agent Skills"

### Templates
- **skill-template-example.md** (14 B) - Basic skill template structure

## What Are Claude Skills?

<cite index="2-2,2-3">Agent Skills package expertise into discoverable capabilities. Each Skill consists of a SKILL.md file with instructions that Claude reads when relevant, plus optional supporting files like scripts and templates.</cite>

### Key Updates (December 18, 2025)

<cite index="8-33">Anthropic has added organization-wide management for skills, a directory featuring partner-built skills, and published Agent Skills as an open standard for cross-platform portability.</cite>

### Open Standard

<cite index="13-5">Agent Skills launched as an independent open standard with a specification and reference SDK available at https://agentskills.io</cite>

## Skills vs Other Tools

- **Skills**: Provide procedural knowledge—instructions for completing specific tasks or workflows
- **MCP (Model Context Protocol)**: Connects Claude to external services and data sources
- **Projects**: Provide static background knowledge always loaded in conversations
- **Custom Instructions**: Apply broadly to all conversations

<cite index="3-19,3-20">Skills provide procedural knowledge—instructions for how to complete specific tasks or workflows. You can use both together: MCP connections give Claude access to tools, while Skills teach Claude how to use those tools effectively.</cite>

## Basic Skill Structure

```
skill-name/
├── SKILL.md              # Main skill definition with YAML frontmatter
└── optional-resources/   # Scripts, templates, reference docs
```

Each SKILL.md includes:
- YAML frontmatter with `name` and `description`
- Instructions and workflows
- Examples and guidelines

## Key Benefits

<cite index="10-2">This filesystem-based architecture enables progressive disclosure: Claude loads information in stages as needed, rather than consuming context upfront.</cite>

## Resources

- Official Site: https://agentskills.io
- GitHub Repository: https://github.com/anthropics/skills
- Documentation: https://docs.claude.com/en/docs/claude-code/skills
- Platform Docs: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview

## Installation Locations

- Personal Skills: `~/.claude/skills/skill-name/SKILL.md`
- Project Skills: `.claude/skills/skill-name/SKILL.md`

## Partner Skills Available

Major partners have published Skills including:
- Atlassian
- Figma
- Canva
- Stripe
- Notion
- Zapier
- Microsoft (VS Code, GitHub)
- Cursor, Goose, Amp, OpenCode

---

**Note**: These are the latest official docs as of December 19, 2025, including the newly released Agent Skills open standard.
