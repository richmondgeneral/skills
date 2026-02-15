# Official Anthropic Agent Skills Resources

As of February 2026, these are the primary official resources for developing Claude Code Agent Skills.

## Repositories

*   **Official Skills Repository:** [https://github.com/anthropics/skills](https://github.com/anthropics/skills)
    *   Contains the skill specification (`spec/`)
    *   Contains the skill template (`template/`)
    *   Contains official examples (`skills/`) including:
        *   `docx` (Word processing)
        *   `pdf` (PDF processing)
        *   `pptx` (PowerPoint)
        *   `xlsx` (Excel)

*   **Agent Skills Specification:** [https://github.com/anthropics/skills/tree/main/spec](https://github.com/anthropics/skills/tree/main/spec)

## Key Concepts

*   **Progressive Disclosure:** Skills are loaded lazily. Only the YAML frontmatter is loaded initially. The Markdown body is loaded only when the model decides to use the skill.
*   **Model-Invoked:** Skills are triggered by the model based on the `description` field, not by explicit user commands (though users can prompt for them).
*   **Directory Structure:**
    ```
    skill-name/
    ├── SKILL.md           # Instructions & Metadata
    ├── scripts/           # Python/Bash scripts
    └── references/        # Static documentation
    ```

## External Documentation

*   [Claude Code Documentation](https://docs.claude.com)
*   [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook) - Often contains agent patterns.
