# Richmond General Skills

AI assistant skills for managing Richmond General's vintage and antique inventory system.

## Skills

### rg-inventory
Main orchestrator skill for the complete inventory workflow from appraisal through GitHub Pages publishing.

**Use when:** Processing items, creating Square catalog entries, pricing vintage/antique items, generating labels, or tracking purchase lots.

### book-appraiser
Specialized skill for antiquarian and antique book appraisal, edition identification, and valuation.

**Use when:** Appraising pre-1970 books, identifying first editions, researching book value, checking Library of Congress holdings, or determining public domain status.

### carnival-glass-appraiser
Complete appraisal workflow for carnival glass (pressed iridescent glass from 1908-1930s).

**Use when:** Identifying carnival glass patterns, authenticating pieces, attributing makers (Northwood, Fenton, Imperial), or valuing bowls, plates, water sets.

### maker-mark-identifier
Focused identification skill for pottery, silver, furniture, and jewelry marks.

**Use when:** Examining stamps, hallmarks, signatures, or labels to determine manufacturer and date range. Returns ID only—defers valuation to rg-inventory.

### product-labeler
Generate product labels for Richmond General Square inventory and thermal printing.

**Use when:** Creating thermal printer labels (CSV for Print Master), Square catalog descriptions, or price tags.

### vintage-appraiser *(deprecated)*
> **Note:** Being replaced by focused skills: `carnival-glass-appraiser` (TVM-24) and `maker-mark-identifier` (TVM-25). Will be removed after migration complete.

Legacy skill for identifying maker's marks, carnival glass, pottery, silver, and other vintage collectibles.

## Structure

```
skills/
├── rg-inventory/           # Main orchestrator
│   ├── SKILL.md
│   └── references/
├── book-appraiser/         # Full appraisal: books
│   ├── SKILL.md
│   └── references/
├── carnival-glass-appraiser/  # Full appraisal: carnival glass
│   ├── SKILL.md
│   └── references/
├── maker-mark-identifier/  # ID only: marks on pottery, silver, furniture
│   ├── SKILL.md
│   └── references/
├── product-labeler/        # Labels & Square descriptions
│   ├── SKILL.md
│   ├── assets/
│   └── references/
├── imessage-assistant/     # iMessage integration
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── square-crm/             # Square customer management
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── skill-manager/          # Meta-skill for skill updates
│   └── SKILL.md
├── vintage-appraiser/      # (deprecated)
│   ├── SKILL.md
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
