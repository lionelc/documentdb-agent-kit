# Manual install (no script)

If you don't want to run the installer, every step is documented in the
[`documentdb-mcp-setup` skill](../../skills/mcp-setup/SKILL.md) (per-client config
file paths, MCP server config template, `CONNECTION_PROFILES` JSON, etc.).
For skills-only manual install:

```bash
# Claude Code (project-scoped)
mkdir -p .claude && ln -s "$(pwd)/skills" .claude/skills

# Claude Code (user-scoped)
mkdir -p ~/.claude/skills && for d in skills/*/; do ln -s "$(pwd)/$d" ~/.claude/skills/; done

# Gemini CLI (project-scoped)
ln -s AGENTS.md GEMINI.md

# GitHub Copilot / other AGENTS.md-aware clients: drop AGENTS.md + skills/ at repo root
```

On Windows, use `New-Item -ItemType SymbolicLink` or copy folders.
