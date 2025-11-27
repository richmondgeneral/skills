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
│   └── references/
│       ├── lot-tracking.md
│       ├── pricing-guidelines.md
│       └── square-catalog.md
├── book-appraiser/
│   ├── SKILL.md
│   └── references/
│       └── condition-grading.md
└── vintage-appraiser.skill    # Zip archive format
```

## Usage

These skills are designed to be loaded by AI assistants (Claude, Warp, etc.) to provide specialized knowledge and workflows for Richmond General inventory management.

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
