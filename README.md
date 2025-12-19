# Richmond General Skills

AI assistant skills for managing Richmond General's vintage and antique inventory system.

## Skills

### rg-inventory
Main orchestrator skill for the complete inventory workflow from appraisal through GitHub Pages publishing.

**Use when:** Processing items, creating Square catalog entries, pricing vintage/antique items, generating labels, or tracking purchase lots.

### book-appraiser
Specialized skill for antiquarian and antique book appraisal, edition identification, and valuation.

**Use when:** Appraising pre-1970 books, identifying first editions, researching book value, checking Library of Congress holdings, or determining public domain status.

### vintage-appraiser
Specialist skill for identifying maker's marks, carnival glass, pottery, silver, and other vintage collectibles.

**Use when:** Items need maker's mark identification, pattern identification, dating, or researching carnival glass, pottery, or antiques.

## Structure

```
skills/
├── rg-inventory/
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── book-appraiser/
│   ├── SKILL.md
│   └── references/
├── imessage-assistant/
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── square-crm/
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── build-skill.sh          # Build script for generating ZIP archives
└── archive/                # Generated ZIP files (not in git)
```

## Usage

These skills are designed to be loaded by AI assistants (Claude, Warp, etc.) to provide specialized knowledge and workflows for Richmond General inventory management.

## Building Skills

Skills are packaged as ZIP files for distribution. Use the build script to generate archives:

```bash
# Build a single skill
./build-skill.sh imessage-assistant

# Build all skills
./build-skill.sh --all

# List available skills
./build-skill.sh
```

Generated ZIP files are placed in `archive/` and are excluded from version control.

## Related Repositories

- **Items Site**: [richmondgeneral/items](https://github.com/richmondgeneral/items) - GitHub Pages site with item cards
- **Main Site**: richmondgeneral.com - Square-hosted ecommerce

## Integration

Skills integrate with:
- Square Catalog API
- Square Checkout API (payment links)
- GitHub Pages (richmondgeneral.github.io/items)
- Library of Congress catalog
- Print Master (label printing)

## License

© 2024-2025 Richmond General. All rights reserved.
