# Requirements & common flags

## Requirements summary

- `git`
- Node.js 20+ and `npm` (the MCP server is a Node app, built from source on
  install). `--skills-only` mode skips Node requirements.

See the per-OS step-by-step guides ([macOS](macos.md), [Linux](linux.md), [Windows](windows.md)) for install commands.

## Common flags

```text
--uri <conn>        DocumentDB / MongoDB connection string
--yes               Non-interactive (don't prompt)
--dry-run           Print planned changes; write nothing
--uninstall         Remove MCP entries, skill symlinks, and ~/.documentdb-agent-kit
--clients <list>    Comma-separated: claude-code,claude-desktop,cursor,copilot-cli,gemini-cli
--skills-only       Skip MCP server install
--mcp-only          Skip skill linking
--mcp-ref <ref>     Git ref of microsoft/documentdb-mcp (default: main)
--profile <name>    CONNECTION_PROFILES key name (default: default)
```

Connection string can also be supplied via `$DOCUMENTDB_URI` (or
`$env:DOCUMENTDB_URI` on PowerShell). When neither flag nor env var is set and
a TTY is attached, the installer prompts.
